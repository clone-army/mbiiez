import concurrent.futures
import json
import secrets
import pytest
from mbiiez.api import shared_ledger as ledger


def item(kind, **fields):
    return dict(id=secrets.token_hex(16), kind=kind, **fields)


@pytest.fixture
def shared(tmp_path, monkeypatch):
    monkeypatch.setenv("MBIIEZ_STATE_DIR", str(tmp_path))
    ledger.seed(
        {
            "datasets": {
                "accounts": [["Player", "a" * 32, "b" * 32, 100, 0, 0]],
                "stats": [["h:Player", 10, 2, 0, 100]],
            }
        }
    )
    return tmp_path


def balance():
    with ledger.transaction() as db:
        return ledger.get(db, "accounts", "player")[3]


def test_earn_spend_both_regions_and_idempotent_retry(shared):
    earn = item("credit", handle="Player", amount=20)
    ledger.apply("na", [earn])
    ledger.apply("na", [earn])
    spend = item("reserve", changes=[dict(handle="player", amount=30)])
    ledger.apply("eu", [spend])
    ledger.apply("eu", [spend])
    commit = item("commit", reservation=spend["id"])
    ledger.apply("eu", [commit])
    ledger.apply("eu", [commit])
    assert balance() == 90
    a = item("stats", key="h:Player", delta=[3, 0, 0, 60])
    b = item("stats", key="h:player", delta=[2, 1, 0, 30])
    ledger.apply("na", [a])
    ledger.apply("eu", [b])
    ledger.apply("eu", [b])
    with ledger.transaction() as db:
        assert ledger.get(db, "stats", "h:player") == ["h:Player", 15, 3, 0, 190]


def test_simultaneous_spending_cannot_overdraw(shared):
    def spend(peer):
        try:
            ledger.apply(
                peer, [item("reserve", changes=[dict(handle="Player", amount=80)])]
            )
            return True
        except ValueError:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(spend, ["na", "eu"]))
    assert sum(results) == 1 and balance() == 20


def test_lost_response_cancel_fences_late_request(shared):
    reserve = item("reserve", changes=[dict(handle="Player", amount=30)])
    ledger.apply("eu", [reserve])
    assert balance() == 70
    cancel = item("cancel", reservation=reserve["id"])
    ledger.apply("eu", [cancel])
    ledger.apply("eu", [cancel])
    assert balance() == 100
    early = item("reserve", changes=[dict(handle="Player", amount=20)])
    ledger.apply("eu", [item("cancel", reservation=early["id"])])
    with pytest.raises(ValueError):
        ledger.apply("eu", [early])
    assert balance() == 100


def test_commit_never_refunded_by_late_cancel_and_transfer_atomic(shared):
    ledger.apply(
        "na",
        [item("join", datasets={"accounts": [["Other", "c" * 32, "d" * 32, 0, 0, 0]]})],
    )
    reserve = item(
        "reserve", changes=[dict(handle="Player", amount=30, recipient="Other")]
    )
    ledger.apply("eu", [reserve])
    ledger.apply("eu", [item("commit", reservation=reserve["id"])])
    ledger.apply("eu", [item("cancel", reservation=reserve["id"])])
    assert balance() == 70
    with ledger.transaction() as db:
        assert ledger.get(db, "accounts", "other")[3] == 30


def test_migration_preserves_local_and_missing_accounts(shared):
    result = ledger.apply(
        "eu",
        [
            item(
                "join",
                datasets={
                    "accounts": [
                        ["Player", "c" * 32, "d" * 32, 200, 0, 0],
                        ["EUOnly", "e" * 32, "f" * 32, 25, 0, 0],
                    ],
                    "stats": [["h:Player", 100, 2, 0, 1000], ["h:EUOnly", 5, 1, 0, 20]],
                },
            )
        ],
    )
    assert balance() == 100 and result["results"][0]["added"]["accounts"] == 1
    with ledger.transaction() as db:
        assert ledger.get(db, "stats", "h:player")[1] == 10
        assert ledger.get(db, "stats", "h:euonly")[1] == 5
    assert (
        ledger.seed(
            {"datasets": {"accounts": [["Player", "a" * 32, "b" * 32, 999, 0, 0]]}}
        )
        is False
    )


def test_unban_tombstone_blocks_stale_peer_and_aliases(shared):
    guid = "A" * 32
    other = "B" * 32
    root = [guid, 0, 0, "Player", "1.2.3.4", 1, "", "test"]
    child = [
        other,
        0,
        0,
        "Player",
        "1.2.3.4",
        2,
        "",
        f"same IP (1.2.3.4) as banned {guid}",
    ]
    result = ledger.apply(
        "na", [item("ban_set", dataset="guid_bans", row=root, base_revision=0)]
    )
    revision = result["snapshot"]["revision"]
    result = ledger.apply(
        "eu", [item("ban_set", dataset="guid_bans", row=child, base_revision=revision)]
    )
    latest = result["snapshot"]["revision"]
    ledger.apply(
        "na", [item("ban_delete", dataset="guid_bans", key=guid, base_revision=latest)]
    )
    result = ledger.apply(
        "eu", [item("ban_set", dataset="guid_bans", row=root, base_revision=revision)]
    )
    assert (
        result["results"][0]["skipped"]
        and not result["snapshot"]["datasets"]["guid_bans"]
    )


def test_credentials_shared_and_daily_bonus_once(shared):
    registered = item("register", handle="New", pin="1234", bonus=50)
    ledger.apply("eu", [registered])
    logged = ledger.apply("na", [item("login", handle="New", pin="1234", bonus=20)])
    assert logged["results"][0]["credits"] == 50  # welcome bonus already claimed today
    ledger.apply("na", [item("account_edit", handle="New", action="pin", pin="5678")])
    bad = ledger.apply("eu", [item("login", handle="New", pin="1234", bonus=20)])
    assert "error" in bad["results"][0]
    assert (
        ledger.apply("eu", [item("login", handle="New", pin="5678", bonus=20)])[
            "results"
        ][0]["credits"]
        == 50
    )


def test_peer_key_hash_and_revocation(shared):
    token = ledger.enroll("eu")
    assert ledger.verify("eu", token)
    assert not ledger.verify("eu", "wrong")
    with ledger.transaction() as db:
        assert token not in json.dumps(db.execute("SELECT * FROM peers").fetchall())
    ledger.disable("eu")
    assert not ledger.verify("eu", token)


def test_journal_watermarks_exact_once_and_atomic_kill(shared):
    epoch = secrets.token_hex(16)
    batch = item(
        "stats_batch",
        rows=[
            {"key": "h:Player", "delta": [1, 0, 0, 0]},
            {"key": "h:Victim", "delta": [0, 1, 0, 0]},
        ],
        journal_epoch=epoch,
        journal_sequence=100,
    )
    ledger.apply("eu", [batch])
    ledger.apply("eu", [batch])
    with ledger.transaction() as db:
        assert ledger.get(db, "stats", "h:player")[1] == 11
        assert ledger.get(db, "stats", "h:victim")[2] == 1
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0
    invalid = item(
        "stats_batch",
        rows=[
            {"key": "h:Player", "delta": [2, 0, 0, 0]},
            {"key": "bad|key", "delta": [0, 1, 0, 0]},
        ],
    )
    with pytest.raises(ValueError):
        ledger.apply("na", [invalid])
    with ledger.transaction() as db:
        assert ledger.get(db, "stats", "h:player")[1] == 11


def test_enrollment_does_not_resurrect_unbans(shared):
    guid = "A" * 32
    row = [guid, 0, 0, "Player", "1.2.3.4", 1, "", ""]
    result = ledger.apply(
        "na", [item("ban_set", dataset="guid_bans", row=row, base_revision=0)]
    )
    ledger.apply(
        "na",
        [
            item(
                "ban_delete",
                dataset="guid_bans",
                key=guid,
                base_revision=result["snapshot"]["revision"],
            )
        ],
    )
    result = ledger.apply("new", [item("join", datasets={"guid_bans": [row]})])
    assert result["snapshot"]["datasets"]["guid_bans"] == []
