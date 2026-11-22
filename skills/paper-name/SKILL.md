---
name: paper-name
description: Extract the system name from the paper title in main.tex and set up reusable LaTeX name commands (\name etc.) plus a prompt snippet other skills inject
---

# /paper-writer:paper-name

Extract the system name from the paper title and set up reusable LaTeX name commands in `main.tex`. Also writes a prompt snippet file (`guidelines/name-commands.md`) that other skills inject into their Opus writing agent prompts.

This skill is called by other paper-writing skills (e.g., `/paper-writer:write-intro`, `/paper-writer:write-background`) before their writing step. It can also be invoked standalone.

## Steps

1. **Extract the system name.** Use Read to load `paper/main.tex`. Find the `\title{...}` line and extract the system name — the text before the colon in the title (e.g., from `\title{Acme: Fast Congestion Control for Datacenter Networks}`, extract `Acme`). If the title has no colon, use the first capitalized multi-word phrase. If ambiguous, ask the user to confirm.

2. **Ensure `xspace` package is loaded.** Use Grep to check whether `\usepackage{xspace}` already exists in `paper/main.tex`. If not, use Edit to insert `\usepackage{xspace}` before the `%% end of the preamble` comment line.

3. **Add or update name commands.** Use Grep to check whether `\newcommand{\name}` already exists in `paper/main.tex`.

   - **If the commands already exist:** Use Edit to update the system name within them to match the extracted name.
   - **If they do not exist:** Use Edit to insert the following block before the `%% end of the preamble` comment line (after any `\usepackage` lines):

     ```latex
     \newcommand{\name}{\textsc{SYSNAME}\xspace}
     \newcommand{\names}{\textsc{SYSNAME}s\xspace}
     \newcommand{\boldname}{\textbf{SYSNAME}\xspace}
     \newcommand{\bigname}{SYSNAME\xspace}
     ```

     Replace `SYSNAME` with the actual extracted system name.

4. **Write prompt snippet.** Use Bash to run `mkdir -p guidelines`. Use Write to create (or overwrite) `guidelines/name-commands.md` with the following content, substituting the extracted system name:

   ```markdown
   **System name commands:** The following LaTeX commands are defined in `main.tex` for the system name "{SYSNAME}":
   - `\name` — renders as small caps (`\textsc`) with trailing space; use for most inline references to the system
   - `\names` — plural form (small caps + "s") with trailing space
   - `\boldname` — bold form with trailing space; use when bold emphasis is needed
   - `\bigname` — plain text form with trailing space; use in headings or plain-text contexts

   **Rules:**
   - Always use `\name`, `\names`, `\boldname`, or `\bigname` to refer to the system. Never write the system name as literal text.
   - Use `\name` as the default. Use `\names` for plural references. Use `\boldname` sparingly for emphasis. Use `\bigname` in contexts where small caps or bold would be inappropriate.
   ```

5. **Report.** Print the extracted system name and whether the commands were newly added or updated.
