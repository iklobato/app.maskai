from backend.email.gmail import GmailProvider
from backend.email.outlook import OutlookProvider
from backend.oauth import PROVIDERS as OAUTH_PROVIDERS

PROVIDERS: dict[str, GmailProvider | OutlookProvider] = {
    "gmail": GmailProvider(oauth_provider=OAUTH_PROVIDERS["google"]),
    "outlook": OutlookProvider(oauth_provider=OAUTH_PROVIDERS["microsoft"]),
}


def get_provider(name: str) -> GmailProvider | OutlookProvider | None:
    return PROVIDERS.get(name)
