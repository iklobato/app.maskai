import httpx

from backend.interfaces.payment_provider import PaymentProvider

TIER_PRICE_IDS = {
    "basic": "price_basic",
    "pro": "price_pro",
    "enterprise": "price_enterprise",
}


class StripePaymentProvider(PaymentProvider):
    provider_name = "stripe"

    def __init__(self):
        from backend.config import settings

        self.secret_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret
        self.prices = {
            "basic": settings.stripe_price_basic,
            "pro": settings.stripe_price_pro,
            "enterprise": settings.stripe_price_enterprise,
        }

    def get_tier_price_id(self, tier: str) -> str | None:
        return self.prices.get(tier)

    def create_checkout(
        self,
        user_id: str,
        tier: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        from backend.database import SessionLocal, Subscription

        price_id = self.get_tier_price_id(tier)
        if not price_id:
            raise ValueError(f"Invalid tier: {tier}")
        db = SessionLocal()
        try:
            sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
            customer_id = sub.stripe_customer_id if sub else None
        finally:
            db.close()
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"user_id": user_id, "tier": tier},
        }
        if customer_id:
            payload["customer"] = customer_id
        with httpx.Client() as client:
            response = client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                headers=headers,
                data=payload,
            )
        response.raise_for_status()
        return response.json()["url"]

    def create_portal(self, customer_id: str, return_url: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {"customer": customer_id, "return_url": return_url}
        with httpx.Client() as client:
            response = client.post(
                "https://api.stripe.com/v1/billing_portal/sessions",
                headers=headers,
                data=payload,
            )
        response.raise_for_status()
        return response.json()["url"]

    async def handle_webhook(self, payload: bytes, sig: str) -> dict:
        import stripe

        stripe.api_key = self.secret_key
        try:
            event = stripe.Webhook.construct_event(payload, sig, self.webhook_secret)
        except ValueError:
            raise ValueError("Invalid payload")
        from backend.database import SessionLocal, Subscription

        db = SessionLocal()
        try:
            if event["type"] == "checkout.session.completed":
                session_data = event["data"]["object"]
                user_id = session_data["metadata"]["user_id"]
                tier = session_data["metadata"]["tier"]
                sub = (
                    db.query(Subscription)
                    .filter(Subscription.user_id == user_id)
                    .first()
                )
                if sub:
                    sub.tier = tier
                    sub.stripe_customer_id = session_data.get("customer")
                    sub.status = "active"
                else:
                    sub = Subscription(
                        user_id=user_id,
                        tier=tier,
                        status="active",
                        stripe_customer_id=session_data.get("customer"),
                        stripe_subscription_id=session_data.get("subscription"),
                    )
                    db.add(sub)
            elif event["type"] == "customer.subscription.updated":
                sub_data = event["data"]["object"]
                customer_id = sub_data["customer"]
                sub = (
                    db.query(Subscription)
                    .filter(Subscription.stripe_customer_id == customer_id)
                    .first()
                )
                if sub:
                    sub.status = sub_data["status"]
            elif event["type"] == "customer.subscription.deleted":
                sub_data = event["data"]["object"]
                customer_id = sub_data["customer"]
                sub = (
                    db.query(Subscription)
                    .filter(Subscription.stripe_customer_id == customer_id)
                    .first()
                )
                if sub:
                    sub.tier = "free"
                    sub.status = "canceled"
            db.commit()
        finally:
            db.close()
        return {"received": True}
