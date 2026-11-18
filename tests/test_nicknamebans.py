import pytest

from mbiiez import nicknamebans


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(nicknamebans.settings.locations, "mbii_path", str(tmp_path), raising=False)
    monkeypatch.setattr(nicknamebans, "sweep", lambda: None)
    nicknamebans._cache.update(mtime=None, rules=[])


def test_normalize_strips_colours_case_and_spaces():
    assert nicknamebans.normalize("^1Pad^7a  Wan^7 ") == "pada wan"


def test_exact_ignores_colours_and_case_but_not_extra_text():
    assert nicknamebans.add_ban("Padawan")[0]
    assert nicknamebans.check("^1PADAWAN^7")
    assert not nicknamebans.check("Padawan2")
    assert not nicknamebans.check("xPadawan")


def test_contains_matches_part_of_a_name():
    assert nicknamebans.add_ban("slur", "contains")[0]
    assert nicknamebans.check("big^1SLUR^7guy")
    assert not nicknamebans.check("sl ur")


def test_contains_needs_three_characters():
    ok, msg = nicknamebans.add_ban("ab", "contains")
    assert not ok and "3" in msg
    assert nicknamebans.add_ban("ab", "exact")[0]


def test_empty_name_rejected_and_blank_names_never_match():
    assert not nicknamebans.add_ban("  ^7 ")[0]
    nicknamebans.add_ban("bob")
    assert not nicknamebans.check("")


def test_remove_and_note_and_dedupe():
    nicknamebans.add_ban("bob", note="first")
    nicknamebans.add_ban("^1BOB", note="second")      # same rule, updated
    bans = nicknamebans.list_bans()
    assert len(bans) == 1 and bans[0]["note"] == "second"
    assert nicknamebans.set_note("bob", "exact", "third")[0]
    assert nicknamebans.list_bans()[0]["note"] == "third"
    assert not nicknamebans.remove_ban("bob", "contains")[0]
    assert nicknamebans.remove_ban("bob", "exact")[0]
    assert not nicknamebans.check("bob")


def test_enforce_kicks_counts_and_ip_bans(monkeypatch):
    nicknamebans.add_ban("griefer", ban_ip=True)
    sent, banned = [], []

    class Console:
        def rcon(self, cmd): sent.append(cmd)

    class Log:
        def log(self, msg): pass

    class Inst:
        console, log_handler = Console(), Log()

    import mbiiez.bansync as bansync
    monkeypatch.setattr(bansync, "add_ban", lambda ip, note, by: banned.append(ip) or (True, ""))
    assert nicknamebans.enforce(Inst(), "7", "^2Griefer", "1.2.3.4")
    assert not nicknamebans.enforce(Inst(), "8", "friendly", "5.6.7.8")
    assert sent == ["clientkick 7"] and banned == ["1.2.3.4"]
    rule = nicknamebans.list_bans()[0]
    assert rule["drops"] == 1 and rule["last_ip"] == "1.2.3.4"
