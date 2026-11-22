# paper-writer

A [Claude Code](https://claude.com/claude-code) plugin for writing systems and networking
research papers. It keeps related work in an Obsidian-style vault, finds papers through
Semantic Scholar and Crossref, selects citations, drafts LaTeX sections, and reviews prose
against an author style guide.

> **Status: v0.1 in progress.** Skills still assume the default project layout below.
> Per-project configuration, style profiles, and `/paper-writer:init` are coming next.

## Install

```
/plugin marketplace add blackterrarium/paper-writer
/plugin install paper-writer@paper-writer
```

To try a local checkout: `claude --plugin-dir /path/to/paper-writer`.

## Skills

| Skill | What it does |
|---|---|
| `/paper-writer:paper-search <topics>` | Search Semantic Scholar across top venues and insert relevant papers into the vault |
| `/paper-writer:paper-add <title>` | Add one specific paper to the vault |
| `/paper-writer:paper-search-verify` | Audit vault papers: abstracts, venue names, relevance notes |
| `/paper-writer:update-refs` | Complete paper metadata via Crossref |
| `/paper-writer:crossref <venue> <year>` | List ACM/IEEE proceedings papers via Crossref |
| `/paper-writer:find-citations <contexts>` | Pick citations from the vault for a section |
| `/paper-writer:paper-name` | Set up `\name` LaTeX commands from the paper title |
| `/paper-writer:write-intro <outline>` | Draft `paper/intro.tex` and update `paper/ref.bib` |
| `/paper-writer:write-background <outline>` | Draft `paper/background.tex` |
| `/paper-writer:design-review <system dir>` | Analyse an implementation and write a design-contributions document |
| `/paper-writer:style-review <file.tex>` | Report style-guide violations and apply selected fixes |

## Default project layout

```
paper/            main.tex, intro.tex, background.tex, ref.bib
vault/paper-writer/   Root.md, topic notes, one note per paper
guidelines/style.md   author style guide (read by writing and review skills)
outline/          section outlines
design/design-details/  design-review output
```

## Network access

The skills call these hosts; allow them in your project's `.claude/settings.json`
(`permissions.allow` with `WebFetch(domain:...)`, and the sandbox network allowlist if you
use the sandbox): `api.semanticscholar.org`, `api.crossref.org`, `doi.org`, `dl.acm.org`,
`arxiv.org`.

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
