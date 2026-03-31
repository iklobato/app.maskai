import json
from uuid import uuid4

from backend.interfaces.vector_store import VectorStore
from backend.database import SessionLocal, VectorEmbedding


class PGVectorStore(VectorStore):
    collection_name = "email_embeddings"

    def __init__(self):
        from backend.config import settings

        self.database_url = settings.database_url
        self._session_factory = SessionLocal

    async def create_collection(self) -> None:
        pass

    async def insert(self, id: str, embedding: list[float], metadata: dict) -> None:
        db = self._session_factory()
        try:
            vector = VectorEmbedding(
                id=id,
                account_id=metadata.get("account_id", ""),
                message_id=metadata.get("message_id", ""),
                content_hash=metadata.get("content_hash", ""),
                embedding_vector=embedding,
                metadata_json=json.dumps(metadata),
            )
            db.add(vector)
            db.commit()
        finally:
            db.close()

    async def search(
        self, query_embedding: list[float], limit: int = 5, filters: dict | None = None
    ) -> list[dict]:
        db = self._session_factory()
        try:
            query = db.query(VectorEmbedding)
            if filters:
                if "account_id" in filters:
                    query = query.filter(
                        VectorEmbedding.account_id == filters["account_id"]
                    )
                if "message_id" in filters:
                    query = query.filter(
                        VectorEmbedding.message_id == filters["message_id"]
                    )
            vectors = query.limit(limit).all()
            results = []
            for v in vectors:
                embedding_list = v.embedding_vector
                if isinstance(embedding_list, str):
                    embedding_list = json.loads(embedding_list)
                similarity = self._cosine_similarity(query_embedding, embedding_list)
                metadata = json.loads(v.metadata_json) if v.metadata_json else {}
                results.append(
                    {
                        "id": v.id,
                        "score": similarity,
                        "metadata": metadata,
                    }
                )
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
        finally:
            db.close()

    async def delete(self, id: str) -> None:
        db = self._session_factory()
        try:
            vector = db.query(VectorEmbedding).filter(VectorEmbedding.id == id).first()
            if vector:
                db.delete(vector)
                db.commit()
        finally:
            db.close()

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class SQLiteVectorStore(VectorStore):
    collection_name = "email_embeddings"

    def __init__(self):
        from backend.config import settings

        self.database_url = settings.database_url
        self._session_factory = SessionLocal

    async def create_collection(self) -> None:
        pass

    async def insert(self, id: str, embedding: list[float], metadata: dict) -> None:
        db = self._session_factory()
        try:
            vector = VectorEmbedding(
                id=id,
                account_id=metadata.get("account_id", ""),
                message_id=metadata.get("message_id", ""),
                content_hash=metadata.get("content_hash", ""),
                embedding_vector=embedding,
                metadata_json=json.dumps(metadata),
            )
            db.add(vector)
            db.commit()
        finally:
            db.close()

    async def search(
        self, query_embedding: list[float], limit: int = 5, filters: dict | None = None
    ) -> list[dict]:
        db = self._session_factory()
        try:
            query = db.query(VectorEmbedding)
            if filters:
                if "account_id" in filters:
                    query = query.filter(
                        VectorEmbedding.account_id == filters["account_id"]
                    )
                if "message_id" in filters:
                    query = query.filter(
                        VectorEmbedding.message_id == filters["message_id"]
                    )
            vectors = query.limit(limit * 10).all()
            scored = []
            for v in vectors:
                embedding_list = v.embedding_vector
                if isinstance(embedding_list, str):
                    embedding_list = json.loads(embedding_list)
                similarity = self._cosine_similarity(query_embedding, embedding_list)
                metadata = json.loads(v.metadata_json) if v.metadata_json else {}
                scored.append(
                    {
                        "id": v.id,
                        "score": similarity,
                        "metadata": metadata,
                    }
                )
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:limit]
        finally:
            db.close()

    async def delete(self, id: str) -> None:
        db = self._session_factory()
        try:
            vector = db.query(VectorEmbedding).filter(VectorEmbedding.id == id).first()
            if vector:
                db.delete(vector)
                db.commit()
        finally:
            db.close()

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


VECTOR_STORES = {
    "pgvector": PGVectorStore,
    "sqlite": SQLiteVectorStore,
}
