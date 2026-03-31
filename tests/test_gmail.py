import pytest


@pytest.mark.asyncio
async def test_gmail_provider_interface():
    from backend.email.gmail import GmailProvider
    from backend.oauth import PROVIDERS as OAUTH_PROVIDERS

    provider = GmailProvider(oauth_provider=OAUTH_PROVIDERS["google"])
    assert provider.provider_name == "gmail"
    assert "gmail" in provider.get_scope()


@pytest.mark.asyncio
async def test_outlook_provider_interface():
    from backend.email.outlook import OutlookProvider
    from backend.oauth import PROVIDERS as OAUTH_PROVIDERS

    provider = OutlookProvider(oauth_provider=OAUTH_PROVIDERS["microsoft"])
    assert provider.provider_name == "outlook"
    assert "Mail.Read" in provider.get_scope()
