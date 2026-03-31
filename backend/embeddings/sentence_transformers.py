from backend.interfaces.embedding_model import EmbeddingModel
from backend.config import settings

MODEL_DIMENSIONS = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "multi-qa-MiniLM-L6-cos-v1": 384,
}


class SentenceTransformersEmbedding(EmbeddingModel):
    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name or settings.embedding_model
        self._model = SentenceTransformer(self._model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return MODEL_DIMENSIONS.get(self._model_name, 384)

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    def encode_query(self, query: str) -> list[float]:
        embedding = self._model.encode(query, convert_to_numpy=True)
        return embedding.tolist()


EMBEDDING_IMPLEMENTATIONS = {
    "sentence-transformers": SentenceTransformersEmbedding,
}
