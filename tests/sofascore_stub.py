"""A synthetic Sofascore web API for tests. No scraped data (ADR 4): every value is made up.

Event 1001 is a finished Match. Players 11 and 12 (home) and 21 and 22 (away) played; 13 sat
on the bench, so it has no minutes and no heatmap. Player 22 came on late: its heatmap
answers 404, which is normal and must not fail the Match. Event 1002 has not started. Any
other event answers 404.
"""

from typing import Any

import httpx

EVENT_ID = 1001
NOT_STARTED_EVENT_ID = 1002
PLAYED = (11, 12, 21, 22)
BENCHED = 13
NO_HEATMAP = 22
BASE = "/api/v1/event"


def _entry(player_id: int, minutes: int | None) -> dict[str, Any]:
    statistics: dict[str, Any] = {"ratingVersions": {}}
    if minutes is not None:
        statistics |= {"minutesPlayed": minutes, "rating": 7.0}
    return {"player": {"id": player_id, "name": f"Player {player_id}"}, "statistics": statistics}


def _event(event_id: int, status: str) -> dict[str, Any]:
    return {
        "event": {
            "id": event_id,
            "status": {"type": status},
            "homeTeam": {"id": 1, "name": "Home FC"},
            "awayTeam": {"id": 2, "name": "Away FC"},
        }
    }


LINEUPS = {
    "home": {"players": [_entry(11, 90), _entry(12, 90), _entry(BENCHED, None)]},
    "away": {"players": [_entry(21, 90), _entry(22, 4)]},
}


class SofascoreStub:
    """Answers like Sofascore for the events above and records every request it receives."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        match = f"{BASE}/{EVENT_ID}"
        if path == f"{BASE}/{NOT_STARTED_EVENT_ID}":
            return httpx.Response(200, json=_event(NOT_STARTED_EVENT_ID, "notstarted"))
        if path == match:
            return httpx.Response(200, json=_event(EVENT_ID, "finished"))
        if path == f"{match}/lineups":
            return httpx.Response(200, json=LINEUPS)
        if path == f"{match}/shotmap":
            return httpx.Response(200, json={"shotmap": [{"player": {"id": 11}, "xg": 0.3}]})
        if path == f"{match}/average-positions":
            return httpx.Response(200, json={"home": [], "away": []})
        if path == f"{match}/player/{NO_HEATMAP}/heatmap":
            return _not_found()
        for player_id in PLAYED:
            if path == f"{match}/player/{player_id}/heatmap":
                return httpx.Response(200, json={"heatmap": [{"x": 50, "y": 50}]})
            if path == f"{match}/player/{player_id}/rating-breakdown":
                return httpx.Response(200, json={"passes": [], "dribbles": []})
        return _not_found()

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


def _not_found() -> httpx.Response:
    return httpx.Response(404, json={"error": {"code": 404, "message": "Not Found"}})
