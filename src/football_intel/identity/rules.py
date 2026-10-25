"""The rules that propose links from Transfermarkt and Understat players to Sofascore
players. Pure functions: the database is read and written elsewhere.

Sofascore is the anchor: every Sofascore player is a Player, with a birth date, in every
lineup. Proposals at or above `ACCEPT_FROM` become links; those from `JUDGE_FROM` are the
ambiguous band left to the LLM judge; lower scores are not proposed at all.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from football_intel.identity.names import similarity

ACCEPT_FROM = 0.9
JUDGE_FROM = 0.6
# Two names at least this similar are the same name, give or take spelling.
SAME_NAME = 0.9
# Understat: a candidate teammate must have played in this share of the player's Matches.
MIN_CO_APPEARANCE = 0.5
# Understat: the co-appearance rule also asks this share and this minutes agreement, since
# teammates co-appear too and names can be contained in one another.
RULE_CO_APPEARANCE = 0.9
RULE_MINUTES_DIFFERENCE = 5.0
# Sofascore and Understat count stoppage time differently; past this, minutes disagree.
MINUTES_SCALE = 30.0
# Fuzzy proposals: the runner-up must stay this far below the best to accept the best.
FUZZY_MARGIN = 0.1


class Method:
    SOFASCORE_ANCHOR = "sofascore_anchor"
    NAME_BIRTH_DATE = "name_birth_date"
    CO_APPEARANCE = "co_appearance"
    FUZZY = "fuzzy"


@dataclass(frozen=True)
class SourcePlayer:
    source_record_id: int
    name: str
    birth_date: date | None = None


@dataclass(frozen=True)
class Appearance:
    """A player's minutes in a canonical Match, for a canonical Club."""

    match_id: str
    club_id: str
    player_id: int
    minutes: int


@dataclass(frozen=True)
class Proposal:
    """A proposed link from a Source Record to the Sofascore player that anchors a Player."""

    source_record_id: int
    sofascore_player_id: int
    method: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict[str, Any])

    @property
    def accepted(self) -> bool:
        return self.confidence >= ACCEPT_FROM


def transfermarkt_proposals(
    transfermarkt: Iterable[SourcePlayer], sofascore: Iterable[SourcePlayer]
) -> list[Proposal]:
    """Same birth date and the same name: a link. Same birth date and a similar name (a
    nickname, a transliteration): left to the judge. Same birth date only: no proposal."""
    by_birth_date: dict[date, list[SourcePlayer]] = defaultdict(list)
    for player in sofascore:
        if player.birth_date is not None:
            by_birth_date[player.birth_date].append(player)
    proposals: list[Proposal] = []
    for player in transfermarkt:
        if player.birth_date is None:
            continue
        scored = sorted(
            (
                (similarity(player.name, other.name), other)
                for other in by_birth_date[player.birth_date]
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        if not scored or scored[0][0] < JUDGE_FROM:
            continue
        name_score, best = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        evidence = {
            "name": player.name,
            "candidate": best.name,
            "name_similarity": round(name_score, 3),
        }
        if name_score >= SAME_NAME and runner_up < SAME_NAME:
            proposals.append(
                Proposal(
                    player.source_record_id,
                    best.source_record_id,
                    Method.NAME_BIRTH_DATE,
                    1.0,
                    evidence,
                )
            )
        else:
            # Below ACCEPT_FROM whatever the name score, so the judge decides.
            confidence = min(name_score, ACCEPT_FROM - 0.01)
            proposals.append(
                Proposal(
                    player.source_record_id,
                    best.source_record_id,
                    Method.FUZZY,
                    confidence,
                    evidence,
                )
            )
    return proposals


@dataclass(frozen=True)
class _Candidate:
    sofascore_player_id: int
    name_similarity: float
    co_appearance: float  # share of the Understat player's Matches it also played
    minutes_difference: float  # mean, over those Matches

    @property
    def score(self) -> float:
        minutes_agreement = 1 - min(self.minutes_difference, MINUTES_SCALE) / MINUTES_SCALE
        return 0.5 * self.name_similarity + 0.3 * self.co_appearance + 0.2 * minutes_agreement


def understat_proposals(
    understat: Sequence[Appearance],
    sofascore: Sequence[Appearance],
    understat_names: dict[int, str],
    sofascore_names: dict[int, str],
) -> list[Proposal]:
    """Link an Understat player to the Sofascore teammate who played the same Matches for
    the same Club, chosen by name.

    The co-appearance rule links outright when the names match and the minutes agree. Any
    other candidate is scored on name, co-appearance and minutes: a clear best links as
    fuzzy, a close or weaker one is left to the judge.
    """
    sofascore_minutes: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)
    for appearance in sofascore:
        sofascore_minutes[(appearance.match_id, appearance.club_id)][appearance.player_id] = (
            appearance.minutes
        )
    by_player: dict[int, list[Appearance]] = defaultdict(list)
    for appearance in understat:
        by_player[appearance.player_id].append(appearance)

    proposals: list[Proposal] = []
    for player_id, appearances in sorted(by_player.items()):
        differences: dict[int, list[int]] = defaultdict(list)
        for appearance in appearances:
            for teammate, minutes in sofascore_minutes[
                (appearance.match_id, appearance.club_id)
            ].items():
                differences[teammate].append(abs(minutes - appearance.minutes))
        name = understat_names[player_id]
        candidates = sorted(
            (
                _Candidate(
                    teammate,
                    similarity(name, sofascore_names[teammate]),
                    len(diffs) / len(appearances),
                    sum(diffs) / len(diffs),
                )
                for teammate, diffs in differences.items()
                if len(diffs) / len(appearances) >= MIN_CO_APPEARANCE
            ),
            key=lambda candidate: candidate.score,
            reverse=True,
        )
        if not candidates:
            continue
        best = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        evidence = {
            "name": name,
            "candidate": sofascore_names[best.sofascore_player_id],
            "name_similarity": round(best.name_similarity, 3),
            "co_appearance": round(best.co_appearance, 3),
            "minutes_difference": round(best.minutes_difference, 1),
            "matches": len(appearances),
        }
        same_name_teammates = sum(1 for c in candidates if c.name_similarity >= SAME_NAME)
        if (
            best.name_similarity >= SAME_NAME
            and same_name_teammates == 1
            and best.co_appearance >= RULE_CO_APPEARANCE
            and best.minutes_difference <= RULE_MINUTES_DIFFERENCE
        ):
            method, confidence = Method.CO_APPEARANCE, 1.0
        else:
            method, confidence = Method.FUZZY, round(best.score, 3)
            if runner_up is not None and best.score - runner_up.score < FUZZY_MARGIN:
                confidence = min(confidence, ACCEPT_FROM - 0.01)
                evidence["runner_up"] = sofascore_names[runner_up.sofascore_player_id]
            if confidence < JUDGE_FROM:
                continue
        proposals.append(
            Proposal(player_id, best.sofascore_player_id, method, confidence, evidence)
        )
    return proposals
