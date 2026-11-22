"""One venue table for every skill: short names and the paper-search venue filter.

Matching is case-insensitive substring, first match wins, so ORDER MATTERS:
longer or more specific fragments must come before fragments they contain.

Each entry is (fragment, short name, counts_for_search). Entries with
counts_for_search=False still normalize names but do not make a paper
in-scope for `paper-search` (e.g. the bare "fast" fragment, which would match
far too many venue names, and venues outside the systems/networking scope).
"""

from __future__ import annotations

import re

VENUES: list[tuple[str, str, bool]] = [
    ("mobile computing and networking", "MobiCom", True),
    ("mobicom", "MobiCom", True),
    ("sigcomm", "SIGCOMM", True),
    ("computer and communications security", "CCS", True),
    ("mobile systems", "MobiSys", True),
    ("mobisys", "MobiSys", True),
    ("embedded networked sensor", "SenSys", True),
    ("sensys", "SenSys", True),
    ("internet measurement", "IMC", True),
    ("emerging network", "CoNEXT", True),  # S2 also spells it "Emerging Network Experiment"
    ("conext", "CoNEXT", True),
    ("architectural support for programming", "ASPLOS", True),
    ("asplos", "ASPLOS", True),
    ("operating systems principles", "SOSP", True),
    ("sosp", "SOSP", True),
    ("knowledge discovery", "KDD", True),
    ("kdd", "KDD", True),
    ("human factors", "CHI", True),
    ("chi conference", "CHI", True),
    ("ubiquitous computing", "UbiComp", True),
    ("ubicomp", "UbiComp", True),
    ("programming language design", "PLDI", True),
    ("pldi", "PLDI", True),
    ("principles of programming languages", "POPL", True),
    ("popl", "POPL", True),
    ("operating systems design and implementation", "OSDI", True),
    ("osdi", "OSDI", True),
    ("networked systems design", "NSDI", True),
    ("nsdi", "NSDI", True),
    ("microarchitecture", "MICRO", True),
    ("micro", "MICRO", True),
    # HPCA must precede "computer architecture" (ISCA), which it contains.
    ("high-performance computer architecture", "HPCA", True),
    ("hpca", "HPCA", True),
    ("computer architecture", "ISCA", True),
    ("isca", "ISCA", True),
    ("infocom", "INFOCOM", True),
    ("global communications", "GLOBECOM", True),
    ("globecom", "GLOBECOM", True),
    ("international conference on communications", "ICC", True),
    ("distributed computing systems", "ICDCS", True),
    ("icdcs", "ICDCS", True),
    ("network protocols", "ICNP", True),
    ("icnp", "ICNP", True),
    ("sensing, communication", "SECON", True),
    ("secon", "SECON", True),
    ("mobile ad-hoc", "MASS", True),
    ("mass", "MASS", True),
    ("security and privacy", "S&P", True),
    ("cloud computing", "SoCC", True),
    ("socc", "SoCC", True),
    ("networked systems design and implementation", "NSDI", True),
    ("symposium on networked systems design and implementation", "NSDI", True),
    ("operating systems design", "OSDI", True),
    ("annual technical conference", "ATC", True),
    ("usenix annual", "ATC", True),
    ("network and distributed system security", "NDSS", True),  # before the generic "security symposium"
    ("security symposium", "USENIX Security", True),
    ("file and storage", "FAST", True),
    ("fast", "FAST", False),
    # Previously only in update-refs: normalize, but outside paper-search scope.
    ("high performance computing", "SC", False),
    ("very large data bases", "VLDB", False),
    ("vldb", "VLDB", False),
    ("management of data", "SIGMOD", False),
    ("sigmod", "SIGMOD", False),
]


_AT_WORKSHOP = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*)@")


def short_name(venue: str, year: str | int | None = None) -> str:
    """Short venue name for a full venue string, with ` {year}` appended if given.
    Empty string if no fragment matches.
    """
    venue = venue or ""
    lower = venue.lower()
    at = _AT_WORKSHOP.match(venue)
    if at and short_name(venue[at.end(1) + 1:]):
        # "EuroP4@CoNEXT": a workshop at a known conference keeps its own name
        abbrev = at.group(1)
    else:
        abbrev = next((a for frag, a, _ in VENUES if frag in lower), "")
        if not abbrev:
            return ""
        if ("workshop" in lower or "wkshp" in lower) and "workshop" not in abbrev.lower():
            abbrev += " Workshops"
    return f"{abbrev} {year}" if year else abbrev


def is_search_target(venue: str) -> bool:
    """True if a paper from this venue is in scope for paper-search."""
    lower = (venue or "").lower()
    return any(frag in lower for frag, _, target in VENUES if target)
