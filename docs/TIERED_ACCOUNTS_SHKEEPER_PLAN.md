# Tiered User Accounts with SHKeeper Crypto Payment Gateway

## Implementation Plan for TASA WebUI

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    TASA WebUI Stack                          │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  SvelteKit   │    │   FastAPI    │    │   SHKeeper   │  │
│  │  Frontend    │───▶│   Backend    │───▶│   Gateway    │  │
│  │  (:3000)     │    │  (:8080)     │    │  (:5555)     │  │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘  │
│                             │                    │          │
│                      ┌──────▼───────┐    ┌──────▼───────┐  │
│                      │  PostgreSQL  │    │    zrok      │  │
│                      │  (existing)  │    │  (external)  │  │
│                      └──────────────┘    └──────────────┘  │
│                                                             │
│  ┌──────────────┐                                          │
│  │   Ollama     │                                          │
│  │  (:11434)    │                                          │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. User selects a subscription tier in TASA WebUI frontend
2. Frontend calls `POST /api/v1/billing/create-invoice` on FastAPI backend
3. Backend calls SHKeeper API to create a crypto invoice (XRP, BTC, ETH, etc.)
4. Backend returns invoice details (address, amount, QR code) to frontend
5. User pays via crypto wallet
6. **Webhook callback URL**: Use the zrok public URL (e.g., `https://tasa-shkeeper.share.zrok.io/api/v1/billing/webhook`) as the callback. This must be reachable from the internet since blockchain nodes POST to it.
7. SHKeeper detects payment confirmation and sends webhook to `POST /api/v1/billing/webhook`
7. Backend validates webhook signature, updates user subscription tier in DB
8. User's permissions/models/features are updated accordingly via group membership

---

## 2. SHKeeper Docker Setup

### 2.1 Port Strategy

Since TASA WebUI already occupies host port **3000**, SHKeeper will be mapped to port **5555**.

### 2.2 Updated `docker-compose.yaml`

```yaml
services:
  ollama:
    volumes:
      - ollama:/root/.ollama
    container_name: ollama
    pull_policy: always
    tty: true
    restart: unless-stopped
    image: ollama/ollama:${OLLAMA_DOCKER_TAG-latest}

  open-webui:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/open-webui/open-webui:${WEBUI_DOCKER_TAG-main}
    container_name: open-webui
    volumes:
      - open-webui:/app/backend/data
    depends_on:
      - ollama
    ports:
      - ${OPEN_WEBUI_PORT-3000}:8080
    environment:
      - 'OLLAMA_BASE_URL=http://ollama:11434'
      - 'WEBUI_SECRET_KEY='
      # SHKeeper connection from within Docker network
      - 'SHKEEPER_API_URL=http://shkeeper:5555'
      - 'SHKEEPER_API_KEY=${SHKEEPER_API_KEY}'
      - 'SHKEEPER_WEBHOOK_SECRET=${SHKEEPER_WEBHOOK_SECRET}'
    extra_hosts:
      - host.docker.internal:host-gateway
    networks:
      - tasa-net
    restart: unless-stopped

  shkeeper:
    image: vsyshost/shkeeper:latest
    container_name: shkeeper
    restart: unless-stopped
    ports:
      - ${SHKEEPER_PORT-5555}:5555
    environment:
      - SHKEEPER_SECRET_KEY=${SHKEEPER_WEBHOOK_SECRET}
      # ── Coin daemon configuration ──
      # XRP node runs inside SHKeeper (self-hosted, no external server needed).
      # SHKeeper manages its own coin daemons by default. Check the repo's
      # example configs or docs for recommended per-coin settings.
      # Minimum recommended: 2+ CPU cores, 6-8 GB RAM, 20 GB+ SSD for XRP.
      # - XRP_WALLET_ADDRESS=${XRP_WALLET_ADDRESS}
      # - BTC_WALLET_ADDRESS=${BTC_WALLET_ADDRESS}
      # - ETH_WALLET_ADDRESS=${ETH_WALLET_ADDRESS}
    volumes:
      - shkeeper_data:/data
    networks:
      - tasa-net

  # Optional: zrok container for exposing SHKeeper externally
  # (if not running zrok on host)
  # zrok:
  #   image: openziti/zrok:latest
  #   container_name: zrok-shkeeper
  #   restart: unless-stopped
  #   network_mode: host
  #   command: ["share", "private", "http://localhost:5555", "--headless"]
  #   depends_on:
  #     - shkeeper

volumes:
  ollama: {}
  open-webui: {}
  shkeeper_data: {}

networks:
  tasa-net:
    driver: bridge
```

### 2.3 Environment Variables (add to `.env.example`)

```env
# ── SHKeeper Payment Gateway ──
SHKEEPER_PORT=5555
SHKEEPER_API_KEY=your_shkeeper_api_key_here
SHKEEPER_WEBHOOK_SECRET=your_webhook_secret_here
SHKEEPER_API_URL=http://shkeeper:5555

# ── Subscription Tiers ──
ENABLE_SUBSCRIPTION_TIERS=true

# ── zrok ──
ZROK_SHKEEPER_TOKEN=your_zrok_token_here
ZROK_SHKEEPER_SHARE_NAME=tasa-shkeeper
```

### 2.4 zrok Exposure for SHKeeper

SHKeeper needs to be externally reachable for webhook callbacks from the blockchain network. Use zrok to expose it:

```bash
# Reserve a stable share name (one-time setup)
zrok reserve public http://localhost:5555 --unique-name tasa-shkeeper

# Start the share
zrok share reserved tasa-shkeeper --headless
```

This gives you a stable URL like `https://tasa-shkeeper.share.zrok.io` that you configure as the webhook callback URL in SHKeeper's dashboard.

---

## 3. Database Schema Design

### 3.1 New Tables

#### `subscription_plan` — Tier definitions

```python
# backend/open_webui/models/subscription.py

class SubscriptionPlan(Base):
    """Defines available subscription tiers."""
    __tablename__ = 'subscription_plan'

    id = Column(String, primary_key=True)          # e.g. 'free', 'pro', 'enterprise'
    name = Column(String, nullable=False)           # Display name
    description = Column(Text, nullable=True)
    price_usd = Column(Float, default=0.0)          # Reference price in USD
    billing_period_days = Column(Integer, default=30)

    # Feature limits
    max_models = Column(Integer, default=-1)         # -1 = unlimited
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
```

#### `user_subscription` — Active subscriptions per user

```python
class UserSubscription(Base):
    """Tracks each user's current and historical subscriptions."""
    __tablename__ = 'user_subscription'

    id = Column(String, primary_key=True)           # UUID
    user_id = Column(String, ForeignKey('user.id'), nullable=False, index=True)
    plan_id = Column(String, ForeignKey('subscription_plan.id'), nullable=False)

    status = Column(String, default='pending')       # pending, active, expired, cancelled
    started_at = Column(BigInteger, nullable=True)
    expires_at = Column(BigInteger, nullable=True)
    cancelled_at = Column(BigInteger, nullable=True)
    auto_renew = Column(Boolean, default=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
```

#### `payment_invoice` — Invoice/payment tracking

```python
class PaymentInvoice(Base):
    """Tracks invoices created through SHKeeper."""
    __tablename__ = 'payment_invoice'

    id = Column(String, primary_key=True)            # UUID
    user_id = Column(String, ForeignKey('user.id'), nullable=False, index=True)
    plan_id = Column(String, ForeignKey('subscription_plan.id'), nullable=False)

    # SHKeeper fields
    shkeeper_invoice_id = Column(String, unique=True, nullable=True)
    crypto_currency = Column(String, nullable=False)  # XRP, BTC, ETH, etc.
    crypto_amount = Column(Float, nullable=True)
    crypto_address = Column(String, nullable=True)
    fiat_amount = Column(Float, nullable=False)
    fiat_currency = Column(String, default='USD')

    # Status
    status = Column(String, default='pending')        # pending, confirming, confirmed, expired, failed
    confirmations = Column(Integer, default=0)
    tx_hash = Column(String, nullable=True)

    # Webhook verification
    webhook_received_at = Column(BigInteger, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
```

### 3.2 Alembic Migration

A new migration file will be created:

```
backend/open_webui/migrations/versions/<hash>_add_subscription_tables.py
```

This will create all three tables with proper indexes and foreign keys.

---

## 4. Backend Implementation

### 4.1 New Models — `backend/open_webui/models/subscription.py`

SQLAlchemy models + Pydantic schemas for:
- `SubscriptionPlan`, `SubscriptionPlanModel`
- `UserSubscription`, `UserSubscriptionModel`
- `PaymentInvoice`, `PaymentInvoiceModel`
- `SubscriptionPlansTable`, `UserSubscriptionsTable`, `PaymentInvoicesTable`

### 4.2 New Router — `backend/open_webui/routers/billing.py`

API endpoints under `/api/v1/billing`:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/plans` | Public | List all active subscription plans |
| `GET` | `/subscription` | Verified User | Get current user's subscription |
| `POST` | `/create-invoice` | Verified User | Create a SHKeeper invoice for a plan |
| `GET` | `/invoices` | Verified User | List user's invoices |
| `GET` | `/invoice/{id}` | Verified User | Get invoice details |
| `POST` | `/webhook` | Signature-validated | SHKeeper webhook callback |
| `POST` | `/cancel` | Verified User | Cancel current subscription |
| `GET` | `/admin/subscriptions` | Admin | List all active subscriptions |
| `POST` | `/admin/plans` | Admin | Create/update subscription plans |

### 4.3 SHKeeper API Client — `backend/open_webui/utils/shkeeper.py`

```python
"""SHKeeper API client for invoice creation and status checking."""

import httpx
import hashlib
import hmac
from open_webui.env import SHKEEPER_API_URL, SHKEEPER_API_KEY

SHKEEPER_BASE = f"{SHKEEPER_API_URL}/api/v1"

async def create_invoice(
    amount: float,
    currency: str = "XRP",
    callback_url: str = None,
    description: str = None,
) -> dict:
    """Create a payment invoice via SHKeeper API.

    The callback_url should be the zrok public URL so SHKeeper can reach
    our webhook endpoint from the internet, e.g.:
        https://tasa-shkeeper.share.zrok.io/api/v1/billing/webhook
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SHKEEPER_BASE}/invoice",
            json={
                "amount": str(amount),
                "currency": currency,
                "callback_url": callback_url,
                "description": description or "TASA WebUI Subscription",
            },
            headers={
                "X-Api-Key": SHKEEPER_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


async def get_invoice_status(invoice_id: str) -> dict:
    """Check the status of an existing invoice."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SHKEEPER_BASE}/invoice/{invoice_id}",
            headers={"X-Api-Key": SHKEEPER_API_KEY},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


async def get_supported_currencies() -> list[str]:
    """Get list of supported cryptocurrencies."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SHKEEPER_BASE}/currencies",
            headers={"X-Api-Key": SHKEEPER_API_KEY},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify the HMAC signature of a SHKeeper webhook."""
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 4.4 Webhook Handler

The webhook endpoint in `billing.py`:

```python
@router.post('/webhook')
async def handle_shkeeper_webhook(request: Request):
    """Process SHKeeper payment confirmation webhook."""
    body = await request.body()
    signature = request.headers.get('X-Signature', '')

    # 1. Verify webhook signature
    if not verify_webhook_signature(body, signature, SHKEEPER_WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail='Invalid signature')

    payload = await request.json()

    # 2. Look up invoice by SHKeeper invoice ID
    invoice = await PaymentInvoices.get_invoice_by_shkeeper_id(
        payload.get('invoice_id')
    )
    if not invoice:
        raise HTTPException(status_code=404, detail='Invoice not found')

    # 3. Update invoice status
    new_status = payload.get('status')  # 'confirmed', 'confirming', etc.
    await PaymentInvoices.update_invoice_status(
        invoice.id,
        status=new_status,
        confirmations=payload.get('confirmations', 0),
        tx_hash=payload.get('tx_hash'),
    )

    # 4. If confirmed, activate the subscription
    if new_status == 'confirmed':
        plan = await SubscriptionPlans.get_plan_by_id(invoice.plan_id)
        if plan:
            import time
            now = int(time.time())
            expires = now + (plan.billing_period_days * 86400)

            await UserSubscriptions.upsert_subscription(
                user_id=invoice.user_id,
                plan_id=invoice.plan_id,
                status='active',
                started_at=now,
                expires_at=expires,
            )

            # 5. Update user's group membership to reflect tier
            await _apply_tier_permissions(invoice.user_id, invoice.plan_id)

    return {'status': 'ok'}
```

### 4.5 Tier-to-Permission Mapping

The integration leverages the existing **Groups** permission system. Each subscription tier maps to a pre-configured group:

```python
async def _apply_tier_permissions(user_id: str, plan_id: str):
    """Map subscription plan to group-based permissions."""
    from open_webui.models.groups import Groups

    # Map plan_id to group name
    TIER_GROUP_MAP = {
        'free': 'tier-free',
        'pro': 'tier-pro',
        'enterprise': 'tier-enterprise',
    }

    target_group_name = TIER_GROUP_MAP.get(plan_id, 'tier-free')

    # Remove user from all tier groups
    all_tier_groups = TIER_GROUP_MAP.values()
    for group_name in all_tier_groups:
        group = await Groups.get_group_by_name(group_name)
        if group:
            await Groups.remove_user_from_group(user_id, group.id)

    # Add user to the target tier group
    target_group = await Groups.get_group_by_name(target_group_name)
    if target_group:
        await Groups.add_user_to_group(user_id, target_group.id)
```

This means the admin creates groups like `tier-free`, `tier-pro`, `tier-enterprise` in the existing admin panel, each with appropriate permissions. The billing system just moves users between these groups based on their subscription.

### 4.6 Middleware — Subscription Validation

A dependency that can be injected into any route to enforce tier requirements:

```python
# backend/open_webui/utils/billing.py

from fastapi import Depends, HTTPException, status
from open_webui.models.users import UserModel
from open_webui.utils.auth import get_verified_user

async def require_subscription_tier(minimum_tier: str):
    """Dependency that enforces a minimum subscription tier."""

    TIER_HIERARCHY = {'free': 0, 'pro': 1, 'enterprise': 2}

    async def _check(user: UserModel = Depends(get_verified_user)):
        from open_webui.models.subscription import UserSubscriptions

        sub = await UserSubscriptions.get_active_subscription(user.id)
        user_tier = sub.plan_id if sub else 'free'

        if TIER_HIERARCHY.get(user_tier, 0) < TIER_HIERARCHY.get(minimum_tier, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'This feature requires a {minimum_tier} subscription or higher.',
            )
        return user

    return _check
```

Usage in other routers:

```python
@router.post('/some-premium-feature')
async def premium_feature(user=Depends(require_subscription_tier('pro'))):
    # Only 'pro' and 'enterprise' users can access this
    ...
```

### 4.7 Router Registration in `main.py`

```python
# Add to backend/open_webui/main.py router imports and registrations:
from open_webui.routers import billing

app.include_router(billing.router, prefix='/api/v1/billing', tags=['billing'])
```

---

## 5. Frontend Implementation

### 5.1 New API Client — `src/lib/apis/billing/index.ts`

```typescript
import { WEBUI_API_BASE_URL } from '$lib/constants';

// GET /api/v1/billing/plans
export const getSubscriptionPlans = async (token: string) => {
    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/plans`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
};

// GET /api/v1/billing/subscription
export const getCurrentSubscription = async (token: string) => {
    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/subscription`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
};

// POST /api/v1/billing/create-invoice
export const createInvoice = async (
    token: string,
    planId: string,
    cryptoCurrency: string
) => {
    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/create-invoice`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            plan_id: planId,
            crypto_currency: cryptoCurrency
        })
    });
    return res.json();
};

// GET /api/v1/billing/invoices
export const getUserInvoices = async (token: string) => {
    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/invoices`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
};

// GET /api/v1/billing/currencies
export const getSupportedCurrencies = async (token: string) => {
    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/currencies`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    return res.json();
};
```

### 5.2 New Pages

#### `src/routes/(app)/billing/+page.svelte` — Subscription Plans Page

Displays pricing tiers (Free / Pro / Enterprise) in a card layout with:
- Feature comparison table
- Price display (USD reference + crypto equivalent)
- "Subscribe" button per tier
- Current subscription indicator

#### `src/routes/(app)/billing/checkout/+page.svelte` — Crypto Payment Page

After selecting a plan:
1. Shows supported cryptocurrencies (XRP, BTC, ETH, etc.)
2. User selects preferred crypto
3. Calls `createInvoice()` API
4. Displays:
   - Payment address (copyable)
   - Amount to send
   - QR code
   - Countdown timer (invoice expiry)
   - **Real-time status polling every 3-5 seconds** (pending → confirming → confirmed)
   - **Estimated confirmation time** per crypto (XRP is typically ~4 seconds, BTC ~10 min)

#### `src/routes/(app)/billing/invoices/+page.svelte` — Invoice History

Lists all past invoices with status, date, amount, and crypto details.

#### `src/routes/(app)/billing/manage/+page.svelte` — Manage Subscription

Shows current plan, expiry date, cancel button, and upgrade/downgrade options.

### 5.3 Navigation Integration

Add a "Subscription" / "Billing" link to the user sidebar/settings menu in:
- `src/routes/(app)/+layout.svelte` — or wherever the sidebar navigation lives

### 5.4 Admin Pages

#### `src/routes/(app)/admin/billing/+page.svelte` — Admin Billing Dashboard

- View all active subscriptions
- View all invoices (with filters)
- Manage subscription plans (CRUD)
- Manually assign/override user tiers

---

## 6. Implementation Order (Phased Approach)

### Phase 1: Foundation (SHKeeper + Docker) — Week 1

- [ ] Add SHKeeper service to `docker-compose.yaml` (port 5555)
- [ ] Add environment variables to `.env.example`
- [ ] Set up zrok exposure for SHKeeper (reserve stable share name `tasa-shkeeper`)
- [ ] Configure SHKeeper dashboard (enable XRP + other coins)
- [ ] Verify SHKeeper API is accessible from the OWUI container via Docker network (`http://shkeeper:5555`)
- [ ] **Validate SHKeeper image & coin daemon configs** — check the repo's example configs or docs for recommended per-coin environment variables. XRP node runs inside SHKeeper (self-hosted). Minimum recommended: 2+ CPU cores, 6-8 GB RAM, 20 GB+ SSD.

### Phase 2: Database + Models — Week 1-2

- [ ] Create `backend/open_webui/models/subscription.py` (SQLAlchemy + Pydantic)
- [ ] Create Alembic migration for `subscription_plan`, `user_subscription`, `payment_invoice`
- [ ] Seed default plans (free, pro, enterprise) in migration
- [ ] Create admin groups (`tier-free`, `tier-pro`, `tier-enterprise`) in seed data

### Phase 3: Backend API — Week 2

- [ ] Create `backend/open_webui/utils/shkeeper.py` (API client)
- [ ] Create `backend/open_webui/routers/billing.py` (all endpoints)
- [ ] Implement webhook handler with signature verification
- [ ] Implement tier-to-group permission mapping
- [ ] Register router in `main.py`
- [ ] Add `require_subscription_tier()` dependency

### Phase 4: Frontend — Week 2-3

- [ ] Create `src/lib/apis/billing/index.ts` (API client)
- [ ] Create pricing/plans page (`/billing`)
- [ ] Create checkout/payment page (`/billing/checkout`)
- [ ] Create invoice history page (`/billing/invoices`)
- [ ] Create subscription management page (`/billing/manage`)
- [ ] Add billing navigation to sidebar

### Phase 5: Admin Panel — Week 3

- [ ] Create admin billing dashboard (`/admin/billing`)
- [ ] Plan management CRUD (create/edit/delete tiers)
- [ ] Manual subscription assignment
- [ ] Invoice viewer with filters

### Phase 5.5: Background Tasks — Week 3

- [ ] Implement background task (APScheduler or FastAPI `BackgroundTasks`) to:
  - [ ] Check and mark expired subscriptions (run every hour)
  - [ ] Auto-downgrade expired users to `tier-free` group
  - [ ] Mark invoices as expired past their TTL (30 min default)
  - [ ] Poll SHKeeper for stuck invoices (pending > 15 min with no webhook)

### Phase 6: Testing + Polish — Week 3-4

- [ ] **Start with testnet coins** if SHKeeper supports them — avoid spending real crypto during development
- [ ] End-to-end test: create invoice → pay test amount → confirm webhook → verify tier upgrade
- [ ] **Manual webhook testing**: Use `curl` to POST mock webhook payloads to the endpoint, verify signature validation and idempotent handling
- [ ] Test subscription expiry (cron/manual check)
- [ ] Test tier enforcement on gated features
- [ ] Test webhook replay protection
- [ ] Add rate limiting + input validation on `/create-invoice` endpoint
- [ ] Add proper error handling and user feedback
- [ ] Add i18n translation keys for billing UI

---

## 7. Security Considerations

1. **Webhook Signature Verification**: Every incoming webhook MUST be validated using HMAC with `SHKEEPER_WEBHOOK_SECRET`
2. **Idempotent Webhook Processing**: Store `shkeeper_invoice_id` with unique constraint; ignore duplicate webhook deliveries
3. **Invoice Expiry**: SHKeeper invoices should have a TTL (e.g., 30 minutes); implement a background task to mark expired invoices
4. **Amount Validation**: Verify the paid crypto amount matches the expected amount (accounting for crypto volatility)
5. **Rate Limiting**: Add rate limiting to `create-invoice` endpoint to prevent abuse (e.g., 5 invoices per user per hour)
6. **Input Validation**: Validate `plan_id` and `crypto_currency` against allowed values before calling SHKeeper
7. **Admin-Only Plan Management**: All plan CRUD operations require admin auth
8. **SHKeeper Isolation**: Run SHKeeper on the same Docker network but do not expose its admin port externally (only expose via zrok if needed for blockchain sync)
9. **Secret Storage**: Store `SHKEEPER_API_KEY` and `SHKEEPER_WEBHOOK_SECRET` securely — use Docker secrets or an external vault in production, not plaintext env vars
10. **Secret Rotation**: Support rotating `SHKEEPER_WEBHOOK_SECRET` without downtime
11. **Cold Wallet Auto-Withdrawal**: Configure SHKeeper to auto-withdraw received funds to a cold wallet
12. **Expired Subscription Enforcement**: Background task must actively downgrade expired subscriptions; do not rely solely on client-side checks

---

## 8. Key Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `backend/open_webui/models/subscription.py` | SQLAlchemy models + Pydantic schemas |
| `backend/open_webui/routers/billing.py` | Billing API endpoints |
| `backend/open_webui/utils/shkeeper.py` | SHKeeper API client |
| `backend/open_webui/utils/billing.py` | Tier enforcement dependency |
| `backend/open_webui/migrations/versions/<hash>_add_subscription_tables.py` | DB migration |
| `src/lib/apis/billing/index.ts` | Frontend API client |
| `src/routes/(app)/billing/+page.svelte` | Pricing page |
| `src/routes/(app)/billing/checkout/+page.svelte` | Payment checkout |
| `src/routes/(app)/billing/invoices/+page.svelte` | Invoice history |
| `src/routes/(app)/billing/manage/+page.svelte` | Manage subscription |
| `src/routes/(app)/admin/billing/+page.svelte` | Admin billing dashboard |

### Modified Files

| File | Change |
|------|--------|
| `docker-compose.yaml` | Add SHKeeper service |
| `.env.example` | Add SHKeeper env vars |
| `backend/open_webui/main.py` | Register billing router |
| `backend/open_webui/env.py` | Add SHKeeper env var loading |
| `src/routes/(app)/+layout.svelte` | Add billing nav link |
| `backend/open_webui/config.py` | Add billing-related config defaults |

---

## 9. Tier Definitions (Example)

| Feature | Free | Pro ($20/mo) | Enterprise ($100/mo) |
|---------|------|-------------|---------------------|
| Chat messages/day | 50 | Unlimited | Unlimited |
| Available models | Basic models only | All models | All models + priority |
| File uploads | 5/day | 50/day | Unlimited |
| Knowledge bases | 1 | 10 | Unlimited |
| Image generation | ✗ | ✓ | ✓ |
| Code interpreter | ✗ | ✓ | ✓ |
| Web search | ✓ | ✓ | ✓ |
| API access | ✗ | ✓ | ✓ |
| Priority queue | ✗ | ✗ | ✓ |
| Max tokens/chat | 4,096 | 32,768 | 128,000 |

These limits are enforced via the group permission system and the `require_subscription_tier()` middleware.

---

## 10. SHKeeper API Reference Notes

Based on the [SHKeeper GitHub repo](https://github.com/vsys-host/shkeeper.io):

- **Invoice Creation**: `POST /api/v1/invoice` — creates a payment invoice
- **Invoice Status**: `GET /api/v1/invoice/{id}` — checks payment status
- **Supported Currencies**: `GET /api/v1/currencies` — lists available cryptos
- **Webhook**: Configured per-invoice; SHKeeper POSTs to your callback URL on status change
- **Auth**: API key via `X-Api-Key` header

**Note**: The exact API endpoint paths may differ from the above — verify against the actual SHKeeper documentation after installation. The client in `shkeeper.py` should be updated to match the real API.

---

## 11. Future Enhancements

- **Stripe/Lightning integration** alongside SHKeeper for fiat on-ramp
- **Credit-based system** (pay-per-use alongside tiers)
- **Promo codes / referral system**
- **Usage analytics dashboard** for admins (revenue, active subscriptions)
- **Automated tier downgrade on expiry** via scheduled background task
- **Email notifications** for payment confirmation, expiry reminders
