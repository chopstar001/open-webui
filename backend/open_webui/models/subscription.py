"""Subscription plan, user subscription, and payment invoice models."""

from __future__ import annotations

import time
import uuid
from typing import Optional

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession


####################
# Subscription Plan
# The house of many rooms — each tier a dwelling
# suited to its tenant's needs and means.
####################


class SubscriptionPlan(Base):
    """Defines available subscription tiers."""

    __tablename__ = 'subscription_plan'

    id = Column(String, primary_key=True)  # e.g. 'free', 'pro', 'enterprise'
    name = Column(String, nullable=False)  # Display name
    description = Column(Text, nullable=True)
    price_usd = Column(Float, default=0.0)  # Reference price in USD
    billing_period_days = Column(Integer, default=30)

    # Feature limits (-1 = unlimited)
    max_models = Column(Integer, default=-1)
    max_chats_per_day = Column(Integer, default=-1)
    max_file_uploads = Column(Integer, default=-1)
    max_knowledge_bases = Column(Integer, default=-1)
    max_tokens_per_chat = Column(Integer, default=-1)
    enable_image_generation = Column(Boolean, default=False)
    enable_code_interpreter = Column(Boolean, default=False)
    enable_web_search = Column(Boolean, default=True)
    enable_api_access = Column(Boolean, default=False)
    priority_queue = Column(Boolean, default=False)

    # Metadata
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class SubscriptionPlanModel(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price_usd: float = 0.0
    billing_period_days: int = 30

    max_models: int = -1
    max_chats_per_day: int = -1
    max_file_uploads: int = -1
    max_knowledge_bases: int = -1
    max_tokens_per_chat: int = -1
    enable_image_generation: bool = False
    enable_code_interpreter: bool = False
    enable_web_search: bool = True
    enable_api_access: bool = False
    priority_queue: bool = False

    is_active: bool = True
    sort_order: int = 0
    created_at: int = 0
    updated_at: int = 0

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanCreateForm(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price_usd: float = 0.0
    billing_period_days: int = 30

    max_models: int = -1
    max_chats_per_day: int = -1
    max_file_uploads: int = -1
    max_knowledge_bases: int = -1
    max_tokens_per_chat: int = -1
    enable_image_generation: bool = False
    enable_code_interpreter: bool = False
    enable_web_search: bool = True
    enable_api_access: bool = False
    priority_queue: bool = False

    sort_order: int = 0


####################
# User Subscription
####################


class UserSubscription(Base):
    """Tracks each user's current and historical subscriptions."""

    __tablename__ = 'user_subscription'

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = Column(String, ForeignKey('subscription_plan.id'), nullable=False)

    status = Column(String, default='pending')  # pending, active, expired, cancelled
    started_at = Column(BigInteger, nullable=True)
    expires_at = Column(BigInteger, nullable=True)
    cancelled_at = Column(BigInteger, nullable=True)
    auto_renew = Column(Boolean, default=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class UserSubscriptionModel(BaseModel):
    id: str
    user_id: str
    plan_id: str

    status: str = 'pending'
    started_at: Optional[int] = None
    expires_at: Optional[int] = None
    cancelled_at: Optional[int] = None
    auto_renew: bool = True

    created_at: int = 0
    updated_at: int = 0

    model_config = ConfigDict(from_attributes=True)


####################
# Payment Invoice
####################


class PaymentInvoice(Base):
    """Tracks invoices created through SHKeeper."""

    __tablename__ = 'payment_invoice'

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = Column(String, ForeignKey('subscription_plan.id'), nullable=False)

    # SHKeeper fields
    shkeeper_invoice_id = Column(String, unique=True, nullable=True)
    crypto_currency = Column(String, nullable=False)
    crypto_amount = Column(Float, nullable=True)
    crypto_address = Column(String, nullable=True)
    fiat_amount = Column(Float, nullable=False)
    fiat_currency = Column(String, default='USD')

    # Status
    status = Column(String, default='pending')  # pending, confirming, confirmed, expired, failed
    confirmations = Column(Integer, default=0)
    tx_hash = Column(String, nullable=True)

    # Webhook verification
    webhook_received_at = Column(BigInteger, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class PaymentInvoiceModel(BaseModel):
    id: str
    user_id: str
    plan_id: str

    shkeeper_invoice_id: Optional[str] = None
    crypto_currency: str
    crypto_amount: Optional[float] = None
    crypto_address: Optional[str] = None
    fiat_amount: float
    fiat_currency: str = 'USD'

    status: str = 'pending'
    confirmations: int = 0
    tx_hash: Optional[str] = None

    webhook_received_at: Optional[int] = None

    created_at: int = 0
    updated_at: int = 0

    model_config = ConfigDict(from_attributes=True)


class CreateInvoiceForm(BaseModel):
    plan_id: str
    crypto_currency: str = 'XRP'


# ── Data Access Layer ──


class SubscriptionPlansTable:
    async def get_all_plans(
        self,
        active_only: bool = True,
        db: AsyncSession | None = None,
    ) -> list[SubscriptionPlanModel]:
        async with get_async_db_context(db) as session:
            stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.sort_order)
            if active_only:
                stmt = stmt.where(SubscriptionPlan.is_active.is_(True))
            results = (await session.execute(stmt)).scalars().all()
            return [SubscriptionPlanModel.model_validate(r) for r in results]

    async def get_plan_by_id(
        self,
        plan_id: str,
        db: AsyncSession | None = None,
    ) -> SubscriptionPlanModel | None:
        async with get_async_db_context(db) as session:
            plan = await session.get(SubscriptionPlan, plan_id)
            return SubscriptionPlanModel.model_validate(plan) if plan else None

    async def create_plan(
        self,
        form_data: SubscriptionPlanCreateForm,
        db: AsyncSession | None = None,
    ) -> SubscriptionPlanModel:
        now = int(time.time())
        async with get_async_db_context(db) as session:
            plan = SubscriptionPlan(
                **form_data.model_dump(),
                created_at=now,
                updated_at=now,
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return SubscriptionPlanModel.model_validate(plan)

    async def update_plan(
        self,
        plan_id: str,
        form_data: dict,
        db: AsyncSession | None = None,
    ) -> SubscriptionPlanModel | None:
        async with get_async_db_context(db) as session:
            form_data['updated_at'] = int(time.time())
            stmt = (
                update(SubscriptionPlan)
                .where(SubscriptionPlan.id == plan_id)
                .values(**form_data)
            )
            await session.execute(stmt)
            await session.commit()
            plan = await session.get(SubscriptionPlan, plan_id)
            return SubscriptionPlanModel.model_validate(plan) if plan else None

    async def delete_plan(
        self,
        plan_id: str,
        db: AsyncSession | None = None,
    ) -> bool:
        async with get_async_db_context(db) as session:
            stmt = delete(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0


class UserSubscriptionsTable:
    async def get_active_subscription(
        self,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> UserSubscriptionModel | None:
        now = int(time.time())
        async with get_async_db_context(db) as session:
            stmt = (
                select(UserSubscription)
                .where(
                    UserSubscription.user_id == user_id,
                    UserSubscription.status == 'active',
                    (UserSubscription.expires_at > now) | (UserSubscription.expires_at.is_(None)),
                )
                .order_by(UserSubscription.created_at.desc())
                .limit(1)
            )
            result = (await session.execute(stmt)).scalars().first()
            return UserSubscriptionModel.model_validate(result) if result else None

    async def get_user_subscriptions(
        self,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> list[UserSubscriptionModel]:
        async with get_async_db_context(db) as session:
            stmt = (
                select(UserSubscription)
                .where(UserSubscription.user_id == user_id)
                .order_by(UserSubscription.created_at.desc())
            )
            results = (await session.execute(stmt)).scalars().all()
            return [UserSubscriptionModel.model_validate(r) for r in results]

    async def upsert_subscription(
        self,
        user_id: str,
        plan_id: str,
        status: str = 'active',
        started_at: int | None = None,
        expires_at: int | None = None,
        db: AsyncSession | None = None,
    ) -> UserSubscriptionModel:
        now = int(time.time())
        async with get_async_db_context(db) as session:
            # Cancel any existing active subscriptions
            stmt = (
                update(UserSubscription)
                .where(
                    UserSubscription.user_id == user_id,
                    UserSubscription.status == 'active',
                )
                .values(status='expired', updated_at=now)
            )
            await session.execute(stmt)

            # Create new subscription
            sub = UserSubscription(
                id=str(uuid.uuid4()),
                user_id=user_id,
                plan_id=plan_id,
                status=status,
                started_at=started_at or now,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            return UserSubscriptionModel.model_validate(sub)

    async def cancel_subscription(
        self,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> bool:
        now = int(time.time())
        async with get_async_db_context(db) as session:
            stmt = (
                update(UserSubscription)
                .where(
                    UserSubscription.user_id == user_id,
                    UserSubscription.status == 'active',
                )
                .values(status='cancelled', cancelled_at=now, updated_at=now)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def expire_old_subscriptions(
        self,
        db: AsyncSession | None = None,
    ) -> int:
        """Mark expired subscriptions. Returns count of newly expired."""
        now = int(time.time())
        async with get_async_db_context(db) as session:
            stmt = (
                update(UserSubscription)
                .where(
                    UserSubscription.status == 'active',
                    UserSubscription.expires_at.isnot(None),
                    UserSubscription.expires_at <= now,
                )
                .values(status='expired', updated_at=now)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount


class PaymentInvoicesTable:
    async def create_invoice(
        self,
        user_id: str,
        plan_id: str,
        crypto_currency: str,
        fiat_amount: float,
        shkeeper_invoice_id: str | None = None,
        crypto_amount: float | None = None,
        crypto_address: str | None = None,
        db: AsyncSession | None = None,
    ) -> PaymentInvoiceModel:
        now = int(time.time())
        async with get_async_db_context(db) as session:
            invoice = PaymentInvoice(
                id=str(uuid.uuid4()),
                user_id=user_id,
                plan_id=plan_id,
                shkeeper_invoice_id=shkeeper_invoice_id,
                crypto_currency=crypto_currency,
                crypto_amount=crypto_amount,
                crypto_address=crypto_address,
                fiat_amount=fiat_amount,
                fiat_currency='USD',
                status='pending',
                created_at=now,
                updated_at=now,
            )
            session.add(invoice)
            await session.commit()
            await session.refresh(invoice)
            return PaymentInvoiceModel.model_validate(invoice)

    async def get_invoice_by_id(
        self,
        invoice_id: str,
        db: AsyncSession | None = None,
    ) -> PaymentInvoiceModel | None:
        async with get_async_db_context(db) as session:
            invoice = await session.get(PaymentInvoice, invoice_id)
            return PaymentInvoiceModel.model_validate(invoice) if invoice else None

    async def get_invoice_by_shkeeper_id(
        self,
        shkeeper_invoice_id: str,
        db: AsyncSession | None = None,
    ) -> PaymentInvoiceModel | None:
        async with get_async_db_context(db) as session:
            stmt = select(PaymentInvoice).where(
                PaymentInvoice.shkeeper_invoice_id == shkeeper_invoice_id
            )
            invoice = (await session.execute(stmt)).scalars().first()
            return PaymentInvoiceModel.model_validate(invoice) if invoice else None

    async def get_user_invoices(
        self,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> list[PaymentInvoiceModel]:
        async with get_async_db_context(db) as session:
            stmt = (
                select(PaymentInvoice)
                .where(PaymentInvoice.user_id == user_id)
                .order_by(PaymentInvoice.created_at.desc())
            )
            results = (await session.execute(stmt)).scalars().all()
            return [PaymentInvoiceModel.model_validate(r) for r in results]

    async def update_invoice_status(
        self,
        invoice_id: str,
        status: str,
        confirmations: int = 0,
        tx_hash: str | None = None,
        db: AsyncSession | None = None,
    ) -> PaymentInvoiceModel | None:
        now = int(time.time())
        async with get_async_db_context(db) as session:
            values = {
                'status': status,
                'confirmations': confirmations,
                'updated_at': now,
            }
            if tx_hash:
                values['tx_hash'] = tx_hash
            if status == 'confirmed':
                values['webhook_received_at'] = now

            stmt = (
                update(PaymentInvoice)
                .where(PaymentInvoice.id == invoice_id)
                .values(**values)
            )
            await session.execute(stmt)
            await session.commit()

            invoice = await session.get(PaymentInvoice, invoice_id)
            return PaymentInvoiceModel.model_validate(invoice) if invoice else None

    async def expire_stale_invoices(
        self,
        max_age_seconds: int = 1800,  # 30 minutes
        db: AsyncSession | None = None,
    ) -> int:
        """Mark invoices older than max_age as expired. Returns count."""
        cutoff = int(time.time()) - max_age_seconds
        async with get_async_db_context(db) as session:
            stmt = (
                update(PaymentInvoice)
                .where(
                    PaymentInvoice.status == 'pending',
                    PaymentInvoice.created_at < cutoff,
                )
                .values(status='expired', updated_at=int(time.time()))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount


# Singleton instances
SubscriptionPlans = SubscriptionPlansTable()
UserSubscriptions = UserSubscriptionsTable()
PaymentInvoices = PaymentInvoicesTable()
