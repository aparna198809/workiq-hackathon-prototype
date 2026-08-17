"""
Azure AI Search integration for Work IQ simulator.

Metadata
--------
Created:   06-JUL-2026
Component: search_client.py
Role:      Manages the AI Search index (create, push documents, query) using
           AI Search's built-in document cracking + OCR skillset for PDF/image
           attachments. No separate Content Understanding service needed — AI Search
           handles PDF text extraction and OCR natively via its indexer pipeline.

Design
------
- Single index stores both text-native content (emails, meetings, chats) and
  attachment-extracted content (PDFs, images via built-in OCR).
- `content_source` field distinguishes "direct" (text bodies) from "attachment"
  (extracted from PDF/image via AI Search skillset).
- ACL filtering happens server-side via OData $filter on the `acl` collection field.
- Embeddings are computed at ingestion time and stored in the index; at query time
  only the question needs embedding (1 API call, often cached).
- For attachments: text is extracted client-side using basic PDF/text parsing before
  pushing to the index. For production, use AI Search's blob indexer with built-in
  skillset (document cracking + OCR) pointed at your blob storage.

Environment
-----------
  AZURE_SEARCH_ENDPOINT       https://<name>.search.windows.net
  AZURE_SEARCH_INDEX          Index name (default: workiq-docs)
  AZURE_SEARCH_ADMIN_KEY      Admin key (for index creation); omit to use az login
  AZURE_OPENAI_ENDPOINT       For embedding computation
  AZURE_EMBEDDING_DEPLOYMENT  Embedding model deployment (default: text-embedding-ada-002)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX", "workiq-docs")
SEARCH_ADMIN_KEY = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "")
EMBEDDING_DIMENSIONS = 1536  # text-embedding-ada-002

# File extensions that AI Search can crack open (PDF, Office, images for OCR)
ATTACHMENT_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".jpg", ".jpeg", ".png", ".tiff", ".bmp",
}


def is_available() -> bool:
    """True if AI Search is configured."""
    global SEARCH_ENDPOINT, SEARCH_INDEX, SEARCH_ADMIN_KEY
    if not SEARCH_ENDPOINT:
        SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
        SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX", "workiq-docs")
        SEARCH_ADMIN_KEY = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "")
    return bool(SEARCH_ENDPOINT)


def _get_credential():
    """Get Azure credential for API calls."""
    from azure.identity import AzureCliCredential
    return AzureCliCredential()


def _get_search_headers() -> dict[str, str]:
    """Auth headers for AI Search REST calls."""
    if SEARCH_ADMIN_KEY:
        return {"api-key": SEARCH_ADMIN_KEY, "Content-Type": "application/json"}
    credential = _get_credential()
    token = credential.get_token("https://search.azure.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --------------------------------------------------------------------------- #
# Index Management
# --------------------------------------------------------------------------- #

def create_index() -> bool:
    """Create or update the AI Search index. Returns True on success."""
    if not is_available():
        return False

    import httpx

    index_definition = {
        "name": SEARCH_INDEX,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "kind", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "text", "type": "Edm.String", "searchable": True, "analyzer": "standard.lucene"},
            {"name": "title", "type": "Edm.String", "searchable": True},
            {"name": "scenario", "type": "Edm.String", "filterable": True},
            {"name": "content_source", "type": "Edm.String", "filterable": True},
            {"name": "parent_id", "type": "Edm.String", "filterable": True},
            {"name": "source_file", "type": "Edm.String", "filterable": True},
            {"name": "acl", "type": "Collection(Edm.String)", "filterable": True},
            {
                "name": "embedding",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "dimensions": EMBEDDING_DIMENSIONS,
                "vectorSearchProfile": "default-profile",
            },
        ],
        "vectorSearch": {
            "algorithms": [{"name": "default-algo", "kind": "hnsw"}],
            "profiles": [{"name": "default-profile", "algorithm": "default-algo"}],
        },
    }

    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}?api-version=2024-07-01"
    headers = _get_search_headers()

    try:
        resp = httpx.put(url, json=index_definition, headers=headers, timeout=30.0)
        if resp.status_code in (200, 201, 204):
            print(f"[search] Index '{SEARCH_INDEX}' ready", file=sys.stderr)
            return True
        else:
            print(f"[search] Index creation failed ({resp.status_code}): {resp.text[:300]}", file=sys.stderr)
            return False
    except Exception as exc:
        print(f"[search] Index creation error: {exc}", file=sys.stderr)
        return False


# --------------------------------------------------------------------------- #
# Attachment handling — uses AI Search's native capabilities
# --------------------------------------------------------------------------- #

def is_attachment(attachment: Any) -> bool:
    """Check if an attachment is a type AI Search can process (PDF, image, Office).
    Handles both dict format ({"filename": ..., "type": ...}) and string id references."""
    if isinstance(attachment, str):
        # String reference to a file id (e.g. "FILE-001") — not a raw attachment
        return False
    if not isinstance(attachment, dict):
        return False
    filename = attachment.get("filename", "")
    ext = Path(filename).suffix.lower() if filename else ""
    return ext in ATTACHMENT_EXTENSIONS


def extract_attachment_text(attachment: dict) -> str | None:
    """Extract text from an attachment for indexing.

    For the simulator, attachments may carry inline `content` (text already extracted)
    or a `summary` field. In production, you'd point an AI Search blob indexer at your
    storage account and let its built-in document cracking + OCR skillset handle this
    automatically — no client-side extraction needed.
    """
    # Simulator path: attachment has inline content or summary
    content = attachment.get("content") or attachment.get("summary")
    if content:
        return content

    # If there's a blob_url, in production the AI Search indexer would handle this.
    # For the simulator, return None (document won't be indexed from attachment).
    return None


def build_attachment_documents(
    attachments: list[Any],
    parent_id: str,
    parent_acl: list[str],
    scenario_name: str,
) -> list[dict]:
    """Build indexable documents from attachments of an email/message.

    Each attachment that AI Search can handle (PDF, image, Office) gets its text
    extracted and turned into one or more index documents. String references
    (file ids like "FILE-001") are skipped — those are already indexed as files.
    """
    documents = []
    for att in attachments:
        if not is_attachment(att):
            continue

        text = extract_attachment_text(att)
        if not text:
            continue

        filename = att.get("filename", "unknown")
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", filename)

        # Chunk large content into segments (~1500 chars each)
        chunks = _chunk_text(text, max_chars=1500)
        for i, chunk in enumerate(chunks):
            doc_id = f"{parent_id}__att__{safe_name}_c{i+1}"
            documents.append({
                "id": doc_id,
                "kind": "attachment",
                "text": chunk,
                "title": f"{filename} (chunk {i+1})" if len(chunks) > 1 else filename,
                "scenario": scenario_name,
                "content_source": "attachment",
                "parent_id": parent_id,
                "source_file": filename,
                "acl": parent_acl,
            })

    return documents


def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_chars]]


# --------------------------------------------------------------------------- #
# Embedding computation
# --------------------------------------------------------------------------- #

def get_embeddings_batch(texts: list[str]) -> np.ndarray | None:
    """Get embeddings from Azure OpenAI for a batch of texts."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    if not endpoint:
        return None

    import httpx

    base = re.sub(r"/openai/v1$", "", endpoint)
    deploy = os.environ.get("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    api_version = "2024-02-01"
    url = f"{base}/openai/deployments/{deploy}/embeddings?api-version={api_version}"

    try:
        credential = _get_credential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default").token
        resp = httpx.post(
            url,
            json={"input": texts},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=60.0,
        )
        if resp.status_code != 200:
            print(f"[search] Embedding batch failed ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
            return None
        data = resp.json()
        vecs = [item["embedding"] for item in data["data"]]
        return np.array(vecs, dtype=np.float32)
    except Exception as exc:
        print(f"[search] Embedding error: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Document Indexing (push to AI Search)
# --------------------------------------------------------------------------- #

def _upload_documents(documents: list[dict]) -> int:
    """Push documents to AI Search. Returns count of successfully indexed docs."""
    if not documents:
        return 0

    import httpx

    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/index?api-version=2024-07-01"
    headers = _get_search_headers()

    indexed = 0
    # AI Search allows max 1000 docs per batch; use 100 for safety
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        actions = [{"@search.action": "mergeOrUpload", **doc} for doc in batch]
        payload = {"value": actions}

        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
            if resp.status_code in (200, 207):
                results = resp.json().get("value", [])
                indexed += sum(1 for r in results if r.get("status", False))
            else:
                print(f"[search] Upload failed ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
        except Exception as exc:
            print(f"[search] Upload error: {exc}", file=sys.stderr)

    return indexed


def index_documents(documents: list[dict]) -> int:
    """Embed documents and push to AI Search. Returns count indexed."""
    if not is_available() or not documents:
        return 0

    # Compute embeddings in batches of 16
    embed_batch_size = 16
    for i in range(0, len(documents), embed_batch_size):
        batch = documents[i:i + embed_batch_size]
        texts = [doc["text"] for doc in batch]
        embeddings = get_embeddings_batch(texts)
        if embeddings is not None:
            for j, doc in enumerate(batch):
                doc["embedding"] = embeddings[j].tolist()
        else:
            print(f"[search] Embedding failed for batch {i//embed_batch_size}; "
                  f"indexing without vectors (keyword search still works)", file=sys.stderr)

    count = _upload_documents(documents)
    print(f"[search] Indexed {count}/{len(documents)} documents", file=sys.stderr)
    return count


# --------------------------------------------------------------------------- #
# Scenario Indexing — builds documents from scenario fixtures
# --------------------------------------------------------------------------- #

def build_scenario_documents(scenario) -> list[dict]:
    """Build indexable documents from a Scenario object.

    Two paths:
    - Text-native content (email body, meeting recap, chat text) -> direct documents
    - Attachments (PDFs, images) -> AI Search handles OCR/extraction via its skillset;
      for the simulator, we extract inline content and index it separately.

    Both go into the same index with `content_source` = "direct" or "attachment".
    """
    from engine import _kind_for_table  # avoid circular import at module level

    documents: list[dict] = []
    scenario_name = scenario.root.name

    # --- Emails + their attachments ---
    for email in scenario.emails:
        documents.append({
            "id": email["id"],
            "kind": "email",
            "text": f"{email.get('subject', '')} :: {email.get('body', '')}",
            "title": f"Email: {email.get('subject', '')}",
            "scenario": scenario_name,
            "content_source": "direct",
            "parent_id": "",
            "source_file": "",
            "acl": email.get("acl", ["all"]),
        })
        # Attachments: extract text and index separately
        for att in email.get("attachments", []):
            att_docs = build_attachment_documents(
                [att],
                parent_id=email["id"],
                parent_acl=email.get("acl", ["all"]),
                scenario_name=scenario_name,
            )
            documents.extend(att_docs)

    # --- Meetings ---
    for mtg in scenario.meetings:
        documents.append({
            "id": mtg["id"],
            "kind": "meeting",
            "text": f"{mtg.get('title', '')} :: {mtg.get('recap', '')}",
            "title": f"Meeting: {mtg.get('title', '')}",
            "scenario": scenario_name,
            "content_source": "direct",
            "parent_id": "",
            "source_file": "",
            "acl": mtg.get("acl", ["all"]),
        })
        for ai in mtg.get("action_items", []):
            documents.append({
                "id": ai["id"],
                "kind": "action_item",
                "text": (f"Action item ({mtg.get('title', '')}): {ai.get('text', '')} "
                         f"(owner {ai.get('owner', '')}, due {ai.get('due', '')}, "
                         f"{ai.get('status', '')})"),
                "title": f"Action: {ai.get('text', '')[:60]}",
                "scenario": scenario_name,
                "content_source": "direct",
                "parent_id": mtg["id"],
                "source_file": "",
                "acl": ai.get("acl", mtg.get("acl", ["all"])),
            })

    # --- Teams messages + their attachments ---
    for msg in scenario.teams_messages:
        documents.append({
            "id": msg["id"],
            "kind": "teams_message",
            "text": f"{msg.get('channel', '')} :: {msg.get('text', '')}",
            "title": f"Teams ({msg.get('channel', '')}): {msg.get('author', '')}",
            "scenario": scenario_name,
            "content_source": "direct",
            "parent_id": "",
            "source_file": "",
            "acl": msg.get("acl", ["all"]),
        })
        for att in msg.get("attachments", []):
            att_docs = build_attachment_documents(
                [att],
                parent_id=msg["id"],
                parent_acl=msg.get("acl", ["all"]),
                scenario_name=scenario_name,
            )
            documents.extend(att_docs)

    # --- Files ---
    for f in scenario.files:
        documents.append({
            "id": f["id"],
            "kind": "file",
            "text": f"{f.get('name', '')} :: {f.get('summary', '')}",
            "title": f"File: {f.get('name', '')}",
            "scenario": scenario_name,
            "content_source": "direct",
            "parent_id": "",
            "source_file": f.get("name", ""),
            "acl": f.get("acl", ["all"]),
        })

    # --- Table rows ---
    for table, rows in scenario.tables.items():
        kind = _kind_for_table(table)
        for row in rows:
            rid = row.get("id")
            if not rid:
                continue
            fields_text = ", ".join(f"{k}: {v}" for k, v in row.items() if k != "acl")
            label = (row.get("milestone") or row.get("title") or
                     row.get("name") or row.get("action") or rid)
            documents.append({
                "id": rid,
                "kind": kind,
                "text": f"{kind.title()} record :: {fields_text}",
                "title": f"{kind.title()}: {label}",
                "scenario": scenario_name,
                "content_source": "direct",
                "parent_id": "",
                "source_file": "",
                "acl": row.get("acl", ["all"]),
            })

    # --- People ---
    for person in scenario.people:
        documents.append({
            "id": person["id"],
            "kind": "person",
            "text": (f"{person.get('name', '')} :: {person.get('title', '')} :: "
                     f"{', '.join(person.get('expertise', []))}"),
            "title": f"{person.get('name', '')} — {person.get('title', '')}",
            "scenario": scenario_name,
            "content_source": "direct",
            "parent_id": "",
            "source_file": "",
            "acl": person.get("acl", ["all"]),
        })

    return documents


def index_scenario(scenario) -> int:
    """Full pipeline: build documents from scenario -> embed -> push to AI Search."""
    if not is_available():
        print("[search] AI Search not configured (set AZURE_SEARCH_ENDPOINT); skipping", file=sys.stderr)
        return 0

    create_index()
    documents = build_scenario_documents(scenario)
    return index_documents(documents)


# --------------------------------------------------------------------------- #
# Query — hybrid vector + keyword search with ACL filtering
# --------------------------------------------------------------------------- #

def search(
    query_embedding: np.ndarray | None,
    question: str,
    persona_id: str | None,
    scenario_name: str,
    k: int = 6,
) -> list[dict]:
    """Query AI Search with hybrid (vector + keyword) and server-side ACL filtering.

    Returns: [{"id": ..., "text": ..., "kind": ..., "score": ...}, ...]
    """
    if not is_available():
        return []

    import httpx

    # Build ACL filter: persona sees docs where acl contains "all" OR their id
    filters = [f"scenario eq '{scenario_name}'"]
    if persona_id:
        filters.append(f"(acl/any(a: a eq 'all') or acl/any(a: a eq '{persona_id}'))")
    filter_str = " and ".join(filters)

    search_body: dict[str, Any] = {
        "search": question,
        "filter": filter_str,
        "top": k,
        "select": "id,text,kind,title,content_source,parent_id,source_file",
    }

    # Add vector query if embedding is available
    if query_embedding is not None:
        vec = query_embedding.tolist() if isinstance(query_embedding, np.ndarray) else query_embedding
        search_body["vectorQueries"] = [{
            "kind": "vector",
            "vector": vec,
            "fields": "embedding",
            "k": k,
        }]

    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version=2024-07-01"
    headers = _get_search_headers()

    try:
        resp = httpx.post(url, json=search_body, headers=headers, timeout=15.0)
        if resp.status_code != 200:
            print(f"[search] Query failed ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
            return []

        results = resp.json().get("value", [])
        return [
            {
                "id": r["id"],
                "text": r.get("text", ""),
                "kind": r.get("kind", ""),
                "title": r.get("title", ""),
                "content_source": r.get("content_source", "direct"),
                "parent_id": r.get("parent_id", ""),
                "source_file": r.get("source_file", ""),
                "score": r.get("@search.score", 0.0),
            }
            for r in results
        ]
    except Exception as exc:
        print(f"[search] Query error: {exc}", file=sys.stderr)
        return []


# --------------------------------------------------------------------------- #
# Incremental indexing — for new content arriving at runtime
# --------------------------------------------------------------------------- #

def index_single_document(doc: dict) -> bool:
    """Index a single new document (e.g., when a new email arrives or create_entity runs)."""
    if not is_available():
        return False

    embedding = get_embeddings_batch([doc["text"]])
    if embedding is not None:
        doc["embedding"] = embedding[0].tolist()

    import httpx
    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/index?api-version=2024-07-01"
    headers = _get_search_headers()
    payload = {"value": [{"@search.action": "mergeOrUpload", **doc}]}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15.0)
        return resp.status_code in (200, 207)
    except Exception:
        return False


def index_new_email(email: dict, scenario_name: str) -> int:
    """Index a newly arrived email + its attachments. Called by the ingestion pipeline."""
    documents = []

    # Index the email body (direct)
    documents.append({
        "id": email["id"],
        "kind": "email",
        "text": f"{email.get('subject', '')} :: {email.get('body', '')}",
        "title": f"Email: {email.get('subject', '')}",
        "scenario": scenario_name,
        "content_source": "direct",
        "parent_id": "",
        "source_file": "",
        "acl": email.get("acl", ["all"]),
    })

    # Index attachments (AI Search handles PDF/OCR via its built-in skillset;
    # here we extract what we can client-side for the simulator)
    for att in email.get("attachments", []):
        att_docs = build_attachment_documents(
            [att],
            parent_id=email["id"],
            parent_acl=email.get("acl", ["all"]),
            scenario_name=scenario_name,
        )
        documents.extend(att_docs)

    return index_documents(documents)
