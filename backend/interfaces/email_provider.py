from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailMessage:
    provider_message_id: str
    subject: str
    sender: str
    recipients: str
    date: datetime | None = None
    snippet: str = ""
    thread_id: str | None = None
    labels: list[str] = field(default_factory=list)
    body: str | None = None


class EmailProvider(ABC):
    provider_name: str

    @abstractmethod
    async def list_messages(
        self,
        access_token: str,
        page_token: str | None = None,
        limit: int = 100,
    ) -> tuple[list[EmailMessage], str | None]: ...

    @abstractmethod
    async def get_message(
        self,
        access_token: str,
        message_id: str,
        include_body: bool = False,
    ) -> EmailMessage: ...

    @abstractmethod
    async def get_inbox(
        self,
        access_token: str,
        limit: int = 20,
    ) -> list[EmailMessage]: ...

    @abstractmethod
    async def get_profile(self, access_token: str) -> dict[str, str]: ...
