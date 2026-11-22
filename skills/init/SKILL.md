---
name: init
description: Set up a paper project in the current directory - paper-writer.toml, the ACM LaTeX template, main.tex, an empty paper vault, and the network allowlist the skills need. Safe to re-run; never overwrites files.
argument-hint: "[\"System: Subtitle\"] [--venues A,B] [--profile NAME] [--template auto|ctan|tex|none]"
---

# /paper-writer:init

Scaffold a paper project in the current working directory so the other paper-writer skills can run. It creates:

- `paper-writer.toml`: the project config (paths, field, target venues, style profile)
- `paper/main.tex`: an anonymous-review ACM `sigconf` skeleton, plus `intro.tex` and `background.tex` stubs, an empty `ref.bib`, and a LaTeX `.gitignore`
- the ACM template (`acmart.cls`, `ACM-Reference-Format.bst`, and the biblatex style files) in `paper/`. By default it is downloaded from CTAN (the newest release) and falls back to the local TeX installation
- `vault/Root.md` and `vault/Vault Layout.md`: an empty paper vault
- `outline/`, `design/design-details/` and `guidelines/`

Existing files are never overwritten. If `paper-writer.toml` already exists, it is kept and the paths it names are scaffolded.

Throughout this skill, `PW` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py"`, run from the project directory.

## Steps

1. **Check the location.** Run `pwd` and `ls -A`. Stop and ask the user to `cd` into the project first if the directory is their home directory, `/`, or the paper-writer plugin itself. If it already has `paper-writer.toml`, say that init will only fill in missing pieces.

2. **Gather settings.** Take anything given in `$ARGUMENTS`: a quoted title, `--venues`, `--profile`, `--field`, `--vault`, `--template`. Run `PW init profiles` to list the user's style profiles. For each setting not given in `$ARGUMENTS`, ask the user in a single AskUserQuestion call:
   - **Title**: the paper title in the form `Name: Subtitle` (the `paper-name` skill takes the system name from the text before the colon). Offer "Decide later" (keeps the placeholder `System: A Descriptive Subtitle`).
   - **Target venues**: offer the default `SIGCOMM, ASPLOS, OSDI`, plus `NSDI, SIGCOMM` and `OSDI, SOSP, EuroSys`.
   - **Style profile**: one option per profile listed by `PW init profiles`, plus "Baseline (no personal profile)". If there are no profiles, skip the question and use the baseline. Mention that a profile can be built with the private `paper-style` plugin's `writing-style` skill, or by hand following the plugin README.

   Skip this step entirely when `paper-writer.toml` already exists.

3. **Scaffold.** Run:

   ```bash
   PW init [--title "<title>"] [--venues "<A,B,C>"] [--profile <name>] [--field "<field>"] [--vault <dir>] [--template <src>]
   ```

   Leave out any flag the user did not set (`--profile` with the baseline). The command prints JSON with `created`, `skipped` and `notes`.
   - The CTAN download needs network access to `mirrors.ctan.org`, which redirects to a mirror, and `tex` to build `acmart.cls` from source. If the CTAN step fails, init falls back to the local TeX installation on its own, and `notes` says which source was used and why CTAN failed.
   - init never replaces an existing `acmart.cls`. To move to the newest release later, delete `<paper_dir>/acmart.cls` and run `PW init --template ctan`. That command needs network access to CTAN.
   - If it fails with "could not install the ACM template" and the user has no TeX installation, everything else has already been created. Tell the user to install TeX Live (or MacTeX), then re-run `/paper-writer:init --template tex`. Alternatively, they can copy `acmart.cls` and `ACM-Reference-Format.bst` into `paper/` by hand.

4. **Network allowlist.** The skills call `api.semanticscholar.org`, `api.crossref.org`, `doi.org`, `dl.acm.org` and `arxiv.org`. Run `PW init allow-network --print`. If `added` is empty, say the allowlist is already in place and continue. Otherwise list the entries in `added` and ask the user whether to add them to the project's `.claude/settings.json`. These are `WebFetch` permissions and sandbox network hosts. On yes, use the Write tool to write the `settings` object from the output to the `file` path, as JSON with 2-space indentation. Use the Write tool because the sandbox blocks shell writes to that file. On no, point them to the "Network access" section of the plugin README.

5. **Check the build (optional).** If `latexmk` is available (`command -v latexmk`), run `cd <paper_dir> && latexmk -pdf -interaction=nonstopmode -silent main.tex` and report whether `main.pdf` was produced. Warnings about missing citations are expected in a new project. Otherwise skip this step.

6. **Report.** Summarize what was created and skipped and which acmart version was installed and from where. Then give the next steps:
   - `/paper-writer:paper-search <topics>` to fill the vault
   - write an outline in `outline/`, then `/paper-writer:write-intro outline/<file>.md`
   - edit `\acmConference` in `main.tex` once the venue is known
   - if the project is a git repository, commit the scaffold
