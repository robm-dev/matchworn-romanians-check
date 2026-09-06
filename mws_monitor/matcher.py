from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .utils import normalize_name


@dataclass(frozen=True)
class MatchResult:
    category_id: str | None
    athlete_name: str | None
    confidence: float
    status: str
    note: str
    candidates: list[dict[str, Any]]


ALIASES_WITH_SEARCH_TERMS = {
    "Samu Aghehowa": ["Samu Aghehowa", "Samu Omorodion", "Samuel Omorodion"],
    "Josko Gvardiol": ["Joško Gvardiol", "Josko Gvardiol"],
    "Aleksandar Pavlovic": ["Aleksandar Pavlović", "Aleksandar Pavlovic"],
    "Luka Vuskovic": ["Luka Vušković", "Luka Vuskovic"],
    "Pio Esposito": ["Francesco Pio Esposito", "Pio Esposito"],
    "Estêvão": ["Estêvão", "Estevão Willian", "Estevao"],
    "Savinho": ["Savinho", "Sávio Moreira de Oliveira", "Sávio"],
}


def candidate_score(input_name: str, candidate_name: str) -> float:
    wanted = normalize_name(input_name)
    candidate = normalize_name(candidate_name)
    if not wanted or not candidate:
        return 0
    if wanted == candidate:
        return 100
    wanted_parts = [part for part in wanted.split() if len(part) > 1]
    if len(wanted_parts) == 1:
        return 60 if wanted_parts[0] in candidate else 0
    if wanted_parts and all(part in candidate for part in wanted_parts):
        return max(80, 94 - abs(len(candidate) - len(wanted)) * 0.25)
    if wanted_parts and wanted_parts[0] in candidate and wanted_parts[-1] in candidate:
        return 75
    if wanted in candidate or candidate in wanted:
        return 60
    return 0


def search_terms_for(name: str, alias: dict[str, str] | None) -> list[str]:
    terms: list[str] = []
    if alias and alias.get("preferred_mws_athlete_name"):
        terms.append(alias["preferred_mws_athlete_name"])
    terms.extend(ALIASES_WITH_SEARCH_TERMS.get(name, []))
    terms.append(name)
    deduped: list[str] = []
    for term in terms:
        if term and term not in deduped:
            deduped.append(term)
    return deduped


def resolve_match(input_name: str, candidates: list[dict[str, Any]], alias: dict[str, str] | None = None) -> MatchResult:
    if alias and alias.get("preferred_mws_category_id"):
        return MatchResult(
            category_id=alias["preferred_mws_category_id"],
            athlete_name=alias.get("preferred_mws_athlete_name") or input_name,
            confidence=100,
            status="found",
            note="manual alias category id",
            candidates=candidates,
        )
    if alias and alias.get("notes", "").lower().startswith("needs manual review"):
        return MatchResult(None, None, 0, "needs_review", alias["notes"], candidates)

    best: tuple[float, dict[str, Any] | None] = (0, None)
    for candidate in candidates:
        score = candidate_score(alias.get("preferred_mws_athlete_name", input_name) if alias else input_name, candidate.get("name", ""))
        if score > best[0]:
            best = (score, candidate)
    if best[1] is None:
        return MatchResult(None, None, 0, "not_found", "no MWS athlete candidates", candidates)
    if best[0] < 70:
        return MatchResult(None, None, best[0], "needs_review", "low confidence athlete match", candidates)
    return MatchResult(best[1].get("id"), best[1].get("name"), best[0], "found", f"matched at {best[0]:.0f}", candidates)
