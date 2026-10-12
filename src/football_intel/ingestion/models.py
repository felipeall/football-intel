"""Workflow and activity inputs and results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SquadIngestInput:
    """One club's squad for one season; `season_id` is the season's start year, e.g. "2025"."""

    club_id: str
    season_id: str


@dataclass(frozen=True)
class SquadIngestResult:
    club_id: str
    season_id: str
    players: int
    raw_responses: int
