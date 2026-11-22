---
name: update-refs
description: Verify and complete paper metadata (title, authors, full and short venue, year) in markdown reference files using the Crossref API
---

# /paper-writer:update-refs

Verify and complete paper metadata in markdown reference files. For each paper entry, ensures all required BibTeX-relevant fields are present: title, authors, full venue name, short venue name, and publication year. Uses the Crossref API to retrieve any missing data.

## Steps

1. **Parse input and discover files.** Take the folder path from `$ARGUMENTS`. Use Glob to find all `*.md` files in that folder. Exclude any file named `consolidated.md`. If no files are found, report this to the user and stop.

2. **Fan-out: one Sonnet agent per file.** Launch one **Sonnet** Agent per file, **all in parallel in a single message**. Use `model: "sonnet"` for each agent. Each agent receives the following prompt (with the actual file path substituted):

   > You are a reference metadata verification agent. Your task is to verify and complete paper metadata in **{file_path}**.
   >
   > **Step 1: Read the file** using the Read tool. Parse each numbered paper entry. Each entry may have these fields: title (bold text), DOI, Authors, Published, Venue, Relevance.
   >
   > **Step 2: Check each entry** for these required fields:
   > - **Title**: the bold text after the number
   > - **DOI**: a `https://doi.org/...` link
   > - **Authors**: a real author list (treat `(see DOI)` or empty as missing)
   > - **Published**: publication year (e.g., `2024`)
   > - **Venue**: full venue name AND short venue name in parentheses (e.g., `Proceedings of the ACM SIGCOMM 2024 Conference (SIGCOMM 2024)`)
   >
   > A venue line like `Venue: Proceedings of the ACM SIGCOMM 2024 Conference` without a parenthetical short name counts as missing the short venue.
   >
   > **Step 3: For each paper entry that has any missing field**, launch a **Haiku** agent (`model: "haiku"`) to look it up. Launch **all Haiku agents in parallel in a single message**. Each Haiku agent receives this prompt (with paper-specific values substituted):
   >
   > > You are a metadata lookup agent. Look up complete metadata for this paper:
   > >
   > > - Title: {title}
   > > - DOI: {doi_if_available_or_NONE}
   > >
   > > Run this bash command to query Crossref:
   > >
   > > ```bash
   > > python3 << 'PYEOF'
   > > import json, subprocess, urllib.parse, time
   > >
   > > doi = "{doi_or_empty}"
   > > title = """{title}"""
   > >
   > > import sys
   > > sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
   > > from pwlib.venues import short_name, is_search_target  # the plugin's single venue table
   > >
   > > if doi:
   > >     url = f"https://api.crossref.org/works/{doi}"
   > >     result = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
   > >     try:
   > >         data = json.loads(result.stdout)
   > >         item = data.get("message", {})
   > >     except json.JSONDecodeError:
   > >         item = {}
   > > else:
   > >     encoded = urllib.parse.quote(title)
   > >     url = f"https://api.crossref.org/works?query.bibliographic={encoded}&rows=3&select=title,DOI,author,container-title,short-container-title,published"
   > >     result = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
   > >     try:
   > >         data = json.loads(result.stdout)
   > >         items = data.get("message", {}).get("items", [])
   > >         item = items[0] if items else {}
   > >     except (json.JSONDecodeError, IndexError):
   > >         item = {}
   > >
   > > if not item:
   > >     print("CROSSREF_RESULT: NOT_FOUND")
   > > else:
   > >     # Extract fields
   > >     cr_title = (item.get("title") or [""])[0]
   > >     cr_doi = item.get("DOI", "")
   > >
   > >     authors_list = item.get("author", [])
   > >     authors = ", ".join(
   > >         f"{a.get('given', '')} {a.get('family', '')}"
   > >         for a in authors_list[:4]
   > >     )
   > >     if len(authors_list) > 4:
   > >         authors += " et al."
   > >
   > >     pub_parts = item.get("published", {}).get("date-parts", [[None]])[0]
   > >     year = str(pub_parts[0]) if pub_parts and pub_parts[0] else ""
   > >
   > >     venue_full = (item.get("container-title") or [""])[0]
   > >     short_ct = (item.get("short-container-title") or [""])[0]
   > >
   > >     if short_ct:
   > >         short_venue = f"{short_ct} {year}" if year else short_ct
   > >     else:
   > >         short_venue = short_name(venue_full, year)
   > >
   > >     print(f"CROSSREF_RESULT: FOUND")
   > >     print(f"CR_TITLE: {cr_title}")
   > >     print(f"CR_DOI: {cr_doi}")
   > >     print(f"CR_AUTHORS: {authors}")
   > >     print(f"CR_YEAR: {year}")
   > >     print(f"CR_VENUE_FULL: {venue_full}")
   > >     print(f"CR_VENUE_SHORT: {short_venue}")
   > > PYEOF
   > > ```
   > >
   > > After running the script, respond with EXACTLY this structured format (fill in from Crossref results):
   > >
   > > ```
   > > PAPER_UPDATE:
   > > TITLE: {title from Crossref, or original if not found}
   > > DOI: {doi}
   > > AUTHORS: {authors}
   > > YEAR: {year}
   > > VENUE_FULL: {full venue name}
   > > VENUE_SHORT: {short venue name with year, e.g. SIGCOMM 2024}
   > > STATUS: {FOUND or NOT_FOUND}
   > > ```
   >
   > **Step 4: Collect results from all Haiku agents.** For each paper, merge the Crossref data with the existing entry: only fill in fields that were missing or incomplete. Preserve the original `Relevance:` text verbatim.
   >
   > **Step 5: Rewrite the file** using the Write tool. Preserve the file's section structure (`# Papers:`, `## From Target Conferences`, `## From General Search`, etc.) exactly. Use this format for each entry:
   >
   > ```
   > 1. **{title}**
   >    - DOI: https://doi.org/{doi}
   >    - Authors: {authors}
   >    - Published: {year}
   >    - Venue: {full_venue} ({short_venue})
   >    - Relevance: {original relevance text, unchanged}
   > ```
   >
   > If a paper already had all required fields, keep it unchanged. If Crossref returned no results for a paper, keep the original entry unchanged and note it in your summary.
   >
   > **Step 6: Return a summary** listing: file name, total papers, how many were already complete, how many were updated, how many could not be resolved, and which specific fields were filled in.

3. **Report results.** After all Sonnet agents complete, present a consolidated summary to the user:
   - Total files processed
   - Total papers checked
   - Papers updated vs. already complete vs. unresolved
   - Any papers that could not be resolved (list title and file)
