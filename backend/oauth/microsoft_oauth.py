import httpx

from backend.interfaces.oauth_provider import OAuthProvider


class MicrosoftOAuth(OAuthProvider):
    provider_name = "microsoft"

    def get_auth_url(self, state: str) -> str:
        from backend.config import settings

        return (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            f"?client_id={settings.microsoft_client_id}"
            f"&redirect_uri={settings.microsoft_redirect_uri}"
            f"&response_type=code"
            f"&scope=openid email profile Mail.Read"
            f"&state={state}"
        )

    async def exchange_code(self, code: str) -> dict[str, str]:
        from backend.config import settings

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "code": code,
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "redirect_uri": settings.microsoft_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(self, refresh_token: str) -> dict[str, str]:
        from backend.config import settings

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_profile(self, access_token: str) -> dict[str, str]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return {
                "email": data.get("mail", data.get("userPrincipalName", "")),
                "name": data.get("displayName", ""),
            }
