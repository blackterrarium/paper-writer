import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pwlib import venues  # noqa: E402
from pwlib.config import Config, ConfigError  # noqa: E402

CASES = json.loads((ROOT / "tests" / "data" / "venue_cases.json").read_text())


# ---------- venues ----------
# venue_cases.json holds the outputs of the four per-skill tables that existed
# before the table was unified (paper-search/paper-add shared one; update-refs
# had a variant). The unified table must reproduce paper-search exactly, and
# fall back to update-refs' answer only where paper-search had none.


# Deliberate fixes relative to the old tables.
INTENTIONAL = {
    "Proceedings of the High-Performance Computer Architecture Conference": "HPCA",  # was mislabelled ISCA
}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["venue"][:50] or "<empty>")
def test_short_name_parity(case):
    got = venues.short_name(case["venue"])
    if case["venue"] in INTENTIONAL:
        assert got == INTENTIONAL[case["venue"]]
    elif case["search_short"]:
        assert got == case["search_short"]
    else:
        assert got == case["refs_short"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["venue"][:50] or "<empty>")
def test_search_target_parity(case):
    assert venues.is_search_target(case["venue"]) is case["is_target"]


def test_short_name_year():
    assert venues.short_name("Proceedings of the ACM SIGCOMM 2024 Conference", 2024) == "SIGCOMM 2024"
    assert venues.short_name("Nowhere Workshop", 2024) == ""


def test_table_has_no_shadowed_fragments():
    """A fragment listed after a fragment it contains can never match first,
    which is a bug unless both map to the same short name."""
    for i, (later, later_short, _) in enumerate(venues.VENUES):
        for earlier, earlier_short, _ in venues.VENUES[:i]:
            if earlier in later:
                assert earlier_short == later_short, f"'{later}' ({later_short}) is shadowed by '{earlier}'"


# ---------- config ----------


def test_defaults_without_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = Config.load()
    assert cfg.file is None
    assert cfg.path("bib") == "paper/ref.bib"
    assert cfg.path("vault") == "vault/paper-writer"
    assert cfg.get("style.profile") == ""


def test_config_found_upward_and_paths_absolute_from_subdir(tmp_path, monkeypatch):
    (tmp_path / "paper-writer.toml").write_text(
        '[paths]\nvault = "notes"\n[paper]\nfield = "databases"\ntarget_venues = ["SIGMOD", "VLDB"]\n'
    )
    sub = tmp_path / "paper" / "figs"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    cfg = Config.load()
    assert cfg.file == tmp_path / "paper-writer.toml"
    assert cfg.path("vault") == str(tmp_path.resolve() / "notes")
    assert cfg.get("paper.target_venues") == ["SIGMOD", "VLDB"]
    assert cfg.get("paths.bib") == "paper/ref.bib"  # untouched default
    monkeypatch.chdir(tmp_path)
    assert Config.load().path("vault") == "notes"


def test_unknown_keys_warn_and_bad_types_fail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "paper-writer.toml").write_text('[paths]\nvalut = "x"\n[extra]\na = 1\n')
    cfg = Config.load()
    assert "unknown config key: paths.valut" in cfg.warnings
    assert "unknown config key: extra" in cfg.warnings

    (tmp_path / "paper-writer.toml").write_text('[paper]\ntarget_venues = "SIGCOMM"\n')
    with pytest.raises(ConfigError, match="target_venues must be list"):
        Config.load()

    (tmp_path / "paper-writer.toml").write_text("[paths\n")
    with pytest.raises(ConfigError):
        Config.load()


def test_dump_includes_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = Config.load().dump()
    assert d["project_root"] == str(tmp_path.resolve())
    assert d["config_file"] is None
    assert set(d) >= {"paths", "paper", "venues", "style"}
