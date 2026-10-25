"""The Reep loader and the Reep step of Identity Resolution, on a synthetic release. No Reep
data is committed (ADR 4): every bridge here is made up."""

import hashlib
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pytest
from psycopg import AsyncConnection
from temporalio.exceptions import ApplicationError

from football_intel.identity.activities import _reep_bridges  # pyright: ignore[reportPrivateUsage]
from football_intel.identity.rules import Method, Proposal, ReepBridge, reep_proposals
from football_intel.identity.store import IdentityStore
from football_intel.reep import load, release

RELEASE = "2026-01-02.1"
PREVIOUS = "2026-01-01.1"

# Person A: Sofascore 1, Transfermarkt 10, Understat 100. Person B was merged into A (a
# redirect), and still carries A's second Transfermarkt bridge. Person C has no Sofascore
# bridge, so it is not loaded. A team bridge and another namespace are noise.
BRIDGES = [
    ("rA", "sofascore", "player", "1", "player"),
    ("rA", "transfermarkt", "spieler", "10", "player"),
    ("rB", "understat", "player", "100", "player"),
    ("rC", "transfermarkt", "spieler", "30", "player"),
    ("rA", "transfermarkt", "verein", "11", "team"),
    ("rT", "sofascore", "team", "42", "team"),
]
REDIRECTS = [("rB", "rA")]


def _write_release(directory: Path) -> dict[str, bytes]:
    directory.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as db:
        db.execute(
            "CREATE TABLE b (reep_id text, provider text, namespace text, external_id text,"
            " entity_type text, rule_id text, route_scope text)"
        )
        db.executemany("INSERT INTO b VALUES (?, ?, ?, ?, ?, 'rule', 'scope')", BRIDGES)
        db.execute("CREATE TABLE r (from_id text, to_id text)")
        db.executemany("INSERT INTO r VALUES (?, ?)", REDIRECTS)
        db.execute(f"COPY b TO '{directory / 'bridges.parquet'}' (FORMAT parquet)")
        db.execute(f"COPY r TO '{directory / 'redirects.parquet'}' (FORMAT parquet)")
    return {name: (directory / name).read_bytes() for name in release.FILES}


def _manifest(files: dict[str, bytes], previous: str | None = PREVIOUS) -> dict[str, Any]:
    return {
        "release_tag": RELEASE,
        "checksums_sha256": {
            name: hashlib.sha256(body).hexdigest() for name, body in files.items()
        },
        "gates": {"gate_passed": False},
        "diff": {
            "previous_label": previous,
            "new_bridges_by_provider": {"transfermarkt": 5},
            "id_retention_pct": 100.0,
        },
    }


class ReepStub:
    """Serves releases like data.reep.football, and records every request."""

    def __init__(self, releases: dict[str, tuple[dict[str, Any], dict[str, bytes]]], latest: str):
        self.releases = releases
        self.latest = latest
        self.requests: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/releases")
        self.requests.append(path)
        if path == "/latest.json":
            return httpx.Response(200, json={"stamp": self.latest})
        stamp, name = path.strip("/").split("/")
        manifest, files = self.releases[stamp]
        if name == "manifest.json":
            return httpx.Response(200, json=manifest)
        return httpx.Response(200, content=files[name])

    def client(self) -> httpx.AsyncClient:
        return release.client(httpx.MockTransport(self.handle))


async def test_a_release_downloads_once_verified(tmp_path: Path) -> None:
    files = _write_release(tmp_path / "source")
    stub = ReepStub({RELEASE: (_manifest(files), files)}, RELEASE)
    target = tmp_path / RELEASE

    async with stub.client() as api:
        manifest = await release.download(api, RELEASE, target)
        await release.download(api, RELEASE, target)

    assert manifest.gate_passed is False
    assert (target / "manifest.json").exists()
    # The second run finds both files verified and fetches only the manifest.
    assert stub.requests.count(f"/{RELEASE}/bridges.parquet") == 1


async def test_a_checksum_mismatch_stops_the_download(tmp_path: Path) -> None:
    files = _write_release(tmp_path / "source")
    corrupt = {**files, "bridges.parquet": b"not the published file"}
    stub = ReepStub({RELEASE: (_manifest(files), corrupt)}, RELEASE)

    with pytest.raises(release.ChecksumMismatchError):
        async with stub.client() as api:
            await release.download(api, RELEASE, tmp_path / RELEASE)

    assert not (tmp_path / RELEASE / "bridges.parquet").exists()
    assert not (tmp_path / RELEASE / "bridges.parquet.partial").exists()


async def test_status_walks_back_from_the_current_release_to_the_pinned_one(
    tmp_path: Path,
) -> None:
    files = _write_release(tmp_path / "source")
    newest = {**_manifest(files, previous=RELEASE), "release_tag": "2026-01-03.1"}
    stub = ReepStub(
        {"2026-01-03.1": (newest, files), RELEASE: (_manifest(files), files)}, "2026-01-03.1"
    )

    async with stub.client() as api:
        newer = await release.releases_since(api, PREVIOUS)
        none_newer = await release.releases_since(api, "2026-01-03.1")

    assert [m.release for m in newer] == ["2026-01-03.1", RELEASE]
    assert newer[0].new_bridges == {"transfermarkt": 5}
    assert none_newer == []
    assert not any(path.endswith(".parquet") for path in stub.requests)


def test_only_players_with_a_sofascore_bridge_load_with_redirects_resolved(
    tmp_path: Path,
) -> None:
    _write_release(tmp_path)

    bridges = load.player_bridges(tmp_path)

    assert [(reep_id, provider, external_id) for reep_id, provider, external_id, *_ in bridges] == [
        ("rA", "sofascore", "1"),
        ("rA", "transfermarkt", "10"),
        ("rA", "understat", "100"),
    ]


@pytest.fixture
async def reference(connection: AsyncConnection[Any]) -> AsyncConnection[Any]:
    await connection.execute("TRUNCATE reference.reep_releases CASCADE")
    await connection.execute(
        "TRUNCATE identity.identity_candidates, identity.players RESTART IDENTITY"
    )
    return connection


async def test_reloading_a_release_replaces_its_rows(
    reference: AsyncConnection[Any], tmp_path: Path
) -> None:
    files = _write_release(tmp_path)
    manifest = release.Manifest(RELEASE, _manifest(files))
    bridges = load.player_bridges(tmp_path)

    await load.load(reference, manifest, bridges)
    await load.load(reference, manifest, bridges[:1])

    cursor = await reference.execute(
        "SELECT count(*), (SELECT gate_passed FROM reference.reep_releases)"
        " FROM reference.reep_player_bridges"
    )
    assert await cursor.fetchone() == (1, False)


async def test_bridges_of_a_release_not_loaded_fail_without_retries(
    reference: AsyncConnection[Any],
) -> None:
    with pytest.raises(ApplicationError) as error:
        await _reep_bridges(reference, RELEASE, "transfermarkt")

    assert error.value.non_retryable


async def test_bridges_map_each_source_to_sofascore(
    reference: AsyncConnection[Any], tmp_path: Path
) -> None:
    files = _write_release(tmp_path)
    await load.load(
        reference, release.Manifest(RELEASE, _manifest(files)), load.player_bridges(tmp_path)
    )

    assert await _reep_bridges(reference, RELEASE, "transfermarkt") == [
        ReepBridge(10, 1, "rule", "scope")
    ]
    assert await _reep_bridges(reference, RELEASE, "understat") == [
        ReepBridge(100, 1, "rule", "scope")
    ]


def test_reep_links_only_records_we_hold_to_one_sofascore_player() -> None:
    bridges = [
        ReepBridge(10, 1),
        ReepBridge(11, 2),  # we do not hold Transfermarkt 11
        ReepBridge(12, 99),  # we do not hold Sofascore 99
        ReepBridge(13, 1),  # Reep maps 13 to two of our Sofascore players: rules decide
        ReepBridge(13, 3),
    ]

    proposals = reep_proposals(RELEASE, bridges, held={10, 12, 13}, sofascore={1, 2, 3})

    assert [(p.source_record_id, p.sofascore_player_id) for p in proposals] == [(10, 1)]
    (proposal,) = proposals
    assert (proposal.method, proposal.decided_by, proposal.accepted) == (
        Method.REEP_BRIDGE,
        f"reep:{RELEASE}",
        True,
    )


async def _statuses(connection: AsyncConnection[Any]) -> list[tuple[Any, ...]]:
    cursor = await connection.execute(
        "SELECT source_record_id, player_id, method, status, decided_by"
        " FROM identity.identity_candidates WHERE source = 'transfermarkt' ORDER BY candidate_id"
    )
    return await cursor.fetchall()


async def test_reep_decides_first_and_the_rules_skip_what_it_linked(
    reference: AsyncConnection[Any],
) -> None:
    store = IdentityStore(reference)
    players, _ = await store.anchor_sofascore([1, 2])

    await store.propose(
        "transfermarkt", reep_proposals(RELEASE, [ReepBridge(10, 1)], {10}, {1, 2}), players
    )
    stored = await store.propose(
        "transfermarkt",
        [
            Proposal(10, 2, Method.NAME_BIRTH_DATE, 1.0),
            Proposal(11, 2, Method.NAME_BIRTH_DATE, 1.0),
        ],
        players,
    )

    assert stored == 1
    assert await _statuses(reference) == [
        ("10", 1, "reep_bridge", "accepted", f"reep:{RELEASE}"),
        ("11", 2, "name_birth_date", "accepted", "rule:name_birth_date"),
    ]


async def test_a_rejected_reep_link_reopens_its_record_to_the_rules(
    reference: AsyncConnection[Any],
) -> None:
    store = IdentityStore(reference)
    players, _ = await store.anchor_sofascore([1, 2])
    await store.propose(
        "transfermarkt", reep_proposals(RELEASE, [ReepBridge(10, 1)], {10}, {1, 2}), players
    )
    await reference.execute(
        "UPDATE identity.identity_candidates SET status = 'rejected' WHERE method = 'reep_bridge'"
    )

    # The same wrong link again is not stored; the rules' own link is.
    stored = await store.propose(
        "transfermarkt",
        [Proposal(10, 1, Method.FUZZY, 0.95), Proposal(10, 2, Method.NAME_BIRTH_DATE, 1.0)],
        players,
    )

    assert stored == 1
    assert await _statuses(reference) == [
        ("10", 1, "reep_bridge", "rejected", f"reep:{RELEASE}"),
        ("10", 2, "name_birth_date", "accepted", "rule:name_birth_date"),
    ]


async def test_a_newer_release_changes_no_existing_candidate(
    reference: AsyncConnection[Any],
) -> None:
    store = IdentityStore(reference)
    players, _ = await store.anchor_sofascore([1, 2])
    await store.propose(
        "transfermarkt", reep_proposals(RELEASE, [ReepBridge(10, 1)], {10}, {1, 2}), players
    )
    before = await _statuses(reference)

    # The newer release maps 10 elsewhere; the existing link stays.
    stored = await store.propose(
        "transfermarkt", reep_proposals("2026-01-03.1", [ReepBridge(10, 2)], {10}, {1, 2}), players
    )

    assert stored == 0
    assert await _statuses(reference) == before
