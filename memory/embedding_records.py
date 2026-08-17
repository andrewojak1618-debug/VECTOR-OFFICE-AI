"""Represent stored embeddings and encode compact float32 vector blobs."""

import struct
from dataclasses import dataclass

from memory.embedding_types import EmbeddingResult, EmbeddingVector
from memory.models import KnowledgeChunk


@dataclass(frozen=True)
class ChunkEmbedding:
    """Associate one generated embedding with its source chunk identifier."""

    chunk_id: int
    result: EmbeddingResult


@dataclass(frozen=True)
class StoredEmbedding:
    """Represent one versioned embedding restored from local SQLite."""

    id: int
    chunk_id: int
    model_name: str
    model_version: str
    dimension: int
    content_hash: str
    vector: EmbeddingVector
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class EmbeddedKnowledgeChunk:
    """Pair a sourced document section with its current local vector."""

    chunk: KnowledgeChunk
    vector: EmbeddingVector


class Float32VectorCodec:
    """Serialize numeric vectors as compact little-endian float32 blobs."""

    BYTES_PER_VALUE = 4

    @classmethod
    def encode(cls, vector: EmbeddingVector) -> bytes:
        """Encode one validated vector into a compact SQLite BLOB."""
        try:
            return struct.pack(f"<{vector.dimension}f", *vector.values)
        except (OverflowError, struct.error) as exc:
            raise ValueError(
                "Embedding vector cannot be encoded as float32."
            ) from exc

    @classmethod
    def decode(cls, payload: bytes, dimension: int) -> EmbeddingVector:
        """Decode a BLOB and verify its stored vector dimension."""
        expected_bytes = dimension * cls.BYTES_PER_VALUE
        if dimension < 1 or len(payload) != expected_bytes:
            raise ValueError("Stored embedding vector has an invalid size.")
        values = struct.unpack(f"<{dimension}f", payload)
        return EmbeddingVector(values)
