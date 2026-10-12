"""Workflow and activity inputs and results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SquadIngestInput:
    """One club's squad for one season; `season_id` is the season's start year, e.g. "2025".

    `refresh` fetches every request from the source, even when a fresh Raw Response is stored.
    """

    club_id: str
    season_id: str
    refresh: bool = False


@dataclass(frozen=True)
class SquadIngestResult:
    club_id: str
    season_id: str
    players: int
    # Requests answered by the source (each stored as a new Raw Response), and requests
    # answered by a fresh stored Raw Response instead.
    raw_responses: int
    reused: int

    @property
    def cache_hit(self) -> bool:
        """True when the run sent no request to the source."""
        return self.raw_responses == 0
