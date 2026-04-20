"""
backend/services/reconciler.py
================================
Autonomous Anime Reconciliation System
Agent 4 - Lead Architect Implementation

First Principles:
  1. AniList ID  = single source of truth
  2. Providers   = Supply Nodes (untrusted, may collide)
  3. Gemini API  = Semantic arbiter when difflib score < 0.7
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

import httpx

from db.connection import database
from services.anilist import fetch_anilist_info
from utils.ssrf_guard import SSRFSafeTransport

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("[WARNING] GEMINI_API_KEY is not set.")
GEMINI_MODEL    = "gemini-2.5-flash"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
    f"?key={GEMINI_API_KEY}"
)
DIFFLIB_THRESHOLD = 0.70   # Below this → ask Gemini
GEMINI_TIMEOUT    = 8.0    # seconds — keep it snappy on Termux


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────
@dataclass
class ProviderCandidate:
    provider_id:   str          # "oploverz" | "otakudesu" | "samehadaku"
    provider_slug: str          # URL slug
    raw_title:     str          # Title as seen on provider
    anilist_id:    Optional[int] = None
    confidence:    float = 0.0
    matched_via:   str = "none" # "difflib" | "gemini" | "exact"


@dataclass
class ReconciliationResult:
    canonical_anilist_id: int
    canonical_title:      str
    anilist_metadata:     Optional[dict] = None # Include full data here
    providers:            list[ProviderCandidate] = field(default_factory=list)
    conflicts_resolved:   int = 0
    migrated_records:     int = 0


# ─────────────────────────────────────────────
# Gemini Semantic Matcher  (lazy singleton)
# ─────────────────────────────────────────────
class GeminiMatcher:
    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                transport=SSRFSafeTransport(),
                timeout=GEMINI_TIMEOUT,
                verify=True,
            )
        return cls._client

    @classmethod
    async def guess_clean_title(cls, dirty_title: str) -> str:
        """
        Ask Gemini to infer the canonical anime title from a dirty slug/string.
        Returns the guessed title, or empty string on failure.
        """
        prompt = (
            "You are an anime expert. Given a messy provider slug or dirty title, "
            "return ONLY the canonical anime title in romaji — no explanation, no markdown.\n\n"
            f"Input: \"{dirty_title}\"\n"
            "Output (title only):"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 40, "temperature": 0},
        }
        try:
            r = await cls._get_client().post(GEMINI_ENDPOINT, json=payload)
            raw = r.json()
            if r.status_code != 200:
                print(f"[Gemini] Error API {r.status_code}: {raw}")
                return ""
            text = (
                raw.get("candidates", [{}])[0]
                   .get("content", {})
                   .get("parts", [{}])[0]
                   .get("text", "")
            )
            return text.strip().strip('"').strip("'")
        except Exception as e:
            print(f"[Gemini] guess_clean_title error: {e}")
            return ""

    @classmethod
    async def is_same_anime(
        cls,
        provider_title: str,
        anilist_candidates: list[str],
    ) -> tuple[bool, str]:
        """
        Ask Gemini whether `provider_title` matches any of `anilist_candidates`.
        Returns (matched: bool, best_match_title: str).
        """
        prompt = (
            "You are an anime title matcher. "
            "Reply ONLY with a JSON object — no markdown, no explanation.\n\n"
            f"Provider title: \"{provider_title}\"\n"
            f"AniList candidates: {json.dumps(anilist_candidates)}\n\n"
            "Return: {\"matched\": true/false, \"best_match\": \"<title or empty>\"}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 80, 
                "temperature": 0,
                "responseMimeType": "application/json"
            },
        }
        try:
            r = await cls._get_client().post(GEMINI_ENDPOINT, json=payload)
            raw = r.json()
            text = (
                raw.get("candidates", [{}])[0]
                   .get("content", {})
                   .get("parts", [{}])[0]
                   .get("text", "{}")
            )
            # Strip possible markdown fences
            text = re.sub(r"```json|```", "", text).strip()
            data = json.loads(text)
            return bool(data.get("matched")), data.get("best_match", "")
        except Exception as e:
            print(f"[Gemini] Matching error: {e}")
            return False, ""

    @classmethod
    async def close(cls):
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()


# ─────────────────────────────────────────────
# Core Reconciler
# ─────────────────────────────────────────────
class AnimeReconciler:
    """
    Detects Mapping Collisions and performs atomic Self-Healing.
    """

    @staticmethod
    def _difflib_score(a: str, b: str) -> float:
        return SequenceMatcher(
            None,
            _normalize(a),
            _normalize(b),
        ).ratio()

    @staticmethod
    async def _get_existing_mapping(
        provider_id: str, provider_slug: str
    ) -> Optional[dict]:
        row = await database.fetch_one(
            """
            SELECT m."anilistId", meta."cleanTitle", meta."nativeTitle"
            FROM anime_mappings m
            JOIN anime_metadata meta ON m."anilistId" = meta."anilistId"
            WHERE m."providerId" = :pid AND m."providerSlug" = :slug
            """,
            {"pid": provider_id, "slug": provider_slug},
        )
        return dict(row) if row else None

    @staticmethod
    async def _get_anilist_alt_titles(anilist_id: int) -> list[str]:
        row = await database.fetch_one(
            'SELECT "cleanTitle", "nativeTitle" FROM anime_metadata WHERE "anilistId" = :id',
            {"id": anilist_id},
        )
        if not row:
            return []
        return [t for t in [row["cleanTitle"], row["nativeTitle"]] if t]

    @staticmethod
    async def _migrate_history(old_id: int, new_id: int) -> int:
        tables = [
            ("user_bookmarks", "anilistId"),
            ("watch_history",  "anilistId"),
        ]
        migrated = 0
        for table, col in tables:
            try:
                result = await database.execute(
                    f"""
                    UPDATE {table}
                    SET "{col}" = :new_id
                    WHERE "{col}" = :old_id
                      AND NOT EXISTS (
                          SELECT 1 FROM {table} t2
                          WHERE t2."{col}" = :new_id
                            AND t2."userId" = {table}."userId"
                      )
                    """,
                    {"new_id": new_id, "old_id": old_id},
                )
                migrated += result or 0
            except Exception as e:
                pass
        return migrated

    async def reconcile(
        self,
        provider_id:   str,
        provider_slug: str,
        raw_title:     str,
    ) -> Optional[ReconciliationResult]:
        candidate = ProviderCandidate(
            provider_id=provider_id,
            provider_slug=provider_slug,
            raw_title=raw_title,
        )

        # ── Step 1: Try AniList with raw_title directly ──────────────────────
        anilist_data = await fetch_anilist_info(raw_title)

        # ── Step 2: If failed, sanitize slug and retry ────────────────────────
        if not anilist_data:
            sanitized = sanitize_slug_title(raw_title)
            if sanitized and sanitized != raw_title:
                print(f"[Reconciler] AniList miss for '{raw_title}', retrying sanitized: '{sanitized}'")
                anilist_data = await fetch_anilist_info(sanitized)

        # ── Step 3: Still failed → ask Gemini to guess the real title ─────────
        if not anilist_data:
            guessed_title = await GeminiMatcher.guess_clean_title(raw_title)
            if guessed_title:
                print(f"[Reconciler] Gemini guessed '{guessed_title}' for slug '{raw_title}'")
                anilist_data = await fetch_anilist_info(guessed_title)

        if not anilist_data:
            print(f"[Reconciler] All strategies exhausted for '{raw_title}' — giving up.")
            return None

        new_id    = anilist_data["anilistId"]
        new_title = anilist_data["cleanTitle"] or anilist_data.get("nativeTitle", "")

        existing = await self._get_existing_mapping(provider_id, provider_slug)
        conflicts_resolved = 0
        migrated           = 0

        if existing:
            old_id    = existing["anilistId"]
            old_title = existing["cleanTitle"] or ""

            if old_id == new_id:
                candidate.anilist_id  = new_id
                candidate.confidence  = 1.0
                candidate.matched_via = "exact"
            else:
                score = self._difflib_score(raw_title, new_title)
                matched_via = "difflib"

                if score < DIFFLIB_THRESHOLD:
                    gemini_match = False
                    best = ""
                    # Check cache first
                    try:
                        from services.cache import upstash_get, upstash_set
                        import hashlib
                        
                        cache_key = f"title_match:{hashlib.md5(raw_title.encode()).hexdigest()[:12]}"
                        cached_match = await upstash_get(cache_key)
                        
                        if cached_match is not None and isinstance(cached_match, dict):
                            gemini_match = cached_match.get("matched", False)
                            best = cached_match.get("best_match", "")
                            matched_via = "gemini_cache"
                        else:
                            alt_titles = await self._get_anilist_alt_titles(old_id)
                            alt_titles.append(new_title)
                            gemini_match, best = await GeminiMatcher.is_same_anime(
                                raw_title, alt_titles
                            )
                            await upstash_set(cache_key, {"matched": gemini_match, "best_match": best}, ex=604800)
                            matched_via = "gemini"
                    except Exception as e:
                        # Fallback without cache if it fails
                        alt_titles = await self._get_anilist_alt_titles(old_id)
                        alt_titles.append(new_title)
                        gemini_match, best = await GeminiMatcher.is_same_anime(
                            raw_title, alt_titles
                        )
                        matched_via = "gemini"

                    if gemini_match and best:
                        if _normalize(best) == _normalize(old_title):
                            new_id    = old_id
                            new_title = old_title
                        score = 0.9
                    else:
                        candidate.anilist_id  = old_id
                        candidate.confidence  = score
                        candidate.matched_via = "gemini_uncertain"
                        return ReconciliationResult(
                            canonical_anilist_id=old_id,
                            canonical_title=old_title,
                            providers=[candidate],
                        )

                if old_id != new_id:
                    migrated = await self._migrate_history(old_id, new_id)
                    conflicts_resolved = 1

                candidate.anilist_id  = new_id
                candidate.confidence  = score
                candidate.matched_via = matched_via

            return ReconciliationResult(
                canonical_anilist_id=new_id,
                canonical_title=new_title,
                anilist_metadata=anilist_data,
                providers=[candidate],
                conflicts_resolved=conflicts_resolved,
                migrated_records=migrated,
            )
        else:
            score       = self._difflib_score(raw_title, new_title)
            matched_via = "difflib"

            if score < DIFFLIB_THRESHOLD:
                alt = [new_title]
                if anilist_data.get("nativeTitle"):
                    alt.append(anilist_data["nativeTitle"])
                gemini_match, _ = await GeminiMatcher.is_same_anime(raw_title, alt)
                matched_via     = "gemini"
                if not gemini_match:
                    return None
                score = 0.85

            candidate.anilist_id  = new_id
            candidate.confidence  = score
            candidate.matched_via = matched_via

            return ReconciliationResult(
            canonical_anilist_id=new_id,
            canonical_title=new_title,
            anilist_metadata=anilist_data, # Data is now attached here
            providers=[candidate],
            conflicts_resolved=conflicts_resolved,
            migrated_records=migrated,
            )
    async def reconcile_batch(
        self,
        items: list[dict],
        concurrency: int = 3,
    ) -> list[ReconciliationResult]:
        sem = asyncio.Semaphore(concurrency)

        async def bounded(item):
            async with sem:
                await asyncio.sleep(0.3)
                return await self.reconcile(**item)

        results = await asyncio.gather(
            *(bounded(i) for i in items), return_exceptions=True
        )
        valid = [r for r in results if isinstance(r, ReconciliationResult)]
        return valid


def _normalize(title: str) -> str:
    t = str(title).lower()
    t = re.sub(r"\b(the|a|an)\b", "", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Noise words commonly appended by Kuronime and similar providers
_SLUG_NOISE_WORDS = re.compile(
    r"\b(op|ed|ost|ova|ona|movie|film|special|sub|indo|batch|"
    r"episode|eps?|season|part|the|and|of|wa|no|wo|ni|ga|to)\b",
    re.IGNORECASE,
)

def sanitize_slug_title(raw: str) -> str:
    """
    Convert a provider slug/dirty title into a clean search query.

    Examples:
      'one-piece-op'      → 'one piece'
      'dan-da-dan'        → 'dan da dan'
      'shingeki-no-kyojin-s4-part2' → 'shingeki kyojin s4 part2'
      'bleach-tybw-episode-1' → 'bleach tybw'
    """
    t = str(raw).lower().strip()
    # Replace hyphens and underscores with spaces
    t = re.sub(r"[-_]+", " ", t)
    # Strip trailing episode/number noise like "episode 12", "ep 5", etc.
    t = re.sub(r"\bepisode?\s*\d+\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\beps?\s*\d+\b", "", t, flags=re.IGNORECASE)
    # Remove standalone noise words
    t = _SLUG_NOISE_WORDS.sub(" ", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

reconciler = AnimeReconciler()