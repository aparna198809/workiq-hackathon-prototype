"""
Embedding + semantic result cache with version-aware invalidation.

Metadata
--------
Created:   06-JUL-2026
Component: cache.py
Role:      Two-layer cache that eliminates redundant embedding API calls and
           AI Search queries for repeated/similar questions. Uses data versioning
           (not time-based TTL) so cache stays valid until the underlying corpus
           actually changes.

Design
------
Layer 1 — Query Embedding Cache:
    Maps normalized question text -> embedding vector. NEVER expires because
    the same text always produces the same embedding. LRU-evicted at max capacity.

Layer 2 — Semantic Result Cache:
    Maps (query_embedding, persona, data_version) -> search results. Entries
    become stale when data_version changes (new email/meeting/chat ingested).
    Paraphrased questions hit the cache via cosine similarity threshold.
"""

from __future__ import annotations

import hashlib
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# --------------------------------------------------------------------------- #
# LRU Cache base
# --------------------------------------------------------------------------- #

class LRUDict(OrderedDict):
    """OrderedDict with a max capacity; evicts least-recently-used on overflow."""

    def __init__(self, maxsize: int = 10_000) -> None:
        super().__init__()
        self.maxsize = maxsize

    def get_lru(self, key: str) -> Any | None:
        if key in self:
            self.move_to_end(key)
            return self[key]
        return None

    def put_lru(self, key: str, value: Any) -> None:
        if key in self:
            self.move_to_end(key)
        self[key] = value
        while len(self) > self.maxsize:
            self.popitem(last=False)


# --------------------------------------------------------------------------- #
# Layer 1: Query Embedding Cache
# --------------------------------------------------------------------------- #

class EmbeddingCache:
    """Caches embedding vectors keyed by normalized text hash. Never expires."""

    def __init__(self, maxsize: int = 10_000) -> None:
        self._store = LRUDict(maxsize)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

    def get(self, text: str) -> np.ndarray | None:
        vec = self._store.get_lru(self._key(text))
        if vec is not None:
            self.hits += 1
        else:
            self.misses += 1
        return vec

    def put(self, text: str, vector: np.ndarray) -> None:
        self._store.put_lru(self._key(text), vector)

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._store)}


# --------------------------------------------------------------------------- #
# Layer 2: Semantic Result Cache
# --------------------------------------------------------------------------- #

@dataclass
class CacheEntry:
    """A cached search result set, tagged with the data version it was computed against."""
    query_embedding: np.ndarray
    persona_id: str | None
    data_version: str
    results: list[dict]
    timestamp: float = field(default_factory=time.time)


class SemanticResultCache:
    """Caches AI Search results by semantic similarity to previously seen queries.

    A cache hit requires:
      1. Cosine similarity >= threshold (handles paraphrases)
      2. Same persona (ACL-filtered results are persona-specific)
      3. Same data_version (results become stale when data changes)
    """

    def __init__(
        self,
        maxsize: int = 500,
        similarity_threshold: float = 0.88,
    ) -> None:
        self._entries: list[CacheEntry] = []
        self.maxsize = maxsize
        self.similarity_threshold = similarity_threshold
        self.hits = 0
        self.misses = 0

    def get(
        self,
        query_vec: np.ndarray,
        persona_id: str | None,
        data_version: str,
    ) -> list[dict] | None:
        """Find cached results for a semantically similar query with matching persona + version."""
        if not self._entries:
            self.misses += 1
            return None

        q_norm = query_vec / (np.linalg.norm(query_vec) or 1.0)

        for entry in self._entries:
            if entry.persona_id != persona_id:
                continue
            if entry.data_version != data_version:
                continue

            cached_norm = entry.query_embedding / (np.linalg.norm(entry.query_embedding) or 1.0)
            similarity = float(q_norm @ cached_norm)

            if similarity >= self.similarity_threshold:
                self.hits += 1
                return entry.results

        self.misses += 1
        return None

    def put(
        self,
        query_vec: np.ndarray,
        persona_id: str | None,
        data_version: str,
        results: list[dict],
    ) -> None:
        """Store a new cache entry. Evicts oldest when at capacity."""
        self._entries.append(CacheEntry(
            query_embedding=query_vec,
            persona_id=persona_id,
            data_version=data_version,
            results=results,
        ))
        if len(self._entries) > self.maxsize:
            self._entries = self._entries[-self.maxsize:]

    def clear(self) -> None:
        """Clear all cached results (called on data mutation)."""
        self._entries.clear()

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._entries)}


# --------------------------------------------------------------------------- #
# Data Version computation
# --------------------------------------------------------------------------- #

def compute_data_version(
    email_count: int,
    meeting_count: int,
    message_count: int,
    table_row_counts: dict[str, int],
    latest_ids: list[str] | None = None,
) -> str:
    """Compute a lightweight hash representing the current data state.

    Changes when any content is added/removed. Does NOT hash full content —
    only counts + latest ids for speed.
    """
    parts = [
        f"e:{email_count}",
        f"m:{meeting_count}",
        f"t:{message_count}",
    ]
    for table, count in sorted(table_row_counts.items()):
        parts.append(f"{table}:{count}")
    if latest_ids:
        parts.extend(latest_ids[-5:])

    version_str = "|".join(parts)
    return hashlib.md5(version_str.encode()).hexdigest()[:12]
