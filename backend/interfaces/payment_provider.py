from abc import ABC, abstractmethod


TIER_LIMITS = {
    "basic": 1,
    "pro": 5,
    "enterprise": 999,
}


class PaymentProvider(ABC):
    provider_name: str

    @abstractmethod
    def get_tier_price_id(self, tier: str) -> str | None: ...

    def get_tier_limit(self, tier: str) -> int:
        return TIER_LIMITS.get(tier, 1)

    @abstractmethod
    def create_checkout(
        self,
        user_id: str,
        tier: str,
        success_url: str,
        cancel_url: str,
    ) -> str: ...

    @abstractmethod
    def create_portal(self, customer_id: str, return_url: str) -> str: ...

    @abstractmethod
    async def handle_webhook(self, payload: bytes, sig: str) -> dict: ...
