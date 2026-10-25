from datetime import date
from typing import Any

import pytest
from psycopg import AsyncConnection

from football_intel.identity.names import normalize, similarity
from football_intel.identity.rules import (
    ACCEPT_FROM,
    JUDGE_FROM,
    Appearance,
    Method,
    Proposal,
    SourcePlayer,
    transfermarkt_proposals,
    understat_proposals,
)
from football_intel.identity.store import IdentityStore

BORN = date(1999, 5, 1)


def test_names_compare_without_accents_punctuation_or_word_order() -> None:
    assert normalize("Đorđe Petrović") == "dorde petrovic"
    assert normalize("Max Weiß") == "max weiss"
    assert normalize("Jean-Mattéo Bahoya") == "jean matteo bahoya"
    assert similarity("Konsa Ngoyo, Ezri", "Ezri Konsa") == 1.0
    assert similarity("Andrew Robertson", "Andy Robertson") < 0.9


def test_transfermarkt_links_on_birth_date_and_the_same_name() -> None:
    sofascore = [SourcePlayer(1, "Djordje Petrović", BORN), SourcePlayer(2, "Someone Else", BORN)]

    (proposal,) = transfermarkt_proposals([SourcePlayer(10, "Đorđe Petrović", BORN)], sofascore)

    assert (proposal.sofascore_player_id, proposal.method, proposal.confidence) == (
        1,
        Method.NAME_BIRTH_DATE,
        1.0,
    )
    assert proposal.accepted


def test_transfermarkt_leaves_a_nickname_to_the_judge() -> None:
    (proposal,) = transfermarkt_proposals(
        [SourcePlayer(10, "Andrew Robertson", BORN)], [SourcePlayer(1, "Andy Robertson", BORN)]
    )

    assert proposal.method == Method.FUZZY
    assert JUDGE_FROM <= proposal.confidence < ACCEPT_FROM


def test_transfermarkt_does_not_link_on_birth_date_alone() -> None:
    assert (
        transfermarkt_proposals(
            [SourcePlayer(10, "Tom McGill", BORN)], [SourcePlayer(1, "Jadon Sancho", BORN)]
        )
        == []
    )
    assert transfermarkt_proposals([SourcePlayer(10, "Tom McGill", None)], []) == []


def test_transfermarkt_leaves_two_same_named_players_to_the_judge() -> None:
    sofascore = [SourcePlayer(1, "Joe Smith", BORN), SourcePlayer(2, "Joe Smith", BORN)]

    (proposal,) = transfermarkt_proposals([SourcePlayer(10, "Joe Smith", BORN)], sofascore)

    assert not proposal.accepted


def _season(player_id: int, minutes: list[int], club: str = "arsenal") -> list[Appearance]:
    return [Appearance(f"m{i}", club, player_id, m) for i, m in enumerate(minutes)]


def test_understat_links_the_same_named_teammate_who_played_the_same_minutes() -> None:
    understat = _season(100, [90, 90, 80, 90])
    sofascore = _season(1, [90, 90, 81, 90]) + _season(2, [90, 90, 90, 90])

    (proposal,) = understat_proposals(
        understat, sofascore, {100: "Ezri Konsa Ngoyo"}, {1: "Ezri Konsa", 2: "Ollie Watkins"}
    )

    assert (proposal.sofascore_player_id, proposal.method, proposal.confidence) == (
        1,
        Method.CO_APPEARANCE,
        1.0,
    )


def test_understat_does_not_link_a_contained_name_whose_minutes_disagree() -> None:
    # "Gabriel" is contained in "Gabriel Martinelli", but the minutes are Gabriel
    # Magalhães's: the co-appearance rule must not pick Martinelli.
    understat = _season(100, [90, 90, 90, 90])
    sofascore = _season(1, [60, 45, 70, 30]) + _season(2, [90, 90, 90, 90])

    (proposal,) = understat_proposals(
        understat, sofascore, {100: "Gabriel"}, {1: "Gabriel Martinelli", 2: "Gabriel Magalhães"}
    )

    assert proposal.sofascore_player_id == 2
    assert proposal.method == Method.FUZZY


def test_understat_does_not_link_a_lone_contained_name_whose_minutes_disagree() -> None:
    # Only Martinelli is in the Sofascore data: the name contains "Gabriel" and he played
    # every Match, but his minutes are not this player's.
    understat = _season(100, [90, 90, 90, 90])
    sofascore = _season(1, [60, 45, 70, 30])

    (proposal,) = understat_proposals(
        understat, sofascore, {100: "Gabriel"}, {1: "Gabriel Martinelli"}
    )

    assert proposal.method == Method.FUZZY
    assert not proposal.accepted


def test_understat_scores_a_nickname_on_name_co_appearance_and_minutes() -> None:
    understat = _season(100, [90] * 10)
    sofascore = _season(1, [90] * 10) + _season(2, [90] * 10)

    (proposal,) = understat_proposals(
        understat, sofascore, {100: "Matthew Cash"}, {1: "Matty Cash", 2: "Ollie Watkins"}
    )

    assert (proposal.sofascore_player_id, proposal.method) == (1, Method.FUZZY)
    assert proposal.accepted


def test_understat_ignores_players_of_another_club_and_rare_teammates() -> None:
    understat = _season(100, [90] * 4)
    # Same name, other club; and a teammate in only one of the four Matches.
    sofascore = [*_season(1, [90] * 4, club="chelsea"), Appearance("m0", "arsenal", 2, 90)]

    assert (
        understat_proposals(
            understat, sofascore, {100: "Joe Smith"}, {1: "Joe Smith", 2: "Joe Smith"}
        )
        == []
    )


@pytest.fixture
async def identity(connection: AsyncConnection[Any]) -> IdentityStore:
    await connection.execute(
        "TRUNCATE identity.identity_candidates, identity.players RESTART IDENTITY"
    )
    return IdentityStore(connection)


async def _candidates(connection: AsyncConnection[Any]) -> list[tuple[Any, ...]]:
    cursor = await connection.execute(
        "SELECT source, source_record_id, player_id, method, status"
        " FROM identity.identity_candidates ORDER BY candidate_id"
    )
    return await cursor.fetchall()


async def test_a_rerun_keeps_player_ids_and_adds_no_candidates(
    identity: IdentityStore, connection: AsyncConnection[Any]
) -> None:
    proposals = [Proposal(10, 1, Method.NAME_BIRTH_DATE, 1.0), Proposal(11, 2, Method.FUZZY, 0.7)]
    players, created = await identity.anchor_sofascore([1, 2])
    await identity.propose("transfermarkt", proposals, players)
    first = await _candidates(connection)

    players_again, created_again = await identity.anchor_sofascore([1, 2, 3])
    stored_again = await identity.propose("transfermarkt", proposals, players_again)

    assert (created, created_again, stored_again) == (2, 1, 0)
    assert {k: players_again[k] for k in players} == players
    assert await _candidates(connection) == [
        *first,
        ("sofascore", "3", 3, "sofascore_anchor", "accepted"),
    ]
    assert first == [
        ("sofascore", "1", 1, "sofascore_anchor", "accepted"),
        ("sofascore", "2", 2, "sofascore_anchor", "accepted"),
        ("transfermarkt", "10", 1, "name_birth_date", "accepted"),
        ("transfermarkt", "11", 2, "fuzzy", "pending"),
    ]


async def test_a_rejected_candidate_is_not_proposed_again(
    identity: IdentityStore, connection: AsyncConnection[Any]
) -> None:
    players, _ = await identity.anchor_sofascore([1])
    await identity.propose("understat", [Proposal(100, 1, Method.FUZZY, 0.7)], players)
    await connection.execute(
        "UPDATE identity.identity_candidates SET status = 'rejected' WHERE source = 'understat'"
    )

    stored = await identity.propose(
        "understat", [Proposal(100, 1, Method.CO_APPEARANCE, 1.0)], players
    )

    assert stored == 0
    assert (await _candidates(connection))[-1] == ("understat", "100", 1, "fuzzy", "rejected")


async def test_a_second_link_to_a_player_from_one_source_waits_for_the_judge(
    identity: IdentityStore, connection: AsyncConnection[Any]
) -> None:
    players, _ = await identity.anchor_sofascore([1])

    await identity.propose(
        "transfermarkt",
        [
            Proposal(10, 1, Method.NAME_BIRTH_DATE, 1.0),
            Proposal(11, 1, Method.NAME_BIRTH_DATE, 1.0),
        ],
        players,
    )

    assert [row[4] for row in await _candidates(connection)] == ["accepted", "accepted", "pending"]
