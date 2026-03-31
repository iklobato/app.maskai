import httpx

from backend.interfaces.oauth_provider import OAuthProvider


class GoogleOAuth(OAuthProvider):
    provider_name = "google"

    def get_auth_url(self, state: str) -> str:
        from backend.config import settings

        return (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={settings.google_client_id}"
            f"&redirect_uri={settings.google_redirect_uri}"
            f"&response_type=code"
            f"&scope=openid email profile https://www.googleapis.com/auth/gmail.readonly"
            f"&access_type=offline"
            f"&prompt=consent"
            f"&state={state}"
        )

    async def exchange_code(self, code: str) -> dict[str, str]:
        from backend.config import settings

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(self, refresh_token: str) -> dict[str, str]:
        from backend.config import settings

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_profile(self, access_token: str) -> dict[str, str]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return {"email": data["email"], "name": data.get("name", "")}
