from abc import ABC, abstractmethod


class OAuthProvider(ABC):
    provider_name: str

    @abstractmethod
    def get_auth_url(self, state: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str) -> dict[str, str]: ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> dict[str, str]: ...

    @abstractmethod
    async def get_profile(self, access_token: str) -> dict[str, str]: ...
