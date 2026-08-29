"""Add subscription tables for tiered accounts and SHKeeper billing

Revision ID: a7b8c9d0e1f2
Revises: 42e2978c7933, 4de81c2a3af1, c0fbf31ca0db, d4e5f6a7b8c9
Create Date: 2026-07-10 08:15:00.000000

Creates subscription_plan, user_subscription, and payment_invoice tables
for the tiered user account system with SHKeeper crypto payment gateway.
"""

import time
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from open_webui.migrations.util import get_existing_tables

revision: str = 'a7b8c9d0e1f2'
# This depends on all current heads (multi-head merge)
down_revision: Union[str, Sequence[str], None] = [
    '42e2978c7933',
    '4de81c2a3af1',
    'c0fbf31ca0db',
    'd4e5f6a7b8c9',
]
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    # ── subscription_plan ──
    if 'subscription_plan' not in existing_tables:
        op.create_table(
            'subscription_plan',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('price_usd', sa.Float(), server_default='0.0'),
            sa.Column('billing_period_days', sa.Integer(), server_default='30'),

            sa.Column('max_models', sa.Integer(), server_default='-1'),
            sa.Column('max_chats_per_day', sa.Integer(), server_default='-1'),
            sa.Column('max_file_uploads', sa.Integer(), server_default='-1'),
            sa.Column('max_knowledge_bases', sa.Integer(), server_default='-1'),
            sa.Column('max_tokens_per_chat', sa.Integer(), server_default='-1'),
            sa.Column('enable_image_generation', sa.Boolean(), server_default=sa.text('0')),
            sa.Column('enable_code_interpreter', sa.Boolean(), server_default=sa.text('0')),
            sa.Column('enable_web_search', sa.Boolean(), server_default=sa.text('1')),
            sa.Column('enable_api_access', sa.Boolean(), server_default=sa.text('0')),
            sa.Column('priority_queue', sa.Boolean(), server_default=sa.text('0')),

            sa.Column('is_active', sa.Boolean(), server_default=sa.text('1')),
            sa.Column('sort_order', sa.Integer(), server_default='0'),
            sa.Column('created_at', sa.BigInteger()),
            sa.Column('updated_at', sa.BigInteger()),
        )

    # Seed default plans (idempotent — skip if 'free' already exists)
    conn = op.get_bind()
    check = conn.execute(sa.text("SELECT COUNT(*) FROM subscription_plan WHERE id = 'free'")).scalar()
    if check == 0:
        now = int(time.time())
        plans = [
            ('free', 'Free', 'Basic access with limited features', 0.0, 0,
             3, 50, 5, 1, 4096, 0, 0, 1, 0, 0, 1, 0, now, now),
            ('pro', 'Pro', 'Full access to all models and features', 20.0, 30,
             -1, -1, 50, 10, 32768, 1, 1, 1, 1, 0, 1, 1, now, now),
            ('ultra', 'Ultra', 'Unlimited access with priority queue', 100.0, 30,
             -1, -1, -1, -1, 128000, 1, 1, 1, 1, 1, 1, 2, now, now),
        ]
        for p in plans:
            conn.execute(
                sa.text(
                    "INSERT INTO subscription_plan "
                    "(id, name, description, price_usd, billing_period_days, "
                    "max_models, max_chats_per_day, max_file_uploads, max_knowledge_bases, "
                    "max_tokens_per_chat, enable_image_generation, enable_code_interpreter, "
                    "enable_web_search, enable_api_access, priority_queue, "
                    "is_active, sort_order, created_at, updated_at) "
                    "VALUES (:id, :name, :description, :price_usd, :billing_period_days, "
                    ":max_models, :max_chats_per_day, :max_file_uploads, :max_knowledge_bases, "
                    ":max_tokens_per_chat, :enable_image_generation, :enable_code_interpreter, "
                    ":enable_web_search, :enable_api_access, :priority_queue, "
                    ":is_active, :sort_order, :created_at, :updated_at)"
                ),
                dict(zip(
                    ['id', 'name', 'description', 'price_usd', 'billing_period_days',
                     'max_models', 'max_chats_per_day', 'max_file_uploads', 'max_knowledge_bases',
                     'max_tokens_per_chat', 'enable_image_generation', 'enable_code_interpreter',
                     'enable_web_search', 'enable_api_access', 'priority_queue',
                     'is_active', 'sort_order', 'created_at', 'updated_at'],
                    p,
                )),
            )

    # ── user_subscription ──
    if 'user_subscription' not in existing_tables:
        op.create_table(
            'user_subscription',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
            sa.Column('plan_id', sa.String(), sa.ForeignKey('subscription_plan.id'), nullable=False),

            sa.Column('status', sa.String(), server_default='pending'),
            sa.Column('started_at', sa.BigInteger(), nullable=True),
            sa.Column('expires_at', sa.BigInteger(), nullable=True),
            sa.Column('cancelled_at', sa.BigInteger(), nullable=True),
            sa.Column('auto_renew', sa.Boolean(), server_default=sa.text('1')),

            sa.Column('created_at', sa.BigInteger()),
            sa.Column('updated_at', sa.BigInteger()),
        )
        op.create_index('ix_user_subscription_user_id', 'user_subscription', ['user_id'])

    # ── payment_invoice ──
    if 'payment_invoice' not in existing_tables:
        op.create_table(
            'payment_invoice',
            sa.Column('id', sa.String(), nullable=False, primary_key=True),
            sa.Column('user_id', sa.String(), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
            sa.Column('plan_id', sa.String(), sa.ForeignKey('subscription_plan.id'), nullable=False),

            sa.Column('shkeeper_invoice_id', sa.String(), unique=True, nullable=True),
            sa.Column('crypto_currency', sa.String(), nullable=False),
            sa.Column('crypto_amount', sa.Float(), nullable=True),
            sa.Column('crypto_address', sa.String(), nullable=True),
            sa.Column('fiat_amount', sa.Float(), nullable=False),
            sa.Column('fiat_currency', sa.String(), server_default='USD'),

            sa.Column('status', sa.String(), server_default='pending'),
            sa.Column('confirmations', sa.Integer(), server_default='0'),
            sa.Column('tx_hash', sa.String(), nullable=True),

            sa.Column('webhook_received_at', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.BigInteger()),
            sa.Column('updated_at', sa.BigInteger()),
        )
        op.create_index('ix_payment_invoice_user_id', 'payment_invoice', ['user_id'])


def downgrade() -> None:
    existing_tables = set(get_existing_tables())

    if 'payment_invoice' in existing_tables:
        op.drop_index('ix_payment_invoice_user_id', table_name='payment_invoice')
        op.drop_table('payment_invoice')

    if 'user_subscription' in existing_tables:
        op.drop_index('ix_user_subscription_user_id', table_name='user_subscription')
        op.drop_table('user_subscription')

    if 'subscription_plan' in existing_tables:
        op.drop_table('subscription_plan')
