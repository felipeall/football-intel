"""A synthetic Transfermarkt JSON API for tests. No scraped data (ADR 4): every value is made up.

Club 1 has three players. Player 103 has no transfer history, so upstream answers 404,
which the SDK tolerates and the recording transport must still store.
"""

import json
from typing import Any

import httpx

CLUB_ID = "1"
SEASON_ID = "2025"
PLAYER_IDS = ("101", "102", "103")
PREVIOUS_CLUB_ID = "2"


def _player(player_id: str, name: str, position: str) -> dict[str, Any]:
    return {
        "id": int(player_id),
        "name": name,
        "portraitUrl": None,
        "attributes": {
            "position": {"name": position},
            "preferredFoot": {"name": "right"},
            "height": 1.85,
            "contractUntil": "2028-06-30",
        },
        "lifeDates": {"dateOfBirth": "2000-01-01", "age": 25},
        "nationalityDetails": {"nationalities": {"nationalityId": 1}},
        "marketValueDetails": {"current": {"value": 10_000_000, "currency": "EUR"}},
        "clubAssignments": [{"type": "current", "clubId": int(CLUB_ID), "start": "2024-07-01"}],
    }


PLAYERS = {
    "101": _player("101", "Alex Keeper", "Goalkeeper"),
    "102": _player("102", "Sam Back", "Left-Back"),
    "103": _player("103", "Jo Forward", "Centre-Forward"),
}
HISTORY = {
    "history": {
        "terminated": [
            {
                "transferDestination": {"clubId": int(CLUB_ID)},
                "transferSource": {"clubId": int(PREVIOUS_CLUB_ID)},
                "details": {"date": "2024-07-01T00:00:00", "seasonId": 2024},
            }
        ]
    }
}
ATTRIBUTES = {
    "countries": [{"id": 1, "name": "Testland"}],
    "confederations": [],
    "competitionTypes": [],
    "contracts": [],
    "positions": [],
}


def _ok(data: Any) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "data": data})


class TransfermarktStub:
    """Handler for `httpx.MockTransport`. Records every request it answers."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        ids = request.url.params.get_list("ids[]")
        if path == f"/club/{CLUB_ID}/squad":
            members = [
                {"playerId": int(i), "type": "current", "shirtNumber": n, "isCaptain": n == 1}
                for n, i in enumerate(PLAYER_IDS, start=1)
            ]
            return _ok({"squad": members})
        if path == "/attributes":
            return _ok(ATTRIBUTES)
        if path == "/players":
            return _ok([PLAYERS[i] for i in ids if i in PLAYERS])
        if path == "/clubs":
            return _ok([{"id": int(i), "name": f"Club {i}"} for i in ids])
        if path.startswith("/transfer/history/player/"):
            if path.endswith("/103"):
                return httpx.Response(404, content=json.dumps({"success": False}).encode())
            return _ok(HISTORY)
        return httpx.Response(404, json={"success": False})
