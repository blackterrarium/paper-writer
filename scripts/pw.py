#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""pw: helper CLI for the paper-writer plugin.

Usage:
    pw.py [--vault DIR] vault <command> [args...]

The vault root is taken from --vault, else $PAPER_VAULT_ROOT, else
`vault/paper-writer` (relative to the current directory).

Vault commands:
    load_tree
        Print the topic tree as JSON:
          {"root": [titles], "topics": {title: {path, title, description,
           subtopics, papers, is_leaf}}}

    find_doi <doi>
        Print the path of the paper file containing the DOI, or empty if none.

    list_paper_files
        Print newline-delimited paths of every paper file in the vault.

    papers_under <topic-title-or-path>
        Print newline-delimited paths of every paper file reachable from the
        given topic (recursively through `## Subtopics`).

    sanitize <title>
        Print the sanitized filename (without .md) for a paper title.

    write_paper <json-blob>
        Create/overwrite a paper file. JSON keys: title (required), doi,
        authors, year, venue, abstract, relevance. Prints the resulting path.

    attach_paper <leaf-path> <paper-title>
        Append `- [[paper-title]]` under `## Papers` of the leaf topic file,
        creating the section if missing. Idempotent. Prints modified|unchanged.

    add_subtopic <parent-path> <child-title>
        Append `- [[child-title]]` under `## Subtopics` of the parent topic
        file, creating the section if missing. Idempotent.

    create_topic <path> <description> [--leaf]
        Create a topic file with the description and the right section header
        (`## Papers` for a leaf, `## Subtopics` otherwise). No-op if it exists.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

DEFAULT_VAULT = "vault/paper-writer"

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
DOI_LINE_RE = re.compile(
    r"^-\s*\*\*DOI\*\*:\s*(?:https?://(?:dx\.)?doi\.org/)?(\S+)\s*$",
    re.MULTILINE,
)

# Vault metadata files that are never topics.
SKIP_TOPIC_FILES = {
    "Paper Vault.md",
    "Vault Layout.md",
    "Vault Init Prompt.md",
    "Vault Skills.md",
}

PAPER_TEMPLATE = """# {title}

- **DOI**: {doi_line}
- **Authors**: {authors}
- **Year**: {year}
- **Venue**: {venue}

## Abstract

{abstract}

## Relevance

{relevance}
"""


class Vault:
    """Read and mutate an Obsidian-style paper vault rooted at `root`."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    # ---------- filenames + classification ----------

    @staticmethod
    def sanitize_title(title: str) -> str:
        """Turn a paper title into its vault filename stem (no .md suffix).

        - Colons become ` -` ("Foo: Bar" -> "Foo - Bar")
        - Forward slashes become a space
        - Characters illegal on macOS/ext4/NTFS are dropped: \\ ? * " < > |
        - Internal whitespace is collapsed; leading/trailing dots and spaces trimmed
        """
        s = title.strip()
        s = s.replace(": ", " - ")
        s = s.replace(":", " -")
        s = s.replace("/", " ")
        s = re.sub(r"[\\?*\"<>|]", "", s)
        s = re.sub(r"\s+", " ", s).strip(" .")
        return s

    def paper_path_for_title(self, title: str) -> Path:
        return self.root / (self.sanitize_title(title) + ".md")

    def resolve_wikilink(self, name: str) -> Path:
        return self.root / f"{name}.md"

    @staticmethod
    def _head(path: Path) -> Optional[str]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                return fh.read(4096)
        except OSError:
            return None

    @classmethod
    def is_paper_file(cls, path: Path) -> bool:
        """A paper file has a `- **DOI**:` line near the top."""
        head = cls._head(path)
        return bool(head and DOI_LINE_RE.search(head))

    @classmethod
    def extract_doi(cls, path: Path) -> Optional[str]:
        head = cls._head(path)
        if not head:
            return None
        m = DOI_LINE_RE.search(head)
        return m.group(1).strip() if m else None

    @staticmethod
    def normalize_doi(doi: str) -> str:
        doi = doi.strip()
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
        return doi.lower()

    def find_paper_by_doi(self, doi: str) -> Optional[Path]:
        if not doi:
            return None
        target = self.normalize_doi(doi)
        for p in sorted(self.root.glob("*.md")):
            found = self.extract_doi(p)
            if found and self.normalize_doi(found) == target:
                return p
        return None

    def list_paper_files(self) -> list[Path]:
        return sorted(p for p in self.root.glob("*.md") if self.is_paper_file(p))

    # ---------- topic tree ----------

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    @staticmethod
    def _split_sections(text: str) -> dict[str, list[str]]:
        """Parse `## Section` headers into {section name: body lines}."""
        sections: dict[str, list[str]] = {"__preamble__": []}
        current = "__preamble__"
        for line in text.splitlines():
            m = re.match(r"^##\s+(.+?)\s*$", line)
            if m:
                current = m.group(1).strip()
                sections.setdefault(current, [])
                continue
            sections[current].append(line)
        return sections

    @staticmethod
    def _extract_wikilinks(lines: list[str]) -> list[str]:
        return [m.group(1).strip() for line in lines for m in WIKILINK_RE.finditer(line)]

    @staticmethod
    def _topic_description(text: str) -> str:
        """The first non-empty, non-heading line is the description."""
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                return s
        return ""

    def load_topic_tree(self) -> dict:
        """Walk the topic tree from Root.md.

        Only bullet wikilinks under Root.md's `## Topics` count as roots, so
        prose like "see [[Vault Layout]]" doesn't pollute the tree.
        `subtopics` and `papers` are lists of wikilink target names (no .md).
        """
        topics: dict[str, dict] = {}

        def visit(title: str) -> None:
            if title in topics:
                return
            path = self.resolve_wikilink(title)
            text = self._read_text(path)
            sections = self._split_sections(text)
            subtopics = self._extract_wikilinks(sections.get("Subtopics", []))
            topics[title] = {
                "path": str(path),
                "title": title,
                "description": self._topic_description(text),
                "subtopics": subtopics,
                "papers": self._extract_wikilinks(sections.get("Papers", [])),
                "is_leaf": not subtopics,
            }
            for child in subtopics:
                visit(child)

        root_sections = self._split_sections(self._read_text(self.root / "Root.md"))
        root_titles = [
            t
            for t in self._extract_wikilinks(root_sections.get("Topics", []))
            if f"{t}.md" not in SKIP_TOPIC_FILES
        ]
        for t in root_titles:
            visit(t)
        return {"root": root_titles, "topics": topics}

    def papers_under(self, topic_title: str) -> list[str]:
        """Recursively collect paper file paths reachable from `topic_title`."""
        tree = self.load_topic_tree()
        seen_topics: set[str] = set()
        seen_papers: set[str] = set()
        papers: list[str] = []

        def walk(t: str) -> None:
            if t in seen_topics or t not in tree["topics"]:
                return
            seen_topics.add(t)
            info = tree["topics"][t]
            for paper_title in info["papers"]:
                p = str(self.resolve_wikilink(paper_title))
                if p not in seen_papers:
                    seen_papers.add(p)
                    papers.append(p)
            for child in info["subtopics"]:
                walk(child)

        walk(topic_title)
        return papers

    # ---------- writers ----------

    def write_paper_file(
        self,
        title: str,
        doi: str = "",
        authors: str = "",
        year: str = "",
        venue: str = "",
        abstract: str = "",
        relevance: str = "",
    ) -> Path:
        """Create or overwrite a canonical paper file and return its path."""
        path = self.paper_path_for_title(title)
        body = PAPER_TEMPLATE.format(
            title=title,
            doi_line=f"https://doi.org/{doi}" if doi else "Not available",
            authors=authors or "Not available",
            year=year or "Unknown",
            venue=venue or "Unknown",
            abstract=abstract.strip() if abstract else "Not available",
            relevance=relevance.strip() if relevance else "Not available",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def _append_wikilink(self, path: Path, section: str, item_title: str) -> bool:
        """Append `- [[item_title]]` under `## section`, creating the section
        at the end of the file if missing. Returns True if the file changed.
        """
        text = self._read_text(path)
        if not text:
            raise FileNotFoundError(f"topic file does not exist or is empty: {path}")

        lines = text.splitlines()
        entry = f"- [[{item_title}]]"
        header_re = re.compile(rf"^##\s+{re.escape(section)}\s*$")

        start: Optional[int] = None
        end = len(lines)
        for i, line in enumerate(lines):
            if start is None and header_re.match(line):
                start = i
            elif start is not None and re.match(r"^##\s+", line):
                end = i
                break

        if start is None:
            while lines and not lines[-1].strip():
                lines.pop()
            lines += ["", f"## {section}", entry]
        else:
            link_re = re.compile(rf"\[\[{re.escape(item_title)}\]\]")
            if any(link_re.search(line) for line in lines[start + 1 : end]):
                return False
            # Insert after the section's last non-blank line.
            insert_at = end
            while insert_at > start + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines.insert(insert_at, entry)

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    def attach_paper(self, leaf_path: Path, paper_title: str) -> bool:
        return self._append_wikilink(Path(leaf_path), "Papers", paper_title)

    def add_subtopic(self, parent_path: Path, child_title: str) -> bool:
        return self._append_wikilink(Path(parent_path), "Subtopics", child_title)

    @staticmethod
    def create_topic_file(path: Path, description: str, is_leaf: bool) -> Path:
        path = Path(path)
        if path.exists():
            return path
        section = "## Papers" if is_leaf else "## Subtopics"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{description.strip()}\n\n{section}\n", encoding="utf-8")
        return path


# ---------- CLI ----------


def _vault_cli(vault: Vault, argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]

    def need(n: int, usage: str) -> bool:
        if len(args) < n:
            print(f"usage: vault {cmd} {usage}", file=sys.stderr)
            return False
        return True

    if cmd == "load_tree":
        print(json.dumps(vault.load_topic_tree(), indent=2))
    elif cmd == "find_doi":
        if not need(1, "<doi>"):
            return 2
        p = vault.find_paper_by_doi(args[0])
        print(str(p) if p else "")
    elif cmd == "list_paper_files":
        for p in vault.list_paper_files():
            print(p)
    elif cmd == "papers_under":
        if not need(1, "<topic-title-or-path>"):
            return 2
        topic = args[0].rsplit("/", 1)[-1].removesuffix(".md")
        for p in vault.papers_under(topic):
            print(p)
    elif cmd == "sanitize":
        if not need(1, "<title>"):
            return 2
        print(Vault.sanitize_title(" ".join(args)))
    elif cmd == "write_paper":
        if not need(1, "<json-blob>"):
            return 2
        blob = json.loads(args[0])
        path = vault.write_paper_file(
            title=blob["title"],
            doi=blob.get("doi", ""),
            authors=blob.get("authors", ""),
            year=str(blob.get("year", "")),
            venue=blob.get("venue", ""),
            abstract=blob.get("abstract", ""),
            relevance=blob.get("relevance", ""),
        )
        print(path)
    elif cmd in ("attach_paper", "add_subtopic"):
        if not need(2, "<topic-path> <title>"):
            return 2
        fn = vault.attach_paper if cmd == "attach_paper" else vault.add_subtopic
        print("modified" if fn(Path(args[0]), args[1]) else "unchanged")
    elif cmd == "create_topic":
        if not need(2, "<path> <description> [--leaf]"):
            return 2
        leaf = "--leaf" in args
        desc = " ".join(a for a in args[1:] if a != "--leaf")
        print(Vault.create_topic_file(Path(args[0]), desc, leaf))
    else:
        print(f"unknown vault command: {cmd}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pw.py",
        description="paper-writer helper CLI",
        epilog="Run `pw.py vault` with no command for the full command list.",
    )
    parser.add_argument("--vault", help="vault root (default: $PAPER_VAULT_ROOT or %s)" % DEFAULT_VAULT)
    parser.add_argument("group", choices=["vault"])
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)

    root = ns.vault or os.environ.get("PAPER_VAULT_ROOT") or DEFAULT_VAULT
    return _vault_cli(Vault(root), ns.rest)


if __name__ == "__main__":
    sys.exit(main())
