import { WEBUI_API_BASE_URL } from '$lib/constants';

// ── Types ──

export interface SubscriptionPlan {
    id: string;
    name: string;
    description: string | null;
    price_usd: number;
    billing_period_days: number;
    max_models: number;
    max_chats_per_day: number;
    max_file_uploads: number;
    max_knowledge_bases: number;
    max_tokens_per_chat: number;
    enable_image_generation: boolean;
    enable_code_interpreter: boolean;
    enable_web_search: boolean;
    enable_api_access: boolean;
    priority_queue: boolean;
    is_active: boolean;
    sort_order: number;
    created_at: number;
    updated_at: number;
}

export interface UserSubscription {
    id: string;
    user_id: string;
    plan_id: string;
    status: string;
    started_at: number | null;
    expires_at: number | null;
    cancelled_at: number | null;
    auto_renew: boolean;
    created_at: number;
    updated_at: number;
}

export interface PaymentInvoice {
    id: string;
    user_id: string;
    plan_id: string;
    shkeeper_invoice_id: string | null;
    crypto_currency: string;
    crypto_amount: number | null;
    crypto_address: string | null;
    fiat_amount: number;
    fiat_currency: string;
    status: string;
    confirmations: number;
    tx_hash: string | null;
    webhook_received_at: number | null;
    created_at: number;
    updated_at: number;
}

export interface InvoiceCreateResponse {
    invoice_id: string;
    crypto: string;
    amount: string;
    wallet: string;
    exchange_rate: string;
    fiat_amount: number;
    fiat_currency: string;
    recalculate_after: number;
}

// ── API Functions ──

export const getSubscriptionPlans = async (token: string): Promise<SubscriptionPlan[]> => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/plans`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.error(err);
            error = err.detail || err;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const getCurrentSubscription = async (token: string): Promise<UserSubscription | null> => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/subscription`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.error(err);
            error = err.detail || err;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const getSupportedCurrencies = async (token: string): Promise<{ currencies: string[] }> => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/currencies`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.error(err);
            error = err.detail || err;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const createInvoice = async (
    token: string,
    planId: string,
    cryptoCurrency: string
): Promise<InvoiceCreateResponse> => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/create-invoice`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
            plan_id: planId,
            crypto_currency: cryptoCurrency
        })
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.error(err);
            error = err.detail || err;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const getUserInvoices = async (token: string): Promise<PaymentInvoice[]> => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/invoices`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.error(err);
            error = err.detail || err;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const getInvoice = async (token: string, invoiceId: string): Promise<PaymentInvoice> => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/invoice/${invoiceId}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.error(err);
            error = err.detail || err;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const cancelSubscription = async (token: string): Promise<{ status: string }> => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/billing/cancel`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.error(err);
            error = err.detail || err;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};
