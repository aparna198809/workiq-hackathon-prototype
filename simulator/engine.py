"""
Local Work IQ Simulator — retrieval + synthesis engine (scenario C2: Contoso Precision Parts / 45621-B).

Metadata
--------
Created:        14-JUN-2026 (authoring date)
Component:      engine.py
Role:           Loads synthetic fixtures, answers compound questions via golden-answer
                keyword matching (works with NO model) with an optional LLM fallback,
                applies persona-based permission trimming, resolves citations, and backs
                the Tools surface (fetch / create_entity / update_entity) against the
                Dataverse-style milestone tracker.

Design
------
- The MCP *contract* is identical to the real Work IQ server; only the backend differs.
- Golden answers guarantee deterministic, citable responses for the 8 scripted C1
  questions even when no model is configured. LLM fallback (OpenAI-compatible env vars)
  handles ad-hoc questions.
- Permission model: every fixture carries an `acl` (list of persona ids, or ["all"]).
  A persona sees a fixture iff its id is in the acl OR the acl contains "all".
  Restricted citations that get trimmed produce a governance note (the RBAC demo).
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np

import cache as _cache
import search_client as _search


# --------------------------------------------------------------------------- #
# CDC: Change Data Capture events emitted by the file watcher
# --------------------------------------------------------------------------- #

@dataclass
class ChangeEvent:
    """Represents a detected change in scenario data files."""
    file: str                         # e.g. "meetings.json", "teams.json"
    kind: Literal["new", "modified"]
    added_ids: list[str] = field(default_factory=list)
    modified_ids: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


# Module-level queue consumed by the reconciliation agent
change_queue: deque[ChangeEvent] = deque(maxlen=200)

# Snapshot of record IDs per fixture file, used to diff on change
_last_snapshot: dict[str, dict[str, set[str]]] = {}  # scenario_key -> {file -> set of ids}


# --------------------------------------------------------------------------- #
# Fixture loading
# --------------------------------------------------------------------------- #

# Maps a fixture file (relative to the scenario dir) to the top-level list key inside it.
# Tools-backed tables are NOT listed here — they are discovered dynamically from the
# scenario's `tables/` folder so new scenarios (C2..C6) need zero engine changes.
FIXTURE_FILES: dict[str, str] = {
    "people.json": "people",
    "emails.json": "emails",
    "meetings.json": "meetings",
    "teams.json": "teams_messages",
    "files.json": "files",
    "personas.json": "personas",
    "golden.json": "golden",
}

# Sub-folder (relative to a scenario root) holding the editable Tools tables.
TABLES_DIR = "tables"


# --------------------------------------------------------------------------- #
# Caching layer
# --------------------------------------------------------------------------- #

# Global cache instances — initialized once, shared across requests.
_embedding_cache = _cache.EmbeddingCache(maxsize=10_000)
_result_cache = _cache.SemanticResultCache(maxsize=500, similarity_threshold=0.88)


def _data_version(sc: "Scenario") -> str:
    """Compute the current data version for cache invalidation."""
    table_counts = {t: len(rows) for t, rows in sc.tables.items()}
    latest_ids: list[str] = []
    if sc.emails:
        latest_ids.append(sc.emails[-1].get("id", ""))
    if sc.meetings:
        latest_ids.append(sc.meetings[-1].get("id", ""))
    if sc.teams_messages:
        latest_ids.append(sc.teams_messages[-1].get("id", ""))
    return _cache.compute_data_version(
        email_count=len(sc.emails),
        meeting_count=len(sc.meetings),
        message_count=len(sc.teams_messages),
        table_row_counts=table_counts,
        latest_ids=latest_ids,
    )


@dataclass
class Scenario:
    """In-memory representation of a loaded scenario."""

    root: Path
    people: list[dict] = field(default_factory=list)
    emails: list[dict] = field(default_factory=list)
    meetings: list[dict] = field(default_factory=list)
    teams_messages: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    personas: list[dict] = field(default_factory=list)
    golden: list[dict] = field(default_factory=list)
    # Tools-backed tables, keyed by file stem (e.g. "milestone_tracker", "capa_tracker").
    tables: dict[str, list[dict]] = field(default_factory=dict)
    # Original on-disk shape per table ("dict" or "list") so persistence round-trips faithfully.
    table_formats: dict[str, str] = field(default_factory=dict)

    # id -> (kind, record) for every citable entity (including action items).
    index: dict[str, tuple[str, dict]] = field(default_factory=dict)

    def persona_ids(self) -> list[str]:
        return [p["id"] for p in self.personas]

    def table_names(self) -> list[str]:
        return list(self.tables.keys())

    def get_persona(self, persona_id: str | None) -> dict | None:
        if persona_id is None:
            return None
        for p in self.personas:
            if p["id"] == persona_id:
                return p
        return None


def _kind_for_table(table: str) -> str:
    """Singular citation 'kind' for a table (milestone_tracker -> milestone)."""
    for suffix in ("_tracker", "_table", "_log", "_pipeline"):
        if table.endswith(suffix):
            return table[: -len(suffix)]
    return table


def _prefix_for_table(rows: list[dict], table: str) -> str:
    """Derive an id prefix from existing row ids (e.g. 'MS-001' -> 'MS', 'CAPA-007' ->
    'CAPA'); fall back to the uppercased table initials."""
    for row in rows:
        rid = row.get("id")
        if isinstance(rid, str) and "-" in rid:
            head = rid.rsplit("-", 1)[0]
            if head:
                return head
    return "".join(w[0] for w in table.split("_") if w).upper() or "ROW"


def load_scenario(scenario_dir: str | Path) -> Scenario:
    """Load every fixture file and build the citation index."""
    root = Path(scenario_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Scenario directory not found: {root}")

    sc = Scenario(root=root)
    for rel, key in FIXTURE_FILES.items():
        path = root / rel
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        setattr(sc, key, data.get(key, []))

    # Discover Tools tables: every JSON file under tables/, keyed by its stem. Each file
    # is either {"<stem>": [...]} or a bare list.
    tables_path = root / TABLES_DIR
    if tables_path.is_dir():
        for tf in sorted(tables_path.glob("*.json")):
            with open(tf, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            stem = tf.stem
            if isinstance(data, dict):
                sc.table_formats[stem] = "dict"
                rows = data.get(stem)
                if rows is None:
                    # Author used a different inner key than the file stem. Fall back to
                    # the first list-valued key so the data isn't silently dropped, and warn.
                    list_keys = [k for k, v in data.items()
                                 if k != "_comment" and isinstance(v, list)]
                    if list_keys:
                        sys.stderr.write(
                            f"[workiq-sim] WARNING: table '{tf.name}' has no '{stem}' key; "
                            f"using '{list_keys[0]}' instead.\n"
                        )
                        rows = data[list_keys[0]]
                    else:
                        sys.stderr.write(
                            f"[workiq-sim] WARNING: table '{tf.name}' has no list rows; "
                            f"registering it empty.\n"
                        )
                        rows = []
            else:
                sc.table_formats[stem] = "list"
                rows = data
            sc.tables[stem] = rows or []

    _build_index(sc)

    # Sync AI Search index with the current scenario data on every load.
    # This ensures that any changes to the JSON files (new emails, messages, etc.)
    # are reflected in AI Search when the server restarts.
    if _search.is_available():
        count = _search.index_scenario(sc)
        print(f"[engine] AI Search synced: {count} documents indexed from {root.name}", file=sys.stderr)

    # Start background file watcher to auto-re-index when JSON files change.
    _start_file_watcher(sc)

    return sc


# --------------------------------------------------------------------------- #
# File watcher — auto-re-index on JSON changes (no restart needed)
# --------------------------------------------------------------------------- #

_watcher_started: set[str] = set()  # track which scenario dirs already have a watcher


def _start_file_watcher(sc: Scenario) -> None:
    """Start a background thread that watches the scenario JSON files for changes.
    When any file is modified, it reloads the scenario in-place, emits CDC events,
    and re-indexes AI Search (if available)."""
    import threading

    scenario_key = str(sc.root)
    if scenario_key in _watcher_started:
        return  # already watching this dir

    _watcher_started.add(scenario_key)

    # Take initial snapshot of all record IDs for diffing
    _take_snapshot(sc)

    def _watch(scenario: Scenario) -> None:
        """Poll for file modifications and re-index when detected."""
        import time as _time

        watch_dir = scenario.root
        # Collect initial modification times
        last_mtimes: dict[str, float] = {}
        for f in watch_dir.rglob("*.json"):
            last_mtimes[str(f)] = f.stat().st_mtime

        while True:
            _time.sleep(5)  # check every 5 seconds
            changed = False
            current_files = list(watch_dir.rglob("*.json"))

            for f in current_files:
                path_str = str(f)
                mtime = f.stat().st_mtime
                if path_str not in last_mtimes or last_mtimes[path_str] < mtime:
                    changed = True
                    last_mtimes[path_str] = mtime

            # Detect new files
            if len(current_files) != len(last_mtimes):
                changed = True
                last_mtimes.clear()
                for f in current_files:
                    last_mtimes[str(f)] = f.stat().st_mtime

            if changed:
                print(f"[engine] JSON change detected in {watch_dir.name}, re-indexing...", file=sys.stderr)
                try:
                    # Capture old snapshot before reload
                    old_snap = _last_snapshot.get(str(scenario.root), {})
                    _reload_scenario_inplace(scenario)
                    _result_cache.clear()
                    # Emit CDC events by diffing old vs new
                    _emit_change_events(scenario, old_snap)
                    if _search.is_available():
                        count = _search.index_scenario(scenario)
                        print(f"[engine] Re-indexed {count} documents after file change", file=sys.stderr)
                    else:
                        print(f"[engine] Scenario reloaded after file change (no AI Search)", file=sys.stderr)
                except Exception as exc:
                    print(f"[engine] Re-index failed: {exc}", file=sys.stderr)

    thread = threading.Thread(target=_watch, args=(sc,), daemon=True, name="json-watcher")
    thread.start()
    print(f"[engine] File watcher started for {sc.root.name} (auto-re-index on JSON changes)", file=sys.stderr)


def _take_snapshot(sc: Scenario) -> None:
    """Capture current record IDs per fixture file for change diffing."""
    scenario_key = str(sc.root)
    snap: dict[str, set[str]] = {}
    # Meetings — include action item IDs
    meeting_ids: set[str] = set()
    for m in sc.meetings:
        meeting_ids.add(m.get("id", ""))
        for ai in m.get("action_items", []):
            meeting_ids.add(ai.get("id", ""))
    snap["meetings.json"] = meeting_ids
    # Teams messages
    snap["teams.json"] = {msg.get("id", "") for msg in sc.teams_messages}
    # Emails
    snap["emails.json"] = {e.get("id", "") for e in sc.emails}
    # Files
    snap["files.json"] = {f.get("id", "") for f in sc.files}
    # Tables
    for table_name, rows in sc.tables.items():
        snap[f"tables/{table_name}.json"] = {r.get("id", "") for r in rows}
    _last_snapshot[scenario_key] = snap


def _emit_change_events(sc: Scenario, old_snap: dict[str, set[str]]) -> None:
    """Compare current scenario state against the old snapshot and emit ChangeEvents."""
    # Take new snapshot
    _take_snapshot(sc)
    new_snap = _last_snapshot.get(str(sc.root), {})

    for file_key, new_ids in new_snap.items():
        old_ids = old_snap.get(file_key, set())
        added = new_ids - old_ids
        if added:
            evt = ChangeEvent(
                file=file_key,
                kind="new",
                added_ids=sorted(added),
            )
            change_queue.append(evt)
            print(
                f"[engine][CDC] New records in {file_key}: {sorted(added)}",
                file=sys.stderr,
            )


def _reload_scenario_inplace(sc: Scenario) -> None:
    """Reload all fixture files from disk into an existing Scenario object."""
    for rel, key in FIXTURE_FILES.items():
        path = sc.root / rel
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        setattr(sc, key, data.get(key, []))

    # Reload tables
    tables_path = sc.root / TABLES_DIR
    if tables_path.is_dir():
        sc.tables.clear()
        sc.table_formats.clear()
        for tf in sorted(tables_path.glob("*.json")):
            with open(tf, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            stem = tf.stem
            if isinstance(data, dict):
                sc.table_formats[stem] = "dict"
                rows = data.get(stem)
                if rows is None:
                    list_keys = [k for k, v in data.items()
                                 if k != "_comment" and isinstance(v, list)]
                    rows = data[list_keys[0]] if list_keys else []
                sc.tables[stem] = rows or []
            else:
                sc.table_formats[stem] = "list"
                sc.tables[stem] = data or []

    _build_index(sc)


def _build_index(sc: Scenario) -> None:
    """Index every citable entity by its stable id. Action items are indexed too."""
    idx: dict[str, tuple[str, dict]] = {}

    for person in sc.people:
        idx[person["id"]] = ("person", person)
    for email in sc.emails:
        idx[email["id"]] = ("email", email)
    for msg in sc.teams_messages:
        idx[msg["id"]] = ("teams_message", msg)
    for f in sc.files:
        idx[f["id"]] = ("file", f)
    for table, rows in sc.tables.items():
        kind = _kind_for_table(table)
        for row in rows:
            rid = row.get("id")
            if not rid:
                sys.stderr.write(
                    f"[workiq-sim] WARNING: row in table '{table}' is missing an 'id'; "
                    f"skipping it (not citable): {row}\n"
                )
                continue
            idx[rid] = (kind, row)
    for mtg in sc.meetings:
        idx[mtg["id"]] = ("meeting", mtg)
        for ai in mtg.get("action_items", []):
            # action items inherit the parent meeting's acl for trimming
            ai_record = dict(ai)
            ai_record.setdefault("acl", mtg.get("acl", ["all"]))
            ai_record["_meeting_id"] = mtg["id"]
            idx[ai["id"]] = ("action_item", ai_record)

    sc.index = idx


# --------------------------------------------------------------------------- #
# Permission trimming
# --------------------------------------------------------------------------- #

def _acl_of(record: dict) -> list[str]:
    acl = record.get("acl")
    if not acl:
        return ["all"]
    return acl


def _email_participants(record: dict) -> set[str]:
    """Return the set of person IDs who are from/to/cc on an email record."""
    participants: set[str] = set()
    frm = record.get("from")
    if frm:
        participants.add(frm)
    for pid in record.get("to") or []:
        participants.add(pid)
    for pid in record.get("cc") or []:
        participants.add(pid)
    return participants


def can_see(record: dict, persona_id: str | None, person_id: str | None = None) -> bool:
    """A record is visible if its acl contains 'all', or contains the persona id.

    For emails (records with 'from'/'to'/'cc' fields): also visible if the
    persona's person_id appears in the from, to, or cc fields — i.e. only
    participants on the email can see it.

    When persona_id is None (no persona selected) the simulator grants full
    visibility — mirroring an unscoped admin/dev session.
    """
    if persona_id is None:
        return True
    acl = _acl_of(record)
    if "all" in acl:
        return True
    if persona_id in acl:
        return True
    # Email participant check: if this is an email and we have a person_id,
    # allow visibility if the person is a participant (from/to/cc).
    if person_id and "from" in record and "to" in record:
        if person_id in _email_participants(record):
            return True
    return False


# --------------------------------------------------------------------------- #
# Citation resolution
# --------------------------------------------------------------------------- #

def _title_for(kind: str, record: dict) -> str:
    if kind == "person":
        return f"{record.get('name')} — {record.get('title')}"
    if kind == "email":
        return f"Email: {record.get('subject')}"
    if kind == "meeting":
        return f"Meeting: {record.get('title')} ({record.get('date', '')[:10]})"
    if kind == "teams_message":
        return f"Teams ({record.get('channel')}): {record.get('author')}"
    if kind == "file":
        return f"File: {record.get('name')}"
    if kind == "action_item":
        return f"Action item: {record.get('text', '')[:60]}"
    # Generic table row (milestone, capa, engagement, deal, …): pick the best label field.
    label = (
        record.get("milestone")
        or record.get("action")
        or record.get("title")
        or record.get("name")
        or record.get("description")
        or record.get("id")
    )
    return f"{kind.replace('_', ' ').title()}: {label}"


def resolve_citations(
    sc: Scenario, citation_ids: list[str], persona_id: str | None
) -> tuple[list[dict], list[str]]:
    """Resolve citation ids to {citation_id, source_index, title, kind}, trimming any
    the persona may not see. Returns (visible_citations, trimmed_ids)."""
    person_id = _person_id_for(sc, persona_id)
    visible: list[dict] = []
    trimmed: list[str] = []
    source_index = 1
    for cid in citation_ids:
        entry = sc.index.get(cid)
        if entry is None:
            continue
        kind, record = entry
        if not can_see(record, persona_id, person_id):
            trimmed.append(cid)
            continue
        visible.append(
            {
                "citation_id": cid,
                "source_index": source_index,
                "title": _title_for(kind, record),
                "kind": kind,
                "sensitivity": record.get("sensitivity", "internal"),
                # Placeholder so UI layers that render clickable citation links don't
                # break; the real Work IQ server returns a Graph webUrl here.
                "url": record.get("url", f"https://simulator.local/{kind}/{cid}"),
            }
        )
        source_index += 1
    return visible, trimmed


# --------------------------------------------------------------------------- #
# Golden-answer matching
# --------------------------------------------------------------------------- #

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


_SUFFIXES = ("ing", "ers", "er", "ed", "es", "s")


def _stem(token: str) -> str:
    """Light, symmetric suffix stripper so 'blocking'/'blockers' both reduce to 'block'.
    Applied to BOTH keywords and the question, so over-stemming stays consistent."""
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if len(token) > len(suf) + 2 and token.endswith(suf):
                token = token[: -len(suf)]
                changed = True
                break
    return token


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in _normalize(text).split() if t}


def _match_stats(question: str, golden: dict) -> tuple[int, float]:
    """(absolute keyword hits, fraction of keywords matched) for ranking golden entries.

    A keyword phrase matches if every (stemmed) word in it appears in the (stemmed)
    question token set — order-independent and morphology-tolerant, so realistic
    paraphrases ('what are the blockers?') still match 'blocking'."""
    qtokens = _tokens(question)
    keywords = golden.get("keywords", [])
    if not keywords:
        return (0, 0.0)
    hits = 0
    for kw in keywords:
        kwt = _tokens(kw)
        if kwt and kwt <= qtokens:
            hits += 1
    return (hits, hits / len(keywords))


def _score_golden(question: str, golden: dict) -> float:
    """Fraction of the golden entry's keyword phrases present in the question.
    Retained for callers (e.g. validate_scenario) that only need the fraction."""
    return _match_stats(question, golden)[1]


def match_golden(sc: Scenario, question: str, threshold: float = 0.5) -> dict | None:
    """Return the best-matching golden entry at/above the fraction `threshold`.

    Ranking is by (absolute hits, fraction): a question that matches more keyword
    phrases outranks one that matches a higher fraction of fewer phrases, so a short
    generic entry can't hijack a longer, more specific one. On exact ties the FIRST
    entry in declaration order wins (deterministic)."""
    best: dict | None = None
    best_key: tuple[int, float] = (-1, -1.0)
    for g in sc.golden:
        hits, frac = _match_stats(question, g)
        if frac >= threshold and (hits, frac) > best_key:
            best_key = (hits, frac)
            best = g
    return best


# --------------------------------------------------------------------------- #
# LLM fallback (optional, OpenAI-compatible)
# --------------------------------------------------------------------------- #

def _llm_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _llm_answer(question: str, context_snippets: list[str]) -> str | None:
    """Best-effort ad-hoc synthesis. Returns None if no model is configured or the
    call fails — the caller then degrades gracefully."""
    if not _llm_available():
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
            api_key=os.environ["OPENAI_API_KEY"],
        )
        model = os.environ.get("MODEL", "gpt-4o-mini")
        context = "\n\n".join(context_snippets[:12])
        prompt = (
            "You are a Work IQ simulator answering from the provided work-context "
            "snippets only. Cite the bracketed ids you use. If the snippets do not "
            "contain the answer, say so.\n\nSNIPPETS:\n"
            f"{context}\n\nQUESTION: {question}\n\nANSWER:"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content
    except Exception:
        return None


def _person_id_for(sc: Scenario, persona_id: str | None) -> str | None:
    """Resolve a persona's person_id (e.g. 'quality_pm' -> 'PPL-001')."""
    if persona_id is None:
        return None
    persona = sc.get_persona(persona_id)
    return persona.get("person_id") if persona else None


def _all_snippets(sc: Scenario, persona_id: str | None) -> list[dict]:
    """Flatten visible fixtures into (id, text) snippets for retrieval/fallback.
    Every snippet is permission-checked so restricted content never reaches the LLM
    fallback context or the retrieval-only response for an unauthorized persona."""
    person_id = _person_id_for(sc, persona_id)
    snippets: list[dict] = []
    for email in sc.emails:
        if can_see(email, persona_id, person_id):
            snippets.append({"id": email["id"], "text": f"{email.get('subject')} :: {email.get('body')}"})
    for mtg in sc.meetings:
        if can_see(mtg, persona_id, person_id):
            snippets.append({"id": mtg["id"], "text": f"{mtg.get('title')} :: {mtg.get('recap')}"})
            for ai in mtg.get("action_items", []):
                ai_rec = sc.index.get(ai["id"], (None, ai))[1]
                if can_see(ai_rec, persona_id, person_id):
                    snippets.append({"id": ai["id"], "text": f"Action item ({mtg.get('title')}): {ai.get('text')} (owner {ai.get('owner')}, due {ai.get('due')}, {ai.get('status')})"})
    for msg in sc.teams_messages:
        if can_see(msg, persona_id, person_id):
            snippets.append({"id": msg["id"], "text": f"{msg.get('channel')} :: {msg.get('text')}"})
    for f in sc.files:
        if can_see(f, persona_id, person_id):
            snippets.append({"id": f["id"], "text": f"{f.get('name')} :: {f.get('summary')}"})
    for table, rows in sc.tables.items():
        for row in rows:
            if can_see(row, persona_id, person_id):
                fields = ", ".join(f"{k} {v}" for k, v in row.items() if k != "acl")
                snippets.append({"id": row["id"], "text": f"{_kind_for_table(table).title()} record :: {fields}"})
    for person in sc.people:
        if can_see(person, persona_id, person_id):
            snippets.append({"id": person["id"], "text": f"{person.get('name')} :: {person.get('title')} :: {', '.join(person.get('expertise', []))}"})
    return snippets


def _retrieve(snippets: list[dict], question: str, k: int = 6) -> list[dict]:
    """Retrieve top-k snippets using cosine similarity on embeddings if available,
    falling back to term-overlap if no embedding endpoint is configured."""
    embeddings = _get_embeddings([s["text"] for s in snippets] + [question])
    if embeddings is not None:
        snippet_vecs = embeddings[:-1]
        query_vec = embeddings[-1]
        # Cosine similarity
        norms = np.linalg.norm(snippet_vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1
        snippet_normed = snippet_vecs / norms
        query_norm = query_vec / (np.linalg.norm(query_vec) or 1)
        scores = snippet_normed @ query_norm
        top_indices = np.argsort(scores)[::-1][:k]
        return [snippets[i] for i in top_indices if scores[i] > 0]

    # Fallback: term overlap
    q_terms = set(_normalize(question).split())
    scored = []
    for s in snippets:
        terms = set(_normalize(s["text"]).split())
        overlap = len(q_terms & terms)
        if overlap:
            scored.append((overlap, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:k]]


def _get_embeddings(texts: list[str]):
    """Get embeddings from Azure OpenAI. Returns numpy array or None if unavailable."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    if not endpoint:
        return None
    # Strip /openai/v1 suffix if present to get the base endpoint
    base = re.sub(r"/openai/v1$", "", endpoint)
    deploy = os.environ.get("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    api_version = "2024-02-01"
    url = f"{base}/openai/deployments/{deploy}/embeddings?api-version={api_version}"

    try:
        import httpx
        from azure.identity import AzureCliCredential
        credential = AzureCliCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default").token
        resp = httpx.post(
            url,
            json={"input": texts},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        if resp.status_code != 200:
            print(f"[engine] embedding request failed ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
            return None
        data = resp.json()
        vecs = [item["embedding"] for item in data["data"]]
        return np.array(vecs, dtype=np.float32)
    except Exception as exc:
        print(f"[engine] embedding fallback to term-overlap: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Public API: ask
# --------------------------------------------------------------------------- #

GOVERNANCE_NOTE = (
    "\n\n[Governance] {n} source(s) were withheld from this answer because the active "
    "persona ('{persona}') does not have access to restricted/customer-confidential "
    "material: {ids}. Switch to a leadership persona to see them."
)


def ask(sc: Scenario, question: str, persona_id: str | None = None) -> dict:
    """Answer a question. Returns {response, conversationId, citations, trimmed}."""
    conversation_id = f"sim-{uuid.uuid4().hex[:12]}"
    golden = match_golden(sc, question)

    if golden is not None:
        visible, trimmed = resolve_citations(sc, golden.get("citations", []), persona_id)
        response = golden["answer"]
        if trimmed:
            # RBAC: return the full answer but strip restricted citations from the
            # visible set and append a governance note. The agent handles any further
            # messaging about restricted content.
            persona = sc.get_persona(persona_id)
            label = persona["label"] if persona else (persona_id or "unscoped")
            response += GOVERNANCE_NOTE.format(
                n=len(trimmed), persona=label, ids=", ".join(trimmed)
            )
        return {
            "response": response,
            "conversationId": conversation_id,
            "citations": visible,
            "trimmed": trimmed,
            "source": "golden",
            "matched": golden["id"],
            "tool": golden.get("tool"),
        }

    # No golden match — retrieve via AI Search (with cache) or fall back to in-memory.
    data_ver = _data_version(sc)
    source_label = "retrieval-only"

    # Step 1: Get query embedding (from cache or compute fresh — avoids redundant API calls)
    query_vec = _embedding_cache.get(question)
    if query_vec is None:
        raw = _get_embeddings([question])
        if raw is not None:
            query_vec = raw[0]
            _embedding_cache.put(question, query_vec)

    # Step 2: Check semantic result cache (handles paraphrases via cosine similarity)
    top: list[dict] = []
    if query_vec is not None:
        cached_results = _result_cache.get(query_vec, persona_id, data_ver)
        if cached_results is not None:
            top = cached_results
            source_label = "cache"

    # Step 3: If cache miss, query AI Search (if configured) or fall back to in-memory
    if not top:
        if _search.is_available() and query_vec is not None:
            top = _search.search(
                query_embedding=query_vec,
                question=question,
                persona_id=persona_id,
                scenario_name=sc.root.name,
                k=6,
            )
            if top:
                _result_cache.put(query_vec, persona_id, data_ver, top)
                source_label = "ai-search"
        if not top:
            # Fallback: original in-memory retrieval (no AI Search configured)
            snippets = _all_snippets(sc, persona_id)
            top = _retrieve(snippets, question)
            source_label = "in-memory"

    # Log retrieval source for observability (visible in server terminal)
    print(f"[engine] ask source={source_label} question={question[:80]!r}", file=sys.stderr)

    # Step 4: Synthesize with LLM if available
    llm = _llm_answer(question, [f"[{s['id']}] {s['text']}" for s in top])
    if llm is not None:
        cited_ids = [s["id"] for s in top]
        visible, _ = resolve_citations(sc, cited_ids, persona_id)
        return {
            "response": llm,
            "conversationId": conversation_id,
            "citations": visible,
            "trimmed": [],
            "source": f"llm+{source_label}",
            "matched": None,
            "tool": None,
        }

    # Graceful degradation: no golden, no model.
    if top:
        bullets = "\n".join(f"- [{s['id']}] {s['text'][:140]}" for s in top)
        response = (
            "No scripted answer matched this question, and no model is configured "
            "(set OPENAI_API_KEY for ad-hoc synthesis). Closest work-context signals:\n"
            f"{bullets}"
        )
    else:
        response = (
            "No scripted answer matched and no relevant work-context signals were found "
            "for the active persona."
        )
    visible, _ = resolve_citations(sc, [s["id"] for s in top], persona_id)
    return {
        "response": response,
        "conversationId": conversation_id,
        "citations": visible,
        "trimmed": [],
        "source": source_label,
        "matched": None,
        "tool": None,
    }


# --------------------------------------------------------------------------- #
# Public API: Tools surface (fetch / create_entity / update_entity)
# --------------------------------------------------------------------------- #

def _persist_table(sc: Scenario, table: str) -> None:
    rows = sc.tables.get(table)
    if rows is None:
        return
    path = sc.root / "tables" / f"{table}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Round-trip in the file's original shape (bare list vs {stem: rows}) so persisting
    # never silently rewrites the on-disk format.
    payload: Any = rows if sc.table_formats.get(table) == "list" else {table: rows}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def _default_table_acl(rows: list[dict]) -> list[str] | None:
    """ACL to apply to a new row that omits one: inherit from the first existing row that
    declares an `acl` (least-privilege — a new row on a restricted table must not default
    to world-readable). Returns None when no row declares an acl (table is public)."""
    for row in rows:
        acl = row.get("acl")
        if acl:
            return list(acl)
    return None


def _next_id(rows: list[dict], prefix: str) -> str:
    """Generate a unique id of the form PREFIX-NNN based on the max existing numeric
    suffix (not len(rows), which collides when rows were deleted or ids are sparse)."""
    max_n = 0
    existing = {row.get("id") for row in rows}
    for rid in existing:
        if isinstance(rid, str) and rid.startswith(prefix + "-"):
            try:
                max_n = max(max_n, int(rid.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                continue
    n = max_n + 1
    while f"{prefix}-{n:03d}" in existing:
        n += 1
    return f"{prefix}-{n:03d}"


def fetch(sc: Scenario, table: str, filter: dict | None = None) -> list[dict]:
    """Read rows from a Tools-backed table, optionally filtered by field match.
    String comparisons are case-insensitive substring (contains) matching;
    other types use exact equality."""
    rows = sc.tables.get(table)
    if rows is None:
        raise ValueError(f"Unknown table: {table}")
    if not filter:
        return list(rows)
    out = []
    for row in rows:
        match = True
        for k, v in filter.items():
            rv = row.get(k)
            if isinstance(rv, str) and isinstance(v, str):
                if v.lower() not in rv.lower():
                    match = False
                    break
            elif rv != v:
                match = False
                break
        if match:
            out.append(row)
    return out


def create_entity(
    sc: Scenario, table: str, record: dict, persist: bool = False,
    approved_by: str | None = None, source_citations: list[str] | None = None,
) -> dict:
    """Append a row to a Tools-backed table. Idempotent on `id` and on a
    `dedupe_key` of (milestone, owner) for the milestone tracker — re-issuing the
    same logical create returns the existing row instead of duplicating."""
    rows = sc.tables.get(table)
    if rows is None:
        raise ValueError(f"Unknown table: {table}")

    record = dict(record)  # never mutate the caller's dict
    new_id = record.get("id")
    if new_id:
        existing = sc.index.get(new_id)
        if existing is not None:
            _, existing_row = existing
            if any(r is existing_row for r in rows):
                return {"created": False, "reason": "id_exists", "row": existing_row}
            # id is already used by a DIFFERENT entity (another table, an email, a
            # person...) — appending would clobber its index entry. Reject.
            return {
                "created": False,
                "reason": "id_collision",
                "detail": f"id '{new_id}' is already used by another entity",
            }

    # logical dedupe for milestone tracker
    if table == "milestone_tracker":
        m = record.get("milestone")
        o = record.get("owner")
        if m and o:
            for row in rows:
                if row.get("milestone") == m and row.get("owner") == o:
                    return {"created": False, "reason": "duplicate_milestone_owner", "row": row}

    if not new_id:
        record["id"] = _next_id(rows, _prefix_for_table(rows, table))

    # least-privilege: a new row that omits `acl` inherits the table's existing acl rather
    # than defaulting to world-readable (can_see treats missing acl as ["all"]).
    if "acl" not in record:
        inherited = _default_table_acl(rows)
        if inherited is not None:
            record["acl"] = inherited

    # Audit trail: stamp who approved the creation
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if approved_by:
        record["created_by"] = approved_by
        record["created_at"] = now
        record.setdefault("approval_log", []).append({
            "approver": approved_by,
            "action": "created",
            "timestamp": now,
            "source_citations": source_citations or [],
        })

    rows.append(record)
    sc.index[record["id"]] = (_kind_for_table(table), record)
    if persist:
        _persist_table(sc, table)

    # Invalidate search result cache (data changed) and index new row in AI Search
    _result_cache.clear()
    if _search.is_available():
        kind = _kind_for_table(table)
        fields_text = ", ".join(f"{k}: {v}" for k, v in record.items() if k != "acl")
        _search.index_single_document({
            "id": record["id"],
            "kind": kind,
            "text": f"{kind.title()} record :: {fields_text}",
            "title": f"{kind.title()}: {record.get('milestone') or record.get('title') or record.get('name') or record['id']}",
            "scenario": sc.root.name,
            "content_source": "direct",
            "parent_id": "",
            "source_file": "",
            "acl": record.get("acl", ["all"]),
        })

    return {"created": True, "row": record}


def update_entity(
    sc: Scenario, table: str, id: str, patch: dict, persist: bool = False,
    approved_by: str | None = None, source_citations: list[str] | None = None,
) -> dict:
    """Patch fields on an existing row by id. If the patch changes `id`, the citation
    index is atomically rekeyed so lookups stay consistent (and id collisions are
    rejected)."""
    rows = sc.tables.get(table)
    if rows is None:
        raise ValueError(f"Unknown table: {table}")
    for row in rows:
        if row.get("id") == id:
            new_id = patch.get("id", id)
            if new_id != id and new_id in sc.index:
                return {"updated": False, "reason": "id_collision"}
            row.update(patch)
            if new_id != id:
                kind = sc.index.get(id, (None,))[0]
                sc.index.pop(id, None)
                if kind is not None:
                    sc.index[new_id] = (kind, row)

            # Audit trail: stamp who approved the update
            if approved_by:
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                row["modified_by"] = approved_by
                row["modified_at"] = now
                row.setdefault("approval_log", []).append({
                    "approver": approved_by,
                    "action": "updated",
                    "timestamp": now,
                    "fields_changed": list(patch.keys()),
                    "source_citations": source_citations or [],
                })

            if persist:
                _persist_table(sc, table)

            # Invalidate search result cache (data changed) and update in AI Search
            _result_cache.clear()
            if _search.is_available():
                kind_label = _kind_for_table(table)
                fields_text = ", ".join(f"{k}: {v}" for k, v in row.items() if k != "acl")
                _search.index_single_document({
                    "id": row["id"],
                    "kind": kind_label,
                    "text": f"{kind_label.title()} record :: {fields_text}",
                    "title": f"{kind_label.title()}: {row.get('milestone') or row.get('title') or row.get('name') or row['id']}",
                    "scenario": sc.root.name,
                    "content_source": "direct",
                    "parent_id": "",
                    "source_file": "",
                    "acl": row.get("acl", ["all"]),
                })

            return {"updated": True, "row": row}
    return {"updated": False, "reason": "not_found"}
