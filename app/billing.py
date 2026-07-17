"""
BILLING — Shared access-check helpers, used by both the billing router and
the assessment router's paywall gate. Subscription rows are only ever written
by the webhook handler in app/routers/billing.py, driven by what Stripe
reports — everything here just reads that state.
"""

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models import Subscription, SubscriptionStatus, User

ACTIVE_STATUSES = {SubscriptionStatus.active, SubscriptionStatus.trialing}


def has_active_access(subscription: Subscription | None) -> bool:
    """Whether this subscription currently unlocks paid content."""
    return subscription is not None and subscription.status in ACTIVE_STATUSES


async def require_active_subscription(user: User = Depends(get_current_user)) -> User:
    """Route dependency: 402s unless the caller has an active subscription."""
    if not has_active_access(user.subscription):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="An active subscription is required to access the assessment.",
        )
    return user
