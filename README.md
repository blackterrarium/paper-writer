# paper-writer

A [Claude Code](https://claude.com/claude-code) plugin for writing systems and networking
research papers. It keeps related work in an Obsidian-style vault, finds papers through
Semantic Scholar and Crossref, selects citations, drafts LaTeX sections, and reviews prose
against an author style guide.

> **Status: v0.1.0.** Scope: systems and networking venues.

## Install

```
/plugin marketplace add blackterrarium/paper-writer
/plugin install paper-writer@paper-writer
```

To try a local checkout: `claude --plugin-dir /path/to/paper-writer`.

## Quick start

In an empty directory for your paper:

```
/paper-writer:init "Acme: Fast Congestion Control for Datacenter Networks"
```

`init` asks for the target venues and the style profile, then creates:

- `paper-writer.toml`
- `paper/main.tex`: an anonymous-review ACM `sigconf` skeleton, with section stubs and an empty `ref.bib`
- the ACM template in `paper/`
- an empty paper vault (`vault/Root.md`, `vault/Vault Layout.md`)
- `outline/`, `design/` and `guidelines/`

It offers to add the hosts the skills need to `.claude/settings.json`. It never overwrites
existing files, so it is safe to re-run.

The template (`acmart.cls`, `ACM-Reference-Format.bst` and the biblatex style files) is not
bundled with the plugin:

- `init` downloads the current release from CTAN and builds the class with `tex`.
- If that fails, it copies the class from your local TeX installation.
- Use `--template tex`, `ctan` or `none` to choose the source yourself.
- To upgrade the template later, delete `paper/acmart.cls` and run `/paper-writer:init --template ctan`.

## Skills

| Skill | What it does |
|---|---|
| `/paper-writer:init ["Name: Subtitle"]` | Scaffold a paper project: config, ACM template, `main.tex`, empty vault, network allowlist |
| `/paper-writer:paper-search <topics>` | Search Semantic Scholar across top venues and insert relevant papers into the vault |
| `/paper-writer:paper-add <title>` | Add one specific paper to the vault |
| `/paper-writer:paper-search-verify` | Audit vault papers: abstracts, venue names, relevance notes |
| `/paper-writer:update-refs` | Complete paper metadata via Crossref |
| `/paper-writer:crossref <venue> <year>` | List ACM/IEEE proceedings papers via Crossref |
| `/paper-writer:find-citations <contexts>` | Pick citations from the vault for a section |
| `/paper-writer:paper-name` | Set up `\name` LaTeX commands from the paper title |
| `/paper-writer:write-intro <outline>` | Draft the introduction (`intro.tex`) and update the bibliography |
| `/paper-writer:write-background <outline>` | Draft the background and motivation section |
| `/paper-writer:design-review <system dir>` | Analyse an implementation and write a design-contributions document |
| `/paper-writer:style-review <file.tex>` | Check a section against your style profile and apply selected fixes |

## Project configuration

Put a `paper-writer.toml` at the project root. The skills find it by searching upward from
the current directory. Every key is optional; these are the defaults:

```toml
[paths]
paper_dir     = "paper"
main_tex      = "paper/main.tex"
bib           = "paper/ref.bib"
vault         = "vault/paper-writer"
outline_dir   = "outline"
design_dir    = "design/design-details"
name_commands = "guidelines/name-commands.md"

[paper]
field         = "computer systems and networking"   # used in drafting prompts
target_venues = ["SIGCOMM", "ASPLOS", "OSDI"]

[venues]
preferred_tier = ["SIGCOMM", "OSDI", "NSDI", "SOSP", "ASPLOS", "MobiCom", "CoNEXT", "EuroSys"]

[style]
profile   = ""   # a profile name under ~/.config/paper-writer/profiles/
path      = ""   # or a profile directory inside the project
overrides = ""   # optional style-overrides.md (a sibling .toml is merged into the rules)
```

`python3 scripts/pw.py config dump` (from the plugin directory, run inside your project)
prints the resolved settings.

## Style profiles

Drafting (`write-intro`, `write-background`) and review (`style-review`) follow a **style
profile**: a directory with

| File | Purpose |
|---|---|
| `style.md` | The prose style guide, pasted into drafting and review prompts |
| `rules.toml` | Banned phrases, avoided transitions, swap suggestions, and which constructions (em-dashes, author-name citations, prose semicolons) to forbid, warn about, or allow |
| `profile.toml` | Metadata: `name` (required), `author`, `version`, `generator`, `created` |
| `rubric.md` | Optional: the judgment rubric `style-review` scores against |

The active profile is chosen in this order: `[style].path`, then `[style].profile` under
`~/.config/paper-writer/profiles/` (or `$XDG_CONFIG_HOME/paper-writer/profiles/`), then a
legacy `guidelines/style.md` in the project, then the neutral baseline profile bundled in
[`profiles/baseline`](profiles/baseline). A project's `style-overrides.md` is added to
drafting prompts after the guide, and `style-overrides.toml` is merged over the rules
(lists are unioned, other values replace).

`rules.toml` format:

```toml
[deterministic]            # each: "forbid" | "warn" | "allow"
em_dash = "forbid"
author_name_citations = "forbid"
prose_semicolons = "warn"

[phrases]
banned = ["delve", "It is important to note that"]
avoided_transitions = ["Moreover,"]

[swaps]                    # lower-case phrase -> replacement; "" means delete by hand
"utilize" = "use"
```

Helper commands:

```
pw.py style resolve                 # which profile is active, and its files
pw.py style rules                   # merged rules as JSON
pw.py style scan paper/intro.tex    # the deterministic checks style-review runs
pw.py style validate <profile-dir>  # check a profile before using it
pw.py style import-legacy guidelines/style.md --out rules.toml
```

`import-legacy` converts a style guide written in the older heading-based format (banned
phrases under `### Filler phrases to never use` and similar headings) into `rules.toml`.

## Network access

The skills call these hosts: `api.semanticscholar.org`, `api.crossref.org`, `doi.org`,
`dl.acm.org`, `arxiv.org`. `/paper-writer:init` offers to add them to your project's
`.claude/settings.json`, both as `permissions.allow` entries (`WebFetch(domain:...)`) and as
sandbox network hosts. `pw.py init allow-network` does the same from a shell.

`init` itself downloads the ACM template from `mirrors.ctan.org`, which redirects to a
mirror near you. If the sandbox blocks that download, `init` falls back to your local TeX
installation.

## Requirements

`python3` (3.11+). The helper `scripts/pw.py` uses only the standard library.

## Semantic Scholar API key

`paper-search` and `paper-add` read an optional key from the `SEMANTIC_SCHOLAR_API_KEY`
environment variable. Without a key, requests go to Semantic Scholar's shared
unauthenticated pool, which is heavily rate-limited (expect frequent HTTP 429 retries).
Request a free key at <https://www.semanticscholar.org/product/api> and export it in your
shell profile:

```
export SEMANTIC_SCHOLAR_API_KEY=...
```

Never commit the key to a project or to this plugin.

## Development

```
uv run pytest
claude plugin validate . --strict
```

## License

MIT. See [LICENSE](LICENSE).
