import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PW = ROOT / "scripts" / "pw.py"
sys.path.insert(0, str(ROOT / "scripts"))

from pwlib import init as initlib  # noqa: E402
from pwlib.config import Config  # noqa: E402
from pwlib.vault import Vault  # noqa: E402


def run(cwd, *args, env=None, check=True):
    r = subprocess.run([sys.executable, str(PW), *args], cwd=cwd, capture_output=True, text=True, env=env)
    if check:
        assert r.returncode == 0, r.stderr
    return r


def test_fresh_project(tmp_path):
    out = initlib.init_project(tmp_path, title="Acme: Fast Congestion Control",
                               target_venues=["NSDI", "SIGCOMM"], profile="eve", template="none")
    assert out["skipped"] == []
    for rel in ("paper-writer.toml", "paper/main.tex", "paper/intro.tex", "paper/background.tex",
                "paper/ref.bib", "paper/.gitignore", "vault/Root.md", "vault/Vault Layout.md"):
        assert (tmp_path / rel).is_file(), rel
    for rel in ("outline", "design/design-details", "guidelines"):
        assert (tmp_path / rel).is_dir(), rel

    cfg = Config.load(tmp_path)
    assert cfg.warnings == []
    assert cfg.get("paths.vault") == "vault"
    assert cfg.get("paper.target_venues") == ["NSDI", "SIGCOMM"]
    assert cfg.get("style.profile") == "eve"

    tex = (tmp_path / "paper/main.tex").read_text()
    assert r"\title{Acme: Fast Congestion Control}" in tex
    assert "%% end of the preamble" in tex  # paper-name inserts packages before this line
    assert r"\bibliography{ref}" in tex and r"\input{intro}" in tex
    assert "—" not in tex

    tree = Vault(str(tmp_path / "vault")).load_topic_tree()
    assert tree == {"root": [], "topics": {}}


def test_rerun_never_overwrites(tmp_path):
    initlib.init_project(tmp_path, template="none")
    (tmp_path / "paper/main.tex").write_text("mine")
    (tmp_path / "paper-writer.toml").write_text('[paths]\nvault = "vault"\n[paper]\nfield = "databases"\n')
    out = initlib.init_project(tmp_path, title="Other: Title", template="none")
    assert out["created"] == []
    assert (tmp_path / "paper/main.tex").read_text() == "mine"
    assert "databases" in (tmp_path / "paper-writer.toml").read_text()


def test_rerun_follows_existing_config(tmp_path):
    (tmp_path / "paper-writer.toml").write_text(
        '[paths]\npaper_dir = "tex"\nmain_tex = "tex/paper.tex"\nbib = "tex/bib/refs.bib"\nvault = "notes"\n')
    initlib.init_project(tmp_path, template="none")
    assert (tmp_path / "notes/Root.md").is_file()
    assert r"\bibliography{bib/refs}" in (tmp_path / "tex/paper.tex").read_text()
    assert not (tmp_path / "paper").exists() and not (tmp_path / "vault").exists()


def test_config_text_round_trips_quotes():
    text = initlib.config_text(field='networks "and" systems', target_venues=["A"],
                               preferred_tier=["B"], profile="", vault="v")
    assert tomllib.loads(text)["paper"]["field"] == 'networks "and" systems'


def _fake_tex_files(d: Path) -> dict[str, Path]:
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in initlib.TEMPLATE_FILES:
        (d / name).write_text("\\ProvidesClass{acmart}\n[2099/01/01 v9.9 test]\n" if name == "acmart.cls" else name)
        out[name] = d / name
    return out


def test_template_auto_falls_back_to_tex(tmp_path, monkeypatch):
    def ctan_fails(work, url=None):
        raise initlib.InitError("offline")
    monkeypatch.setattr(initlib, "_template_from_ctan", ctan_fails)
    monkeypatch.setattr(initlib, "_template_from_tex", lambda: _fake_tex_files(tmp_path / "texmf"))
    proj = tmp_path / "proj"
    proj.mkdir()
    out = initlib.init_project(proj)
    assert "paper/acmart.cls" in out["created"]
    assert any("v9.9 from the local TeX installation" in n for n in out["notes"])
    assert any("ctan: offline" in n for n in out["notes"])
    # second run keeps the class file
    out = initlib.init_project(proj)
    assert "paper/acmart.cls" in out["skipped"]


def test_template_failure_is_reported_after_scaffolding(tmp_path, monkeypatch):
    def fail(*a, **k):
        raise initlib.InitError("nope")
    monkeypatch.setattr(initlib, "_template_from_ctan", fail)
    monkeypatch.setattr(initlib, "_template_from_tex", fail)
    with pytest.raises(initlib.InitError, match="could not install the ACM template"):
        initlib.init_project(tmp_path)
    assert (tmp_path / "paper/main.tex").is_file()


def test_ctan_extract_uses_basenames_only(tmp_path, monkeypatch):
    """The archive is untrusted: members are written by basename, so ../ paths cannot escape."""
    if shutil.which("tex") is None:
        pytest.skip("tex not installed")
    archive = tmp_path / "acmart.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("acmart/acmart.ins", "\\input docstrip\n\\keepsilent\n\\askforoverwritefalse\n\\generate{\\file{acmart.cls}{\\from{acmart.dtx}{class}}}\n\\endbatchfile\n")
        zf.writestr("acmart/acmart.dtx", "%<*class>\n\\ProvidesClass{acmart}[2099/01/01 v9.9 test]\n%</class>\n")
        zf.writestr("../../evil.bst", "x")
    monkeypatch.setattr(initlib.urllib.request, "urlopen", lambda url, timeout: archive.open("rb"))
    work = tmp_path / "work"
    work.mkdir()
    files = initlib._template_from_ctan(work)
    assert initlib._class_version(files["acmart.cls"]) == "v9.9"
    assert not (tmp_path / "evil.bst").exists()


def test_allow_network_merges(tmp_path):
    s = tmp_path / ".claude/settings.json"
    s.parent.mkdir()
    s.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)", "WebFetch(domain:doi.org)"]}, "model": "x"}))
    preview = initlib.allow_network(tmp_path, write=False)
    assert "WebFetch(domain:doi.org)" not in preview["added"]
    assert json.loads(s.read_text())["model"] == "x" and "sandbox" not in json.loads(s.read_text())
    initlib.allow_network(tmp_path)
    data = json.loads(s.read_text())
    assert data["model"] == "x" and data["permissions"]["allow"][0] == "Bash(ls)"
    assert data["permissions"]["allow"].count("WebFetch(domain:doi.org)") == 1
    assert data["sandbox"]["network"]["allowedDomains"] == list(initlib.NETWORK_HOSTS)
    assert initlib.allow_network(tmp_path)["added"] == []


def test_allow_network_rejects_bad_json(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/settings.json").write_text("{not json")
    with pytest.raises(initlib.InitError, match="not valid JSON"):
        initlib.allow_network(tmp_path)


def test_network_hosts_match_readme():
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## Network access", 1)[1]
    for h in initlib.NETWORK_HOSTS:
        assert f"`{h}`" in section


def test_cli(tmp_path, monkeypatch):
    env = {"PATH": "/usr/bin:/bin", "XDG_CONFIG_HOME": str(tmp_path / "xdg"), "HOME": str(tmp_path)}
    prof = tmp_path / "xdg/paper-writer/profiles/eve"
    prof.mkdir(parents=True)
    (prof / "style.md").write_text("# guide\n")
    assert json.loads(run(tmp_path, "init", "profiles", env=env).stdout) == [
        {"name": "eve", "dir": str(prof), "has_rules": False, "has_rubric": False}]
    proj = tmp_path / "p"
    proj.mkdir()
    out = json.loads(run(proj, "init", "--venues", "NSDI, SIGCOMM", "--template", "none", env=env).stdout)
    assert "paper-writer.toml" in out["created"]
    assert tomllib.loads((proj / "paper-writer.toml").read_text())["paper"]["target_venues"] == ["NSDI", "SIGCOMM"]
    assert run(proj, "init", "--bogus", "x", env=env, check=False).returncode == 2


def test_cli_bad_template_source(tmp_path):
    r = run(tmp_path, "init", "--template", "weird", check=False)
    assert r.returncode == 1 and "unknown template source" in r.stderr
