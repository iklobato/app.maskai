from backend.interfaces.oauth_provider import OAuthProvider
from backend.oauth.google_oauth import GoogleOAuth
from backend.oauth.microsoft_oauth import MicrosoftOAuth

PROVIDERS: dict[str, OAuthProvider] = {
    "google": GoogleOAuth(),
    "microsoft": MicrosoftOAuth(),
}


def get_provider(name: str) -> OAuthProvider | None:
    return PROVIDERS.get(name)


__all__ = ["OAuthProvider", "PROVIDERS", "get_provider"]
