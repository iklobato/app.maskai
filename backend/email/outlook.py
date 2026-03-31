import httpx

from backend.interfaces.email_provider import EmailProvider, EmailMessage
from backend.interfaces.oauth_provider import OAuthProvider


class OutlookProvider(EmailProvider):
    provider_name = "outlook"

    def __init__(self, oauth_provider: OAuthProvider):
        self.oauth = oauth_provider

    def get_scope(self) -> str:
        return "Mail.Read"

    async def list_messages(
        self,
        access_token: str,
        page_token: str | None = None,
        limit: int = 100,
    ) -> tuple[list[EmailMessage], str | None]:
        params: dict = {"$top": "100"}
        if page_token:
            params["$skip"] = page_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            result = response.json()

            messages = result.get("value", [])
            next_token = None
            if "@odata.nextLink" in result:
                next_token = str(messages[-1]["id"] if messages else "")

            email_messages = [
                self._parse_email_message(msg, False) for msg in messages[:limit]
            ]
            return email_messages, next_token

    async def get_message(
        self,
        access_token: str,
        message_id: str,
        include_body: bool = False,
    ) -> EmailMessage:
        params = {}
        if not include_body:
            params["$select"] = "id,subject,from,to,receivedDateTime,snippet,threadId"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_email_message(data, include_body)

    async def get_inbox(
        self,
        access_token: str,
        limit: int = 20,
    ) -> list[EmailMessage]:
        params = {
            "$top": min(limit, 100),
            "$orderby": "receivedDateTime desc",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            result = response.json()
            messages = result.get("value", [])
            return [self._parse_email_message(msg, False) for msg in messages[:limit]]

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

    async def get_emails(
        self, access_token: str, query: str = "", max_results: int = 10
    ) -> list[dict]:
        async with httpx.AsyncClient() as client:
            search_query = query if query else ""
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "$search": search_query,
                    "$top": max_results,
                    "$select": "id,subject,from,receivedDateTime,bodyPreview,threadId",
                    "$orderby": "receivedDateTime desc",
                },
            )
            response.raise_for_status()
            result = response.json()
            emails = []
            for msg in result.get("value", []):
                emails.append(
                    {
                        "id": msg["id"],
                        "thread_id": msg.get("threadId"),
                        "subject": msg.get("subject", ""),
                        "from": msg.get("from", {})
                        .get("emailAddress", {})
                        .get("address", ""),
                        "date": msg.get("receivedDateTime", ""),
                        "snippet": msg.get("bodyPreview", ""),
                    }
                )
            return emails

    async def get_email_body(self, access_token: str, message_id: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"$select": "body"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("body", {}).get("content", "")

    def _parse_email_message(self, msg: dict, include_body: bool) -> EmailMessage:
        from_email = msg.get("from", {}).get("emailAddress", {})
        to_email = msg.get("toRecipients", [{}])
        to_addresses = ", ".join(
            r.get("emailAddress", {}).get("address", "") for r in to_email
        )

        try:
            from datetime import datetime, timezone

            date_str = msg.get("receivedDateTime", "")
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            date = None

        body = None
        if include_body:
            body = msg.get("body", {}).get("content", "")

        return EmailMessage(
            provider_message_id=msg["id"],
            subject=msg.get("subject", ""),
            sender=from_email.get("address", ""),
            recipients=to_addresses,
            date=date,
            snippet=msg.get("bodyPreview", msg.get("snippet", "")),
            thread_id=msg.get("threadId"),
            body=body,
        )
