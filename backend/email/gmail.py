import base64
from datetime import datetime

import httpx

from backend.interfaces.email_provider import EmailProvider, EmailMessage
from backend.interfaces.oauth_provider import OAuthProvider


class GmailProvider(EmailProvider):
    provider_name = "gmail"

    def __init__(self, oauth_provider: OAuthProvider):
        self.oauth = oauth_provider

    def get_scope(self) -> str:
        return "https://www.googleapis.com/auth/gmail.readonly"

    async def list_messages(
        self,
        access_token: str,
        page_token: str | None = None,
        limit: int = 100,
    ) -> tuple[list[EmailMessage], str | None]:
        params = {"maxResults": 100}
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            response.raise_for_status()
            result = response.json()

            messages = result.get("messages", [])
            next_token = result.get("nextPageToken")

            email_messages = []
            for msg in messages[:limit]:
                msg_data = await self._get_message_metadata(access_token, msg["id"])
                if msg_data:
                    email_messages.append(msg_data)

            return email_messages, next_token

    async def get_message(
        self,
        access_token: str,
        message_id: str,
        include_body: bool = False,
    ) -> EmailMessage:
        async with httpx.AsyncClient() as client:
            format_type = "full" if include_body else "metadata"
            response = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": format_type},
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_email_message(data, include_body)

    async def get_inbox(
        self,
        access_token: str,
        limit: int = 20,
    ) -> list[EmailMessage]:
        return await self._search_emails(access_token, "in:inbox", limit)

    async def get_profile(self, access_token: str) -> dict[str, str]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return {
                "email": data.get("email", ""),
                "name": data.get("name", ""),
            }

    async def get_emails(
        self, access_token: str, query: str = "", max_results: int = 10
    ) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": query, "maxResults": max_results},
            )
            response.raise_for_status()
            result = response.json()
            messages = result.get("messages", [])
            emails = []
            for msg in messages:
                msg_response = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "format": "metadata",
                        "metadataHeaders": ["Subject", "From", "Date"],
                    },
                )
                msg_response.raise_for_status()
                msg_data = msg_response.json()
                payload = msg_data.get("payload", {})
                headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
                emails.append(
                    {
                        "id": msg_data["id"],
                        "thread_id": msg_data.get("threadId"),
                        "subject": headers.get("Subject", ""),
                        "from": headers.get("From", ""),
                        "date": headers.get("Date", ""),
                        "snippet": msg_data.get("snippet", ""),
                    }
                )
            return emails

    async def get_email_body(self, access_token: str, message_id: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "full"},
            )
            response.raise_for_status()
            data = response.json()
            payload = data.get("payload", {})
            body = self._extract_body(payload)
            return body or data.get("snippet", "")

    async def _search_emails(
        self, access_token: str, query: str, limit: int
    ) -> list[EmailMessage]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": query, "maxResults": min(limit, 100)},
            )
            response.raise_for_status()
            result = response.json()
            messages = result.get("messages", [])
            email_messages = []
            for msg in messages[:limit]:
                msg_data = await self._get_message_metadata(access_token, msg["id"])
                if msg_data:
                    email_messages.append(msg_data)
            return email_messages

    async def _get_message_metadata(
        self, access_token: str, message_id: str
    ) -> EmailMessage | None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "format": "metadata",
                        "metadataHeaders": ["Subject", "From", "To", "Date"],
                    },
                )
                response.raise_for_status()
                data = response.json()
                return self._parse_email_message(data, False)
            except Exception:
                return None

    def _parse_email_message(self, data: dict, include_body: bool) -> EmailMessage:
        payload = data.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        subject = headers.get("subject", "")
        sender = headers.get("from", "")
        recipients = headers.get("to", "")
        date_str = headers.get("date", "")

        try:
            from email.utils import parsedate_to_datetime

            date = parsedate_to_datetime(date_str)
        except Exception:
            date = None

        body = None
        if include_body:
            body = self._extract_body(payload)

        return EmailMessage(
            provider_message_id=data["id"],
            subject=subject,
            sender=sender,
            recipients=recipients,
            date=date,
            snippet=data.get("snippet", ""),
            thread_id=data.get("threadId"),
            body=body,
        )

    def _extract_body(self, payload: dict) -> str:
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    return self._decode_body(part.get("body", {}).get("data", ""))
                if "parts" in part:
                    body = self._extract_body(part)
                    if body:
                        return body
        elif payload.get("body", {}).get("data"):
            return self._decode_body(payload["body"]["data"])
        return ""

    def _decode_body(self, data: str) -> str:
        if not data:
            return ""
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        except Exception:
            return data
