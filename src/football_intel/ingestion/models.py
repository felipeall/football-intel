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


@dataclass(frozen=True)
class CompetitionClubsInput:
    competition_id: str
    season_id: str
    refresh: bool = False


@dataclass(frozen=True)
class CompetitionClubsResult:
    competition_id: str
    season_id: str
    club_ids: list[str]
    raw_responses: int
    reused: int


@dataclass(frozen=True)
class CompetitionSquadsInput:
    """Every club's squad in one competition season.

    `max_concurrent_clubs` caps the squads in flight: they share the source's rate limit, so
    more at once only makes each squad's activity take longer.
    """

    competition_id: str
    season_id: str
    refresh: bool = False
    max_concurrent_clubs: int = 3


@dataclass(frozen=True)
class CompetitionSquadsResult:
    competition_id: str
    season_id: str
    clubs: CompetitionClubsResult
    squads: list[SquadIngestResult]
    # Clubs whose squad workflow failed; the other clubs still ran to completion.
    failed_club_ids: list[str]


@dataclass(frozen=True)
class MatchIngestInput:
    """One finished Sofascore Match, by Sofascore event ID.

    `refresh` fetches every request from the source, even when a fresh Raw Response is stored.
    """

    event_id: int
    refresh: bool = False


@dataclass(frozen=True)
class MatchIngestResult:
    event_id: int
    name: str  # "Home v Away"
    players: int  # players who appeared
    # Requests answered by the source (each stored as a new Raw Response), and requests
    # answered by a fresh stored Raw Response instead.
    raw_responses: int
    reused: int

    @property
    def cache_hit(self) -> bool:
        """True when the run sent no request to the source."""
        return self.raw_responses == 0
