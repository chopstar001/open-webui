"""Background task to poll SHKeeper for pending invoice statuses.

This bridges the gap when the XRP daemon's walletnotify to SHKeeper
fails due to DNS issues. The poller:
1. Gets all pending invoices with their addresses
2. Checks SHKeeper's internal DB for transactions on those addresses
3. If SHKeeper has recorded the transaction, sends the webhook callback
4. If not, manually triggers walletnotify on SHKeeper
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30
INVOICE_EXPIRY_SECONDS = 1800  # 30 minutes


async def poll_pending_invoices():
    """Periodically check for pending invoices and bridge the XRP→SHKeeper gap."""
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.subscription import (
        PaymentInvoice,
        PaymentInvoices,
        SubscriptionPlans,
        UserSubscriptions,
    )
    from open_webui.routers.billing import _apply_tier_permissions
    from open_webui.utils.shkeeper import check_invoice_paid_on_shkeeper, trigger_walletnotify
    from sqlalchemy import select

    log.info('Invoice polling task started (interval=%ds)', POLL_INTERVAL_SECONDS)

    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            # Get all pending/confirming invoices
            async with get_async_db_context() as session:
                stmt = select(PaymentInvoice).where(
                    PaymentInvoice.status.in_(['pending', 'confirming'])
                )
                pending = (await session.execute(stmt)).scalars().all()

            if not pending:
                continue

            now = int(time.time())

            for inv in pending:
                # Expire old invoices
                if now - inv.created_at > INVOICE_EXPIRY_SECONDS:
                    await PaymentInvoices.update_invoice_status(inv.id, status='expired')
                    log.info(f'Invoice {inv.id} expired')
                    continue

                if not inv.shkeeper_invoice_id:
                    continue

                # Check if SHKeeper has this invoice as paid
                is_paid = await check_invoice_paid_on_shkeeper(
                    inv.crypto_currency,
                    inv.shkeeper_invoice_id,
                )

                if is_paid:
                    log.info(f'Poll: invoice {inv.id} is paid on SHKeeper, activating...')

                    # Update invoice
                    await PaymentInvoices.update_invoice_status(
                        inv.id, status='confirmed'
                    )

                    # Activate subscription
                    plan = await SubscriptionPlans.get_plan_by_id(inv.plan_id)
                    if plan:
                        expires = now + (plan.billing_period_days * 86400) if plan.billing_period_days > 0 else None
                        await UserSubscriptions.upsert_subscription(
                            user_id=inv.user_id,
                            plan_id=inv.plan_id,
                            status='active',
                            started_at=now,
                            expires_at=expires,
                        )
                        await _apply_tier_permissions(inv.user_id, inv.plan_id)
                        log.info(f'Poll activated: user={inv.user_id} plan={inv.plan_id}')
                    continue

                # If not paid yet, try to trigger walletnotify on SHKeeper
                # This bridges the gap when xrp-shkeeper→SHKeeper DNS fails
                if inv.crypto_address:
                    try:
                        await trigger_walletnotify(inv.crypto_currency, inv.crypto_address)
                    except Exception as e:
                        log.debug(f'walletnotify trigger failed for {inv.id}: {e}')

        except asyncio.CancelledError:
            log.info('Invoice polling task cancelled')
            break
        except Exception as e:
            log.error(f'Invoice polling error: {e}')
