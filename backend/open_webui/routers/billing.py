"""Billing API — subscription plans, invoices, and SHKeeper webhook handler."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.models.subscription import (
    CreateInvoiceForm,
    PaymentInvoices,
    PaymentInvoiceModel,
    SubscriptionPlanCreateForm,
    SubscriptionPlanModel,
    SubscriptionPlans,
    UserSubscriptionModel,
    UserSubscriptions,
)
from open_webui.models.users import UserModel
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.shkeeper import (
    create_payment_request,
    get_supported_currencies,
    verify_webhook_api_key,
)

log = logging.getLogger(__name__)

router = APIRouter()


# ── Webhook callback URL ──
# This is the URL that SHKeeper will POST to when a payment is confirmed.
# From SHKeeper's Docker container, this must resolve to TASA WebUI's billing endpoint.
# host.docker.internal:3000 works because SHKeeper has extra_hosts mapping.
# Override via SHKEEPER_CALLBACK_URL env var if needed.
import os
SHKEEPER_CALLBACK_URL = os.getenv(
    'SHKEEPER_CALLBACK_URL',
    'http://host.docker.internal:3000/api/v1/billing/webhook'
)


############################
# Public: List subscription plans
############################


@router.get('/plans', response_model=list[SubscriptionPlanModel])
async def list_plans(db: AsyncSession = Depends(get_async_session)):
    """List all active subscription plans. Public endpoint."""
    return await SubscriptionPlans.get_all_plans(active_only=True, db=db)


############################
# User: Get current subscription
############################


@router.get('/subscription', response_model=UserSubscriptionModel | None)
async def get_current_subscription(
    user: UserModel = Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get the current user's active subscription."""
    return await UserSubscriptions.get_active_subscription(user.id, db=db)


############################
# User: Get subscription plan limits
############################


@router.get('/limits')
async def get_my_limits(user: UserModel = Depends(get_verified_user)):
    """Get the feature limits for the current user's subscription tier."""
    from open_webui.utils.billing import get_user_plan_limits

    return await get_user_plan_limits(user.id)


############################
# User: Create invoice
############################


@router.post('/create-invoice', response_model=dict)
async def create_invoice(
    form_data: CreateInvoiceForm,
    request: Request,
    user: UserModel = Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a SHKeeper payment invoice for a subscription plan."""
    # 1. Validate plan exists
    plan = await SubscriptionPlans.get_plan_by_id(form_data.plan_id, db=db)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Subscription plan not found',
        )

    if plan.price_usd <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cannot create invoice for free plan',
        )

    # 2. Validate crypto currency
    try:
        supported = await get_supported_currencies()
    except Exception as e:
        log.error(f'Failed to get supported currencies from SHKeeper: {e}')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Payment gateway unavailable',
        )

    if form_data.crypto_currency not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Currency {form_data.crypto_currency} not supported. Available: {supported}',
        )

    # 3. Create invoice record in our DB
    invoice = await PaymentInvoices.create_invoice(
        user_id=user.id,
        plan_id=form_data.plan_id,
        crypto_currency=form_data.crypto_currency,
        fiat_amount=plan.price_usd,
        db=db,
    )

    # 4. Create payment request in SHKeeper
    try:
        shkeeper_response = await create_payment_request(
            crypto=form_data.crypto_currency,
            fiat_amount=plan.price_usd,
            external_id=invoice.id,
            callback_url=SHKEEPER_CALLBACK_URL,
        )
    except Exception as e:
        log.error(f'SHKeeper payment request failed: {e}')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Failed to create payment request',
        )

    if shkeeper_response.get('status') != 'success':
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'SHKeeper error: {shkeeper_response.get("message", "Unknown error")}',
        )

    # 5. Update invoice with SHKeeper details
    await PaymentInvoices.update_invoice_status(
        invoice.id,
        status='pending',
        db=db,
    )

    # Store SHKeeper invoice ID and payment details
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.subscription import PaymentInvoice

    async with get_async_db_context(db) as session:
        inv = await session.get(PaymentInvoice, invoice.id)
        if inv:
            shkeeper_id = str(shkeeper_response.get('id', ''))
            # Use try/except to handle UNIQUE constraint on shkeeper_invoice_id
            # (SHKeeper uses auto-increment IDs that can repeat after reset)
            try:
                inv.shkeeper_invoice_id = shkeeper_id
                inv.crypto_amount = float(shkeeper_response.get('amount', 0))
                inv.crypto_address = shkeeper_response.get('wallet', '')
                await session.commit()
            except Exception:
                await session.rollback()
                # If the SHKeeper ID already exists, append our UUID to make it unique
                inv.shkeeper_invoice_id = f"{shkeeper_id}-{invoice.id[:8]}"
                inv.crypto_amount = float(shkeeper_response.get('amount', 0))
                inv.crypto_address = shkeeper_response.get('wallet', '')
                await session.commit()

    return {
        'invoice_id': invoice.id,
        'crypto': form_data.crypto_currency,
        'amount': shkeeper_response.get('amount'),
        'wallet': shkeeper_response.get('wallet'),
        'exchange_rate': shkeeper_response.get('exchange_rate'),
        'fiat_amount': plan.price_usd,
        'fiat_currency': 'USD',
        'recalculate_after': shkeeper_response.get('recalculate_after', 0),
    }


############################
# User: List invoices
############################


@router.get('/invoices', response_model=list[PaymentInvoiceModel])
async def list_invoices(
    user: UserModel = Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all invoices for the current user."""
    return await PaymentInvoices.get_user_invoices(user.id, db=db)


############################
# User: Get invoice details
############################


@router.get('/invoice/{invoice_id}', response_model=PaymentInvoiceModel)
async def get_invoice(
    invoice_id: str,
    user: UserModel = Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get details of a specific invoice."""
    invoice = await PaymentInvoices.get_invoice_by_id(invoice_id, db=db)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Invoice not found',
        )
    if invoice.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Access denied',
        )
    return invoice


############################
# User: Cancel subscription
############################


@router.post('/cancel')
async def cancel_subscription(
    user: UserModel = Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Cancel the current user's active subscription."""
    result = await UserSubscriptions.cancel_subscription(user.id, db=db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No active subscription to cancel',
        )
    return {'status': 'cancelled'}


############################
# Webhook: SHKeeper payment callback
############################


@router.post('/webhook')
async def handle_shkeeper_webhook(request: Request):
    """Process SHKeeper payment confirmation webhook.

    SHKeeper POSTs to this endpoint when a payment status changes.
    The payload contains the invoice external_id (our invoice ID),
    payment status, and transaction details.

    We expect HTTP 202 response to confirm receipt.
    """
    # 1. Verify API key
    api_key = request.headers.get('X-Shkeeper-Api-Key', '')
    if not verify_webhook_api_key(api_key):
        log.warning('SHKeeper webhook: invalid API key')
        raise HTTPException(status_code=403, detail='Invalid API key')

    # 2. Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid JSON')

    external_id = payload.get('external_id')
    if not external_id:
        raise HTTPException(status_code=400, detail='Missing external_id')

    log.info(f'SHKeeper webhook received: {payload}')

    # 3. Look up invoice by our ID (external_id)
    invoice = await PaymentInvoices.get_invoice_by_id(external_id)
    if not invoice:
        log.warning(f'SHKeeper webhook: invoice not found: {external_id}')
        # Return 202 anyway to prevent SHKeeper from retrying
        return {'status': 'accepted'}

    # 4. Idempotency: skip if already confirmed or expired
    if invoice.status in ('confirmed', 'expired'):
        log.info(f'SHKeeper webhook: invoice {external_id} already {invoice.status}, skipping')
        return {'status': 'accepted'}

    # 5. Determine new status
    paid = payload.get('paid', False)
    shkeeper_status = payload.get('status', '').upper()

    if paid or shkeeper_status in ('PAID', 'OVERPAID'):
        new_status = 'confirmed'
    elif shkeeper_status == 'PARTIAL':
        new_status = 'confirming'
    else:
        new_status = 'pending'

    # 5. Update invoice
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.subscription import PaymentInvoice

    db = None
    async with get_async_db_context(db) as session:
        inv = await session.get(PaymentInvoice, invoice.id)
        if inv:
            inv.status = new_status
            transactions = payload.get('transactions', [])
            inv.confirmations = len(transactions)
            if transactions:
                # Use the triggering transaction's txid
                for tx in transactions:
                    if tx.get('trigger'):
                        inv.tx_hash = tx.get('txid')
                        break
                else:
                    inv.tx_hash = transactions[0].get('txid')
            import time
            inv.webhook_received_at = int(time.time())
            inv.updated_at = int(time.time())
            await session.commit()

    # 6. If confirmed, activate subscription and assign tier group
    if new_status == 'confirmed':
        plan = await SubscriptionPlans.get_plan_by_id(invoice.plan_id)
        if plan:
            import time
            now = int(time.time())
            expires = now + (plan.billing_period_days * 86400) if plan.billing_period_days > 0 else None

            await UserSubscriptions.upsert_subscription(
                user_id=invoice.user_id,
                plan_id=invoice.plan_id,
                status='active',
                started_at=now,
                expires_at=expires,
            )

            # Assign user to the appropriate tier group
            await _apply_tier_permissions(invoice.user_id, invoice.plan_id)

            log.info(f'Subscription activated: user={invoice.user_id} plan={invoice.plan_id}')

    # 7. Return 202 to confirm receipt
    return {'status': 'accepted'}


############################
# Tier permission mapping
############################

# Map plan IDs to group names created in the admin panel
TIER_GROUP_MAP = {
    'free': 'tier-free',
    'pro': 'tier-pro',
    'ultra': 'tier-ultra',
}


async def _apply_tier_permissions(user_id: str, plan_id: str):
    """Move user to the appropriate tier group based on their subscription.

    Removes user from all other tier groups first, then adds them to the
    target tier group. This leverages OWUI's existing Groups permission system.
    """
    from open_webui.models.groups import Groups

    target_group_name = TIER_GROUP_MAP.get(plan_id, 'tier-free')

    # Get user's current tier groups
    user_groups = await Groups.get_groups_by_member_id(user_id)
    tier_group_names = set(TIER_GROUP_MAP.values())

    # Remove user from all tier groups they're currently in
    for group in user_groups:
        if group.name in tier_group_names:
            await Groups.remove_users_from_group(group.id, user_ids=[user_id])

    # Add user to the target tier group
    target_group = await Groups.get_group_by_name(target_group_name)
    if target_group:
        await Groups.add_users_to_group(target_group.id, user_ids=[user_id])
        log.info(f'User {user_id} assigned to tier group: {target_group_name}')
    else:
        log.warning(f'Tier group not found: {target_group_name}. Create it in Admin → Users → Groups')


############################
# Supported currencies
############################


@router.get('/currencies')
async def list_currencies():
    """List supported cryptocurrencies from SHKeeper."""
    try:
        currencies = await get_supported_currencies()
        return {'currencies': currencies}
    except Exception as e:
        log.error(f'Failed to get currencies: {e}')
        return {'currencies': []}


############################
# Admin: List all subscriptions
############################


@router.get('/admin/subscriptions')
async def admin_list_subscriptions(
    user: UserModel = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Admin: List all active subscriptions."""
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.subscription import UserSubscription
    from sqlalchemy import select

    async with get_async_db_context(db) as session:
        stmt = (
            select(UserSubscription)
            .where(UserSubscription.status == 'active')
            .order_by(UserSubscription.created_at.desc())
        )
        results = (await session.execute(stmt)).scalars().all()
        return [UserSubscriptionModel.model_validate(r) for r in results]


############################
# Admin: Create/Update plan
############################


@router.post('/admin/plans', response_model=SubscriptionPlanModel)
async def admin_create_plan(
    form_data: SubscriptionPlanCreateForm,
    user: UserModel = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Admin: Create a new subscription plan."""
    existing = await SubscriptionPlans.get_plan_by_id(form_data.id, db=db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Plan {form_data.id} already exists',
        )
    return await SubscriptionPlans.create_plan(form_data, db=db)


@router.put('/admin/plans/{plan_id}', response_model=SubscriptionPlanModel)
async def admin_update_plan(
    plan_id: str,
    form_data: dict,
    user: UserModel = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Admin: Update an existing subscription plan."""
    result = await SubscriptionPlans.update_plan(plan_id, form_data, db=db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Plan {plan_id} not found',
        )
    return result
