"""Billing utilities — tier enforcement and subscription helpers."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from open_webui.models.users import UserModel
from open_webui.utils.auth import get_verified_user


# Tier hierarchy: higher number = higher tier
TIER_HIERARCHY: dict[str, int] = {
    'free': 0,
    'pro': 1,
    'ultra': 2,
}


def get_tier_level(plan_id: str | None) -> int:
    """Get the numeric level for a plan_id."""
    return TIER_HIERARCHY.get(plan_id or 'free', 0)


def require_subscription_tier(minimum_tier: str):
    """FastAPI dependency that enforces a minimum subscription tier.

    Usage:
        @router.post('/some-premium-feature')
        async def premium_feature(user=Depends(require_subscription_tier('pro'))):
            # Only 'pro' and 'ultra' users can access this
            ...
    """

    async def _check(user: UserModel = Depends(get_verified_user)):
        from open_webui.models.subscription import UserSubscriptions

        sub = await UserSubscriptions.get_active_subscription(user.id)
        user_tier = sub.plan_id if sub else 'free'

        if get_tier_level(user_tier) < get_tier_level(minimum_tier):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'This feature requires a {minimum_tier} subscription or higher.',
            )
        return user

    return _check


async def get_user_tier(user_id: str) -> str:
    """Get the current subscription tier for a user.

    Returns the plan_id string (e.g., 'free', 'pro', 'ultra').
    Defaults to 'free' if no active subscription.
    """
    from open_webui.models.subscription import UserSubscriptions

    sub = await UserSubscriptions.get_active_subscription(user_id)
    return sub.plan_id if sub else 'free'


async def get_user_plan_limits(user_id: str) -> dict[str, Any]:
    """Get the feature limits for a user's current subscription tier.

    Returns a dict of plan limits, or free-tier defaults if no subscription.
    """
    from open_webui.models.subscription import SubscriptionPlans, UserSubscriptions

    sub = await UserSubscriptions.get_active_subscription(user_id)
    plan_id = sub.plan_id if sub else 'free'

    plan = await SubscriptionPlans.get_plan_by_id(plan_id)
    if plan:
        return {
            'plan_id': plan.id,
            'plan_name': plan.name,
            'max_models': plan.max_models,
            'max_chats_per_day': plan.max_chats_per_day,
            'max_file_uploads': plan.max_file_uploads,
            'max_knowledge_bases': plan.max_knowledge_bases,
            'max_tokens_per_chat': plan.max_tokens_per_chat,
            'enable_image_generation': plan.enable_image_generation,
            'enable_code_interpreter': plan.enable_code_interpreter,
            'enable_web_search': plan.enable_web_search,
            'enable_api_access': plan.enable_api_access,
            'priority_queue': plan.priority_queue,
        }

    # Fallback free-tier defaults
    return {
        'plan_id': 'free',
        'plan_name': 'Free (default)',
        'max_models': 3,
        'max_chats_per_day': 50,
        'max_file_uploads': 5,
        'max_knowledge_bases': 1,
        'max_tokens_per_chat': 4096,
        'enable_image_generation': False,
        'enable_code_interpreter': False,
        'enable_web_search': True,
        'enable_api_access': False,
        'priority_queue': False,
    }
