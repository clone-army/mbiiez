import hashlib
import json
import secrets
from pathlib import Path
import pytest
import requests
from mbiiez import settings, accounts_store, guidbans, bansync
from mbiiez.api import shared_node as node, shared_ledger as ledger, keys
from mbiiez.api.storage import read, write
from mbiiez.api.server import create_app


@pytest.fixture
def group(tmp_path, monkeypatch):
    home = tmp_path / "remote"
    hub = tmp_path / "hub"
    data = tmp_path / "MBII"
    data.mkdir()
    monkeypatch.setenv("MBIIEZ_STATE_DIR", str(home))
    monkeypatch.setattr(settings.locations, "mbii_path", str(data))
    monkeypatch.setattr(ledger, "state_dir", lambda: hub)
    monkeypatch.setattr(
        node, "safety", lambda: {"ready": True, "shared_protocol": 2, "note": ""}
    )
    monkeypatch.setattr(node.psutil, "process_iter", lambda *a, **kw: [])
    monkeypatch.setattr(bansync, "sync", lambda: [])
    ledger.seed(
        {
            "datasets": {
                "accounts": [["Player", "a" * 32, "b" * 32, 100, 0, 0]],
                "stats": [["h:Player", 10, 2, 0, 100]],
            },
            "admin_handles": ["Player"],
        }
    )
    (data / "economy_accounts.dat").write_text(
        "Player "
        + ("c" * 32)
        + " "
        + ("d" * 32)
        + " 200 0 0\nRemote "
        + ("e" * 32)
        + " "
        + ("f" * 32)
        + " 25 0 0\n"
    )
    (data / "player_stats.dat").write_text("h:Player|100|3|0|900\nh:Remote|5|1|0|30\n")
    (data / "economy_daily.dat").write_text("Remote 123\n")

    def post(url, json, **kwargs):
        result = ledger.apply(kwargs["headers"]["X-MBIIEZ-Peer"], json["events"])
        return type("Reply", (), {"ok": True, "json": lambda self: result})()

    monkeypatch.setattr(node.requests, "post", post)
    return home, hub, data, post


def current_balance(handle="player"):
    with ledger.transaction() as db:
        return ledger.get(db, "accounts", handle)[3]


def event(kind, **fields):
    return dict(id=secrets.token_hex(16), kind=kind, **fields)


def test_atomic_bootstrap_lost_reply_and_local_authority(group, monkeypatch):
    home, hub, data, post = group
    count = 0

    def lost(*args, **kwargs):
        nonlocal count
        count += 1
        result = post(*args, **kwargs)
        if count == 1:
            raise requests.Timeout("reply lost after commit")
        return result

    monkeypatch.setattr(node.requests, "post", lost)
    assert node.activate("eu", "https://panel.example.com", "t" * 40)["pending"]
    assert read(home / "shared_node.json", {})["bootstrap"]
    node.append(event("credit", handle="Player", amount=20))
    node.append(event("stats", key="h:Player", delta=[3, 0, 0, 60]))
    node.exchange()
    node.exchange()
    assert current_balance() == 120
    assert node.engine_operation({"kind": "balance", "handle": "player"}) == {
        "credits": 120
    }
    assert not read(home / "shared_node.json", {}).get("bootstrap")
    assert accounts_store.read_accounts()[0]["credits"] == 120
    assert accounts_store.read_admins() == {"player"}
    with ledger.transaction() as db:
        assert ledger.get(db, "stats", "h:player")[1] == 13
        assert ledger.get(db, "accounts", "remote")[3] == 25
    backups = list(home.glob("shared_initial_backups/*/snapshot.json"))
    assert len(backups) == 1 and "200" in backups[0].read_text()
    node.activate("eu", "https://panel.example.com", "t" * 40)
    assert len(list(home.glob("shared_initial_backups/*/snapshot.json"))) == 1


def test_bootstrap_is_one_transaction_and_recoverable(group, monkeypatch):
    home, hub, data, post = group

    def unavailable(*a, **kw):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(node.requests, "post", unavailable)
    node.activate("eu", "https://panel.example.com", "t" * 40)
    node.append(event("credit", handle="Player", amount=20))
    with ledger.transaction() as db:
        assert ledger.get(db, "accounts", "remote") is None
    monkeypatch.setattr(node.requests, "post", post)
    node.exchange()
    assert current_balance() == 120
    with ledger.transaction() as db:
        assert ledger.get(db, "accounts", "remote")[3] == 25


def test_admin_edits_and_unban_propagate_through_ledger(group):
    home, hub, data, post = group
    node.activate("eu", "https://panel.example.com", "t" * 40)
    assert accounts_store.add_credits("Player", 10)[0]
    assert current_balance() == 110
    assert accounts_store.set_pin("Player", "1234")[0]
    login = node.engine_operation(event("login", handle="Player", pin="1234", bonus=0))
    spend = event(
        "reserve", changes=[dict(handle="Player", amount=30, session=login["session"])]
    )
    assert node.engine_operation(spend)["balances"]["player"] == 80
    node.append(event("commit", reservation=spend["id"]))
    node.exchange()
    assert (
        accounts_store.set_admin("Player", False)[0]
        and not accounts_store.read_admins()
    )
    guid = "A" * 32
    assert guidbans.add_ban(guid, "test")[0]
    node.exchange()
    assert guidbans.list_bans()[0]["guid"] == guid
    assert guidbans.remove_ban(guid)[0]
    node.exchange()
    assert not guidbans.list_bans()
    assert accounts_store.delete_account("Remote")[0]
    with ledger.transaction() as db:
        assert ledger.get(db, "accounts", "remote") is None


def test_dead_process_reservation_is_refunded_once(group):
    home, hub, data, post = group
    node.activate("eu", "https://panel.example.com", "t" * 40)
    reserve = event("reserve", changes=[dict(handle="Player", amount=30)])
    node.append(dict(reserve, kind="intent", pid=2147483647, started="0"))
    ledger.apply("eu", [reserve])
    assert current_balance() == 70
    node.exchange()
    node.exchange()
    assert current_balance() == 100
    assert not read(home / "shared_view.json", {})["intents"]


def test_engine_scope_cannot_admin_or_read_private_data(group):
    home, hub, data, post = group
    node.activate("eu", "https://panel.example.com", "t" * 40)
    client = create_app().test_client()
    _, engine = keys.generate("engine")
    headers = {"Authorization": "Bearer " + engine}
    assert client.get("/api/v1/instances", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/shared/configure", headers=headers, json={"enabled": False}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/shared/engine",
            headers=headers,
            json={"kind": "balance", "handle": "Player"},
        ).json["credits"]
        == 100
    )
    _, admin = keys.generate("admin")
    assert (
        client.post(
            "/api/v1/shared/engine",
            headers={"Authorization": "Bearer " + admin, "X-MBIIEZ-Role": "viewer"},
            json={"kind": "balance", "handle": "Player"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/sync/import",
            headers={"Authorization": "Bearer " + admin},
            json={"snapshot": {}},
        ).status_code
        == 400
    )
    assert client.post("/shared/v1/exchange", json={"events": []}).status_code == 401


@pytest.mark.parametrize("truncated", [False, True])
def test_compaction_recovers_both_sides_of_crash_with_new_native_writes(
    group, truncated
):
    home, hub, data, post = group
    node.activate("eu", "https://panel.example.com", "t" * 40)
    node.append(event("credit", handle="Player", amount=1))
    node.exchange()
    first = node.journal().read_bytes().splitlines(keepends=True)[0]
    old = read(home / "shared_epoch.json", {})["id"]
    new = secrets.token_hex(16)
    view = read(home / "shared_view.json", {})
    write(
        home / "shared_compaction.json",
        {
            "view": view,
            "old_epoch": old,
            "new_epoch": new,
            "first_line": hashlib.sha256(first).hexdigest(),
        },
    )
    if truncated:
        node.journal().write_bytes(b"")
    node.append(event("credit", handle="Player", amount=2))
    node.exchange()
    node.exchange()
    assert current_balance() == 103
    assert read(home / "shared_epoch.json", {})["id"] == (new if truncated else old)
    assert not (home / "shared_compaction.json").exists()


def test_crash_refund_waits_for_commit_beyond_bounded_batch(group):
    home, hub, data, post = group
    node.activate("eu", "https://panel.example.com", "t" * 40)
    reserve = event("reserve", changes=[dict(handle="Player", amount=30)])
    node.append(dict(reserve, kind="intent", pid=2147483647, started="0"))
    ledger.apply("eu", [reserve])
    for _ in range(400):
        node.append(event("stats", key="h:Player", delta=[1, 0, 0, 0]))
    node.append(event("commit", reservation=reserve["id"]))
    node.exchange()
    assert current_balance() == 70  # must not cancel before seeing final commit
    node.exchange()
    node.exchange()
    assert current_balance() == 70
    assert not read(home / "shared_view.json", {})["intents"]


def test_unlink_preserves_wallet_and_daily_claim_cache(group):
    home, hub, data, post = group
    node.activate("eu", "https://panel.example.com", "t" * 40)
    node.engine_operation(event("register", handle="Fresh", pin="1234", bonus=50))
    node.exchange()
    before = (data / "economy_accounts.dat").read_bytes()
    daily = (data / "economy_daily.dat").read_text()
    assert "fresh " in daily
    assert node.deactivate() == {"enabled": False}
    assert not node.enabled()
    assert (data / "economy_accounts.dat").read_bytes() == before
    assert (data / "economy_daily.dat").read_text() == daily
    assert accounts_store.add_credits("Fresh", 5)[0]
    with ledger.transaction() as db:
        assert ledger.get(db, "accounts", "fresh")[3] == 50
