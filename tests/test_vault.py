import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pw import Vault, main  # noqa: E402

PW = ROOT / "scripts" / "pw.py"


def paper(title: str, doi: str) -> str:
    return f"# {title}\n\n- **DOI**: https://doi.org/{doi}\n- **Year**: 2024\n\n## Abstract\n\nx\n"


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    v = tmp_path / "vault"
    v.mkdir()
    (v / "Root.md").write_text(
        "# Root\n\nSee [[Vault Layout]] for details.\n\n## Topics\n- [[Networking]]\n- [[Vault Layout]]\n"
    )
    (v / "Vault Layout.md").write_text("layout notes\n")
    (v / "Networking.md").write_text(
        "All networking work.\n\n## Subtopics\n- [[Datacenter Transport]]\n- [[Congestion Control]]\n"
    )
    (v / "Datacenter Transport.md").write_text("Transport protocols.\n\n## Papers\n- [[Acme - Fast Congestion Control]]\n")
    (v / "Congestion Control.md").write_text(
        "CC algorithms.\n\n## Papers\n- [[BBR]]\n- [[Acme - Fast Congestion Control]]\n\n## Notes\nmisc\n"
    )
    (v / "Acme - Fast Congestion Control.md").write_text(paper("Acme: Fast Congestion Control", "10.1145/ABC.1"))
    (v / "BBR.md").write_text(paper("BBR", "10.1145/3009824"))
    return Vault(v)


def test_sanitize_title():
    assert Vault.sanitize_title("Acme: Fast Congestion Control") == "Acme - Fast Congestion Control"
    assert Vault.sanitize_title("A/B testing: why?") == "A B testing - why"
    assert Vault.sanitize_title('  "Quoted" <x> | y.  ') == "Quoted x y"
    assert Vault.sanitize_title("ratio:1") == "ratio -1"


def test_list_and_find_doi(vault: Vault):
    names = [p.name for p in vault.list_paper_files()]
    assert names == ["Acme - Fast Congestion Control.md", "BBR.md"]
    assert vault.find_paper_by_doi("https://doi.org/10.1145/abc.1").name == "Acme - Fast Congestion Control.md"
    assert vault.find_paper_by_doi("10.9999/none") is None
    assert vault.find_paper_by_doi("") is None


def test_load_tree(vault: Vault):
    tree = vault.load_topic_tree()
    assert tree["root"] == ["Networking"]  # Vault Layout skipped, prose link ignored
    net = tree["topics"]["Networking"]
    assert net["is_leaf"] is False
    assert net["description"] == "All networking work."
    assert net["subtopics"] == ["Datacenter Transport", "Congestion Control"]
    assert tree["topics"]["Congestion Control"]["papers"] == ["BBR", "Acme - Fast Congestion Control"]
    assert tree["topics"]["Datacenter Transport"]["is_leaf"] is True


def test_papers_under_dedupes(vault: Vault):
    got = [Path(p).name for p in vault.papers_under("Networking")]
    assert got == ["Acme - Fast Congestion Control.md", "BBR.md"]
    assert vault.papers_under("Missing Topic") == []


def test_attach_paper_inserts_inside_section_and_is_idempotent(vault: Vault):
    leaf = vault.root / "Congestion Control.md"
    assert vault.attach_paper(leaf, "Cubic") is True
    assert vault.attach_paper(leaf, "Cubic") is False
    text = leaf.read_text()
    assert "- [[Acme - Fast Congestion Control]]\n- [[Cubic]]\n\n## Notes" in text


def test_attach_paper_creates_missing_section(vault: Vault):
    topic = vault.root / "Bare.md"
    topic.write_text("Just a description.\n\n")
    assert vault.attach_paper(topic, "X") is True
    assert topic.read_text() == "Just a description.\n\n## Papers\n- [[X]]\n"


def test_attach_paper_missing_file_raises(vault: Vault):
    with pytest.raises(FileNotFoundError):
        vault.attach_paper(vault.root / "Nope.md", "X")


def test_add_subtopic(vault: Vault):
    parent = vault.root / "Networking.md"
    assert vault.add_subtopic(parent, "Routing") is True
    assert vault.load_topic_tree()["topics"]["Networking"]["subtopics"][-1] == "Routing"


def test_create_topic_and_write_paper(vault: Vault):
    t = Vault.create_topic_file(vault.root / "New Leaf.md", "  A leaf.  ", is_leaf=True)
    assert t.read_text() == "A leaf.\n\n## Papers\n"
    t.write_text("changed\n")
    Vault.create_topic_file(t, "other", is_leaf=False)
    assert t.read_text() == "changed\n"  # never overwrites

    p = vault.write_paper_file(title="Foo: Bar", doi="10.1/x", year="2025")
    body = p.read_text()
    assert p.name == "Foo - Bar.md"
    assert "- **DOI**: https://doi.org/10.1/x" in body
    assert "- **Authors**: Not available" in body
    assert vault.find_paper_by_doi("10.1/X") == p


def test_cli_roundtrip(vault: Vault, capsys):
    assert main(["--vault", str(vault.root), "vault", "list_paper_files"]) == 0
    assert capsys.readouterr().out.count(".md") == 2

    assert main(["--vault", str(vault.root), "vault", "papers_under", "vault/Datacenter Transport.md"]) == 0
    assert capsys.readouterr().out.strip().endswith("Acme - Fast Congestion Control.md")

    assert main(["--vault", str(vault.root), "vault", "find_doi"]) == 2
    assert main(["--vault", str(vault.root), "vault", "bogus"]) == 2


def test_cli_env_var_and_script_entrypoint(vault: Vault):
    out = subprocess.run(
        [sys.executable, str(PW), "vault", "load_tree"],
        env={"PAPER_VAULT_ROOT": str(vault.root), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(out)["root"] == ["Networking"]
