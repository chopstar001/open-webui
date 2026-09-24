"""Add subscription, user subscription, and payment invoice tables

Revision ID: c7e4a2b9d3f1
Revises: d4c1a8e37b62
Create Date: 2026-09-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c7e4a2b9d3f1'
down_revision: str | None = 'd4c1a8e37b62'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if 'subscription_plan' not in existing:
        op.create_table(
        'subscription_plan',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.Column('billing_period_days', sa.Integer(), nullable=True),
        sa.Column('max_models', sa.Integer(), nullable=True),
        sa.Column('max_chats_per_day', sa.Integer(), nullable=True),
        sa.Column('max_file_uploads', sa.Integer(), nullable=True),
        sa.Column('max_knowledge_bases', sa.Integer(), nullable=True),
        sa.Column('max_tokens_per_chat', sa.Integer(), nullable=True),
        sa.Column('enable_image_generation', sa.Boolean(), nullable=True),
        sa.Column('enable_code_interpreter', sa.Boolean(), nullable=True),
        sa.Column('enable_web_search', sa.Boolean(), nullable=True),
        sa.Column('enable_api_access', sa.Boolean(), nullable=True),
        sa.Column('priority_queue', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
    )

    if 'user_subscription' not in existing:
        op.create_table(
        'user_subscription',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_id', sa.String(), sa.ForeignKey('subscription_plan.id'), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('started_at', sa.BigInteger(), nullable=True),
        sa.Column('expires_at', sa.BigInteger(), nullable=True),
        sa.Column('cancelled_at', sa.BigInteger(), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
    )
    if 'user_subscription' not in existing:
        op.create_index('ix_user_subscription_user_id', 'user_subscription', ['user_id'])

    if 'payment_invoice' not in existing:
        op.create_table(
        'payment_invoice',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_id', sa.String(), sa.ForeignKey('subscription_plan.id'), nullable=False),
        sa.Column('shkeeper_invoice_id', sa.String(), nullable=True),
        sa.Column('crypto_currency', sa.String(), nullable=False),
        sa.Column('crypto_amount', sa.Float(), nullable=True),
        sa.Column('crypto_address', sa.String(), nullable=True),
        sa.Column('fiat_amount', sa.Float(), nullable=False),
        sa.Column('fiat_currency', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('confirmations', sa.Integer(), nullable=True),
        sa.Column('tx_hash', sa.String(), nullable=True),
        sa.Column('webhook_received_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
    )
    if 'payment_invoice' not in existing:
        op.create_index('ix_payment_invoice_user_id', 'payment_invoice', ['user_id'])
    op.create_index('ix_payment_invoice_shkeeper_invoice_id', 'payment_invoice', ['shkeeper_invoice_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_payment_invoice_shkeeper_invoice_id', 'payment_invoice')
    op.drop_index('ix_payment_invoice_user_id', 'payment_invoice')
    op.drop_table('payment_invoice')
    op.drop_index('ix_user_subscription_user_id', 'user_subscription')
    op.drop_table('user_subscription')
    op.drop_table('subscription_plan')
