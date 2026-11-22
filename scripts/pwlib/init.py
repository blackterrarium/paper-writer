"""Project scaffolding for `/paper-writer:init`.

Everything here is idempotent: existing files are never overwritten. Each step
reports what it created and what it left alone.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .config import CONFIG_NAME, DEFAULTS, Config

CTAN_ACMART = "https://mirrors.ctan.org/macros/latex/contrib/acmart.zip"

# Files a project needs next to main.tex to build with acmart.
TEMPLATE_FILES = (
    "acmart.cls",
    "ACM-Reference-Format.bst",
    "acmauthoryear.bbx",
    "acmauthoryear.cbx",
    "acmnumeric.bbx",
    "acmnumeric.cbx",
    "acmdatamodel.dbx",
)

# Hosts the skills contact. Kept in sync with README "Network access".
NETWORK_HOSTS = (
    "api.semanticscholar.org",
    "api.crossref.org",
    "doi.org",
    "dl.acm.org",
    "arxiv.org",
)


class InitError(Exception):
    pass


def _toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_list(items) -> str:
    return "[" + ", ".join(_toml_str(i) for i in items) + "]"


class Report:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.skipped: list[str] = []
        self.notes: list[str] = []

    def write(self, root: Path, rel: str, text: str) -> None:
        p = root / rel
        if p.exists():
            self.skipped.append(rel)
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        self.created.append(rel)

    def mkdir(self, root: Path, rel: str) -> None:
        p = root / rel
        if not p.is_dir():
            p.mkdir(parents=True, exist_ok=True)
            self.created.append(rel + "/")

    def as_dict(self) -> dict:
        return {"created": self.created, "skipped": self.skipped, "notes": self.notes}


# ---------- config ----------


def config_text(*, field: str, target_venues: list[str], preferred_tier: list[str],
                profile: str, vault: str) -> str:
    p = dict(DEFAULTS["paths"], vault=vault)
    return f"""# paper-writer project configuration. Paths are relative to this file.
# Every key is optional; omitted keys take the plugin defaults.

[paths]
paper_dir     = {_toml_str(p["paper_dir"])}
main_tex      = {_toml_str(p["main_tex"])}
bib           = {_toml_str(p["bib"])}
vault         = {_toml_str(p["vault"])}
outline_dir   = {_toml_str(p["outline_dir"])}
design_dir    = {_toml_str(p["design_dir"])}
name_commands = {_toml_str(p["name_commands"])}

[paper]
field         = {_toml_str(field)}
target_venues = {_toml_list(target_venues)}

[venues]
preferred_tier = {_toml_list(preferred_tier)}

[style]
profile   = {_toml_str(profile)}   # a profile under ~/.config/paper-writer/profiles/ ("" = built-in baseline)
path      = ""   # or a profile directory inside the project
overrides = ""   # optional per-project style-overrides.md
"""


# ---------- vault ----------

ROOT_MD = """This holds references to all the root topics of the paper tree. Update this file with more topics as needed.

The layout of the paper vault is defined in [[Vault Layout]].

## Topics

"""

VAULT_LAYOUT_MD = """## Organization

**Root**: [[Root]] holds all root topics of the tree. Every paper search starts from [[Root]].

**Papers**: each paper is stored in its own markdown file, named after its title, with YAML front matter (title, authors, venue, year, DOI, abstract) and a short note on why it matters to this project.

**Topic hierarchy**: each paper is associated with one or more research topics. Topics form a multi-rooted tree whose child nodes are subtopics of the parent's topic.

Each topic or subtopic is its own markdown file. A topic file lists its children as `[[file name]]` links; a child listed this way is *attached* to the parent.

**Leaves**: papers are attached to leaf topics. A paper may be attached to more than one leaf when it is relevant to several lines of research.

## Search process

Starting at [[Root]], move down the topic tree, at each level picking the one or more children closest to the topic being searched. At a leaf, retrieve every attached paper.

## Maintenance

The paper-writer skills (`paper-search`, `paper-add`, `paper-search-verify`, `update-refs`) create and update these files. Hand edits are fine as long as the link structure above is kept.
"""


# ---------- LaTeX ----------


def main_tex(title: str, bib_stem: str) -> str:
    return rf"""%% Main file for the paper. Created by /paper-writer:init.
%% Anonymous review build for an ACM sigconf venue. For camera-ready, drop
%% `review,anonymous`, fill in the authors and the ACM rights block, and
%% replace \acmConference with the details your venue gives you.
\documentclass[sigconf,review,anonymous]{{acmart}}

\settopmatter{{printacmref=false}}
\setcopyright{{none}}
\renewcommand\footnotetextcopyrightpermission[1]{{}}
\acmConference[Conference 'YY]{{Conference Name}}{{Month DD--DD, YYYY}}{{City, Country}}

\usepackage{{xspace}}

%% end of the preamble

\begin{{document}}

\title{{{title}}}

\author{{Anonymous Author(s)}}
\affiliation{{\institution{{Anonymous Institution}}\country{{Country}}}}

\begin{{abstract}}
Abstract goes here.
\end{{abstract}}

\maketitle

\input{{intro}}
\input{{background}}

\bibliographystyle{{ACM-Reference-Format}}
\bibliography{{{bib_stem}}}

\end{{document}}
"""


SECTION_STUBS = {
    "intro.tex": "\\section{Introduction}\n\\label{sec:intro}\n\n% Written by /paper-writer:write-intro.\n",
    "background.tex": "\\section{Background and Motivation}\n\\label{sec:background}\n\n% Written by /paper-writer:write-background.\n",
}

LATEX_GITIGNORE = """*.aux
*.bbl
*.blg
*.fdb_latexmk
*.fls
*.log
*.out
*.synctex.gz
main.pdf
"""


def _kpsewhich(name: str) -> Path | None:
    try:
        out = subprocess.run(["kpsewhich", name], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    p = out.stdout.strip()
    return Path(p) if out.returncode == 0 and p else None


def _class_version(cls: Path) -> str:
    text = cls.read_text(encoding="utf-8", errors="replace")
    i = text.find("\\ProvidesClass{acmart}")
    if i < 0:
        return "unknown"
    seg = text[i:i + 200]
    for tok in seg.replace("[", " ").split():
        if tok.startswith("v") and tok[1:2].isdigit():
            return tok
    return "unknown"


def _template_from_tex() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for name in TEMPLATE_FILES:
        p = _kpsewhich(name)
        if p:
            found[name] = p
    if "acmart.cls" not in found:
        raise InitError("acmart is not in the local TeX installation (kpsewhich acmart.cls found nothing)")
    return found


def _template_from_ctan(work: Path, url: str = CTAN_ACMART) -> dict[str, Path]:
    """Download acmart from CTAN and generate acmart.cls with `tex acmart.ins`."""
    if shutil.which("tex") is None:
        raise InitError("CTAN ships acmart as source; generating acmart.cls needs `tex`, which is not installed")
    archive = work / "acmart.zip"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, archive.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    except OSError as e:
        raise InitError(f"download from CTAN failed: {e}") from e
    if not zipfile.is_zipfile(archive):
        raise InitError("CTAN returned something that is not a zip archive")
    src = work / "src"
    src.mkdir()
    wanted = {"acmart.dtx", "acmart.ins", *TEMPLATE_FILES} - {"acmart.cls"}
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            base = info.filename.rsplit("/", 1)[-1]
            if base in wanted and not info.is_dir():
                (src / base).write_bytes(zf.read(info))  # by basename only: no path traversal
    if not (src / "acmart.ins").is_file():
        raise InitError("acmart.ins missing from the CTAN archive")
    r = subprocess.run(["tex", "-interaction=batchmode", "acmart.ins"], cwd=src,
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not (src / "acmart.cls").is_file():
        raise InitError("`tex acmart.ins` did not produce acmart.cls")
    return {name: src / name for name in TEMPLATE_FILES if (src / name).is_file()}


def install_template(root: Path, paper_dir: str, source: str, rep: Report) -> None:
    """source: auto (CTAN, then local TeX) | ctan | tex | none."""
    if source == "none":
        rep.notes.append("template: skipped (--template none)")
        return
    dest = root / paper_dir
    if (dest / "acmart.cls").exists():
        rep.skipped.append(f"{paper_dir}/acmart.cls")
        rep.notes.append(f"template: kept existing acmart.cls ({_class_version(dest / 'acmart.cls')})")
        return
    order = {"auto": ["ctan", "tex"], "ctan": ["ctan"], "tex": ["tex"]}.get(source)
    if order is None:
        raise InitError(f"unknown template source: {source}")
    errors = []
    with tempfile.TemporaryDirectory(prefix="pw-acmart-") as tmp:
        for how in order:
            try:
                files = _template_from_ctan(Path(tmp)) if how == "ctan" else _template_from_tex()
            except InitError as e:
                errors.append(f"{how}: {e}")
                continue
            dest.mkdir(parents=True, exist_ok=True)
            for name, p in files.items():
                if (dest / name).exists():
                    rep.skipped.append(f"{paper_dir}/{name}")
                else:
                    shutil.copyfile(p, dest / name)
                    rep.created.append(f"{paper_dir}/{name}")
            version = _class_version(dest / "acmart.cls")
            rep.notes.append(f"template: acmart {version} from {'CTAN' if how == 'ctan' else 'the local TeX installation'}")
            if errors:
                rep.notes.append("template: " + "; ".join(errors))
            return
    raise InitError("could not install the ACM template: " + "; ".join(errors)
                    + ". Install TeX Live (which includes acmart), or copy acmart.cls and "
                    "ACM-Reference-Format.bst into the paper directory, then re-run init.")


# ---------- network allowlist ----------


def list_profiles() -> list[dict]:
    """User-level style profiles that have a style.md."""
    from .style import user_profiles_dir
    base = user_profiles_dir()
    out = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if (d / "style.md").is_file():
                out.append({"name": d.name, "dir": str(d), "has_rules": (d / "rules.toml").is_file(),
                            "has_rubric": (d / "rubric.md").is_file()})
    return out


def allow_network(root: Path, hosts=NETWORK_HOSTS, write: bool = True) -> dict:
    """Merge WebFetch permissions and sandbox hosts into .claude/settings.json.

    With write=False, return the merged settings instead of writing them."""
    path = root / ".claude" / "settings.json"
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise InitError(f"{path} is not valid JSON ({e}); fix it or add the hosts by hand") from e
        if not isinstance(data, dict):
            raise InitError(f"{path} does not hold a JSON object")
    added = []
    allow = data.setdefault("permissions", {}).setdefault("allow", [])
    for h in hosts:
        rule = f"WebFetch(domain:{h})"
        if rule not in allow:
            allow.append(rule)
            added.append(rule)
    domains = data.setdefault("sandbox", {}).setdefault("network", {}).setdefault("allowedDomains", [])
    for h in hosts:
        if h not in domains:
            domains.append(h)
            added.append(f"sandbox:{h}")
    if not write:
        return {"file": str(path), "added": added, "settings": data}
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"file": str(path), "added": added}


# ---------- entry point ----------


def init_project(root: Path, *, title: str = "System: A Descriptive Subtitle",
                 field: str | None = None, target_venues: list[str] | None = None,
                 profile: str = "", vault: str = "vault", template: str = "auto") -> dict:
    root = root.resolve()
    rep = Report()
    paths = dict(DEFAULTS["paths"], vault=vault)
    if (root / CONFIG_NAME).exists():
        # Re-running init on a configured project: scaffold the paths it names.
        cfg = Config.load(root)
        if cfg.root != root:
            raise InitError(f"{CONFIG_NAME} resolved to {cfg.root}, expected {root}")
        paths = {k: cfg.get(f"paths.{k}") for k in DEFAULTS["paths"]}
        vault = paths["vault"]
        rep.notes.append(f"{CONFIG_NAME} exists: kept it and scaffolded the paths it names")
    rep.write(root, CONFIG_NAME, config_text(
        field=field or DEFAULTS["paper"]["field"],
        target_venues=target_venues or list(DEFAULTS["paper"]["target_venues"]),
        preferred_tier=list(DEFAULTS["venues"]["preferred_tier"]),
        profile=profile, vault=vault))

    paper_dir = paths["paper_dir"]
    for key in ("paper_dir", "outline_dir", "design_dir", "vault"):
        rep.mkdir(root, paths[key])
    rep.mkdir(root, os.path.dirname(paths["name_commands"]) or ".")

    rep.write(root, f"{vault}/Root.md", ROOT_MD)
    rep.write(root, f"{vault}/Vault Layout.md", VAULT_LAYOUT_MD)

    bib = paths["bib"]
    bib_stem = os.path.splitext(os.path.relpath(bib, paper_dir))[0]
    rep.write(root, paths["main_tex"], main_tex(title, bib_stem))
    for name, text in SECTION_STUBS.items():
        rep.write(root, f"{paper_dir}/{name}", text)
    rep.write(root, bib, "")
    rep.write(root, f"{paper_dir}/.gitignore", LATEX_GITIGNORE)

    install_template(root, paper_dir, template, rep)
    return {"root": str(root), **rep.as_dict()}
