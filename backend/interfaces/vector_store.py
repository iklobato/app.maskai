from abc import ABC, abstractmethod


class VectorStore(ABC):
    collection_name: str

    @abstractmethod
    async def create_collection(self) -> None: ...

    @abstractmethod
    async def insert(self, id: str, embedding: list[float], metadata: dict) -> None: ...

    @abstractmethod
    async def search(
        self, query_embedding: list[float], limit: int = 5, filters: dict | None = None
    ) -> list[dict]: ...

    @abstractmethod
    async def delete(self, id: str) -> None: ...
