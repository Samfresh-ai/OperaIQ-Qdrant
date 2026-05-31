from __future__ import annotations

from abc import ABC, abstractmethod
import math


class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per input text."""


class FastEmbedEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "fastembed is not installed. Run `uv sync` before starting the app."
            ) from exc

        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.embed(texts)
        return [[float(value) for value in vector] for vector in vectors]


class KeywordEmbedder(Embedder):
    """Small deterministic embedder for tests; app runtime uses FastEmbed."""

    vocabulary = [
        "redis",
        "econnreset",
        "connection",
        "pool",
        "queue",
        "backlog",
        "worker",
        "auth",
        "token",
        "expiry",
        "database",
        "db",
        "payment",
        "webhook",
        "retry",
        "latency",
        "timeout",
        "checkout",
        "verify",
    ]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        lowered = text.lower()
        vector = [float(lowered.count(token)) for token in self.vocabulary]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return [0.0 for _ in self.vocabulary]
        return [value / norm for value in vector]

