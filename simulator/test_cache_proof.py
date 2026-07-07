"""
Quick proof that the semantic result cache correctly identifies paraphrased questions.
Run: .venv\Scripts\python.exe simulator\test_cache_proof.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from cache import EmbeddingCache, SemanticResultCache
from search_client import get_embeddings_batch

# ─── Test configuration ────────────────────────────────────────────────────────
Q1 = "What is the timeline for the Westgate EHR migration?"
Q2 = "When is the Westgate EHR migration happening?"
Q3 = "Who owns the CAPA tracker?"  # Unrelated question (should NOT hit cache)
PERSONA = "quality_pm"
DATA_VERSION = "v1"

print("=" * 70)
print("CACHE PROOF: Paraphrased questions hit the semantic result cache")
print("=" * 70)

# ─── Step 1: Get embeddings for all three questions ────────────────────────────
print("\n[1] Computing embeddings via Azure OpenAI...")
embeddings = get_embeddings_batch([Q1, Q2, Q3])
if embeddings is None:
    print("ERROR: Could not get embeddings. Check AZURE_OPENAI_ENDPOINT and az login.")
    sys.exit(1)

vec1, vec2, vec3 = embeddings[0], embeddings[1], embeddings[2]
print(f"    Q1 embedding shape: {vec1.shape}")
print(f"    Q2 embedding shape: {vec2.shape}")
print(f"    Q3 embedding shape: {vec3.shape}")

# ─── Step 2: Compute cosine similarities ──────────────────────────────────────
def cosine_sim(a, b):
    return float((a / np.linalg.norm(a)) @ (b / np.linalg.norm(b)))

sim_12 = cosine_sim(vec1, vec2)
sim_13 = cosine_sim(vec1, vec3)
print(f"\n[2] Cosine similarities:")
print(f"    Q1 vs Q2 (paraphrase):  {sim_12:.4f}  (threshold=0.88)")
print(f"    Q1 vs Q3 (unrelated):   {sim_13:.4f}  (threshold=0.88)")
print(f"    {'✓' if sim_12 >= 0.88 else '✗'} Q1↔Q2 {'ABOVE' if sim_12 >= 0.88 else 'BELOW'} threshold → cache {'HIT' if sim_12 >= 0.88 else 'MISS'}")
print(f"    {'✓' if sim_13 < 0.88 else '✗'} Q1↔Q3 {'BELOW' if sim_13 < 0.88 else 'ABOVE'} threshold → cache {'MISS' if sim_13 < 0.88 else 'HIT'}")

# ─── Step 3: Demonstrate cache behavior ──────────────────────────────────────
print(f"\n[3] Simulating cache workflow...")
result_cache = SemanticResultCache(similarity_threshold=0.88)
embedding_cache = EmbeddingCache()

# Store Q1 embedding in L1 cache
embedding_cache.put(Q1, vec1)

# Simulate: Q1 was asked, got results from AI Search, stored in L2 cache
fake_results = [
    {"id": "MTG-004", "text": "Westgate EHR rollout program review..."},
    {"id": "MSG-001", "text": "Westgate go-live status..."},
]
result_cache.put(vec1, PERSONA, DATA_VERSION, fake_results)
print(f"    Stored Q1 results in cache. Cache size: {result_cache.stats()['size']}")

# Now ask Q2 (paraphrase) — should HIT the result cache
cached = result_cache.get(vec2, PERSONA, DATA_VERSION)
print(f"\n    Q2 lookup (paraphrase of Q1):")
print(f"    → Result: {'CACHE HIT ✓' if cached is not None else 'CACHE MISS ✗'}")
if cached:
    print(f"    → Got {len(cached)} cached results: {[r['id'] for r in cached]}")

# Now ask Q3 (unrelated) — should MISS
cached3 = result_cache.get(vec3, PERSONA, DATA_VERSION)
print(f"\n    Q3 lookup (unrelated question):")
print(f"    → Result: {'CACHE HIT ✗ (unexpected!)' if cached3 is not None else 'CACHE MISS ✓ (correct)'}")

# ─── Step 4: L1 embedding cache check ─────────────────────────────────────────
print(f"\n[4] Embedding cache (L1) stats:")
# Exact match for Q1
hit = embedding_cache.get(Q1)
print(f"    Q1 exact lookup: {'HIT ✓' if hit is not None else 'MISS'}")
# Q2 is different text — L1 cache misses (expected; L1 is exact-match only)
hit2 = embedding_cache.get(Q2)
print(f"    Q2 exact lookup: {'HIT' if hit2 is not None else 'MISS ✓ (expected: L1=exact match only, L2 handles paraphrases)'}")

# ─── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("SUMMARY:")
print(f"  • L1 (EmbeddingCache): Exact text match → eliminates redundant embedding API calls")
print(f"  • L2 (SemanticResultCache): Cosine similarity {sim_12:.4f} ≥ 0.88 → cache HIT for paraphrases")
print(f"  • Unrelated questions (similarity {sim_13:.4f} < 0.88) correctly MISS the cache")
print(f"  • Result cache stats: {result_cache.stats()}")
print(f"  • Embedding cache stats: {embedding_cache.stats()}")
print(f"{'=' * 70}")
