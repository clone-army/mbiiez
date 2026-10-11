import pytest
from mbiiez.api.client import save_node, nodes, Client
from mbiiez.api.storage import write
from mbiiez.web import auto_sync


@pytest.fixture
def peers(tmp_path, monkeypatch):
    monkeypatch.setenv("MBIIEZ_STATE_DIR", str(tmp_path / "state"))
    save_node("na", "Local", "http://127.0.0.1:8081", "secret")
    save_node("eu", "Europe", "https://eu.example.com", "secret-eu")
    save_node("other", "Offline", "https://other.example.com", "secret-other")
    write(
        auto_sync.settings_path(),
        {
            "nodes": {
                key: {"enabled": True, "url": node["url"], "protocol": 2}
                for key, node in nodes().items()
            }
        },
    )
    return tmp_path


def test_status_monitor_never_transfers_snapshots_and_continues_past_offline(peers):
    calls = []

    class Fake:
        def __init__(self, identifier):
            self.identifier = identifier

        def call(self, method, path, data=None):
            calls.append((self.identifier, method, path))
            if self.identifier == "other":
                raise RuntimeError("secret error text")
            assert (method, path) == ("GET", "shared/status")
            return {"enabled": True, "status": {"last_success": 123}}

    result = auto_sync.cycle(Fake)
    assert result["nodes"]["na"]["last_success"] == 123
    assert result["nodes"]["eu"]["last_success"] == 123
    assert "queued" in result["nodes"]["other"]["error"]
    assert "secret" not in str(result)


def test_changed_url_revokes_peer_and_defaults_to_local(peers):
    save_node("eu", "Europe", "https://changed.example.com", "")
    calls = []

    class Fake:
        def __init__(self, identifier):
            self.identifier = identifier

        def call(self, method, path, data=None):
            calls.append((self.identifier, method, path, data))
            return {"enabled": False, "status": {}}

    result = auto_sync.cycle(Fake)
    assert "URL changed" in result["nodes"]["eu"]["error"]
    assert ("na", "POST", "shared/peer", {"peer": "eu", "enabled": False}) in calls
    assert not any(call[0] == "eu" for call in calls)
    auto_sync.settings_path().unlink()
    assert list(auto_sync.settings()["nodes"]) == ["na"]


def test_enrolls_local_authority_and_only_selected_remote(peers, monkeypatch):
    calls = []

    def call(self, method, path, data=None):
        calls.append((self.identifier, method, path, data))
        if path == "sync/info":
            return {"shared_protocol": 2, "ready": True, "caded_instances": ["legends"]}
        if path == "shared/peer":
            return {"token": "peer-secret"}
        return {"enabled": True}

    monkeypatch.setattr(Client, "call", call)
    assert auto_sync.configure("eu", True, "https://panel.example.com")["enabled"]
    assert (
        "na",
        "POST",
        "shared/configure",
        {"enabled": True, "authority": True, "peer": "na"},
    ) in calls
    assert (
        "eu",
        "POST",
        "shared/configure",
        {
            "enabled": True,
            "peer": "eu",
            "hub": "https://panel.example.com",
            "token": "peer-secret",
        },
    ) in calls
    assert not any(row[0] == "other" for row in calls)
    assert "peer-secret" not in auto_sync.settings_path().read_text()
    for identifier, value in [("na", True), ("missing", True), ("eu", "yes")]:
        with pytest.raises(ValueError):
            auto_sync.configure(identifier, value, "https://panel.example.com")


def test_offline_unlink_preserves_membership_and_engine_upgrade_gate(
    peers, monkeypatch
):
    def offline(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(Client, "call", offline)
    with pytest.raises(RuntimeError):
        auto_sync.configure("eu", False)
    assert auto_sync.settings()["nodes"]["eu"]["enabled"]
    monkeypatch.setattr(
        Client,
        "call",
        lambda *a, **kw: {
            "shared_protocol": 2,
            "ready": False,
            "note": "Planned restart required",
        },
    )
    with pytest.raises(ValueError, match="Planned restart"):
        auto_sync.configure("eu", True, "https://panel.example.com")
