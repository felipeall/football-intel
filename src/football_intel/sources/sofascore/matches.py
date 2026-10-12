"""One finished Sofascore Match: every response we need from it, fetched through a transport."""

from dataclasses import dataclass
from typing import Any

import httpx

BASE_URL = "https://www.sofascore.com/api/v1"
TIMEOUT_SECONDS = 30.0
# Per Match, after the event and its lineups (per-player statistics: Appearances): the
# shotmap (Shots) and average positions. Per player who appeared: heatmap and rating
# breakdown (Actions).
MATCH_PATHS = ("/shotmap", "/average-positions")
PLAYER_PATHS = ("/heatmap", "/rating-breakdown")


class MatchNotFound(Exception):
    """Sofascore has no such event, or no lineups for it."""


class MatchNotFinished(Exception):
    """The event exists but is not finished, so its data is not final."""


class UpstreamError(Exception):
    """Sofascore refused or failed a request (403, 429, 5xx…). Retryable."""

    def __init__(self, url: httpx.URL, status_code: int) -> None:
        super().__init__(f"Sofascore answered {status_code} for {url.path}")
        self.status_code = status_code


@dataclass(frozen=True)
class MatchResponses:
    """What one Match ingest received: every request path with its status code."""

    event_id: int
    name: str  # "Home v Away"
    # Players with minutes in the Match, in lineup order: home, then away.
    player_ids: tuple[int, ...]
    statuses: dict[str, int]


async def fetch_match(transport: httpx.AsyncBaseTransport, event_id: int) -> MatchResponses:
    """Request everything we need from one finished Match through `transport`.

    A 404 for the event or its lineups raises `MatchNotFound`. A 404 for the shotmap, average
    positions, or one player's heatmap or rating breakdown is a normal answer (little data,
    few minutes played): it is kept and the Match goes on.
    """
    statuses: dict[str, int] = {}
    async with httpx.AsyncClient(
        transport=transport, base_url=BASE_URL, timeout=TIMEOUT_SECONDS
    ) as client:

        async def get(path: str, required: bool = False) -> httpx.Response:
            response = await client.get(path)
            statuses[path] = response.status_code
            if response.status_code == 404 and required:
                raise MatchNotFound(f"Sofascore has no {path}")
            if response.is_error and response.status_code != 404:
                raise UpstreamError(response.request.url, response.status_code)
            return response

        match = f"/event/{event_id}"
        event = (await get(match, required=True)).json()["event"]
        if event["status"]["type"] != "finished":
            raise MatchNotFinished(f"Event {event_id} is {event['status']['type']}")
        lineups = (await get(f"{match}/lineups", required=True)).json()
        for path in MATCH_PATHS:
            await get(f"{match}{path}")
        player_ids = _appeared(lineups)
        for player_id in player_ids:
            for path in PLAYER_PATHS:
                await get(f"{match}/player/{player_id}{path}")

    return MatchResponses(
        event_id=event_id,
        name=f"{event['homeTeam']['name']} v {event['awayTeam']['name']}",
        player_ids=player_ids,
        statuses=statuses,
    )


def _appeared(lineups: dict[str, Any]) -> tuple[int, ...]:
    """Players with minutes played. Unused substitutes have no heatmap or rating breakdown."""
    return tuple(
        entry["player"]["id"]
        for side in ("home", "away")
        for entry in lineups[side]["players"]
        if entry.get("statistics", {}).get("minutesPlayed")
    )
