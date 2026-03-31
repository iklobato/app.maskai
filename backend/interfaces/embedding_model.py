from abc import ABC, abstractmethod
from typing import Any


class EmbeddingModel(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    def encode(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def encode_query(self, query: str) -> list[float]: ...
