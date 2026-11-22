---
name: paper-add
description: Find a specific paper by title using Semantic Scholar and add it to the Obsidian.
---

# Paper search and add them into Obisdian vault

## Overview

Find a specific paper by title using Semantic Scholar and add it to the Obsidian paper vault at `{paths.vault}/`, attaching it to the most relevant leaf topic(s).

The vault layout is documented in `{paths.vault}/Vault Layout.md`: papers live as individual `.md` files at the vault root and are attached to one or more leaf topic files via `[[wikilinks]]` under a `## Papers` section. Papers are deduplicated by DOI.

This skill never reads or writes the legacy `search-results/` folder. All vault mutations go through `${CLAUDE_PLUGIN_ROOT}/scripts/pw.py`.

## Configuration

Before step 1, resolve the project configuration:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" config dump
```

It prints the project's `paper-writer.toml` settings as JSON, or the defaults when the project has none. Throughout this skill, `{paths.*}`, `{paper.*}` and `{venues.*}` stand for values from that output: substitute them before running any command or writing any prompt. Lists such as `{venues.preferred_tier}` are written comma-separated. Run commands from `project_root`. `pw.py vault` commands already use `{paths.vault}` as the vault root.

## Steps

1. **Parse the paper title.** Extract the paper title from `$ARGUMENTS` or the user's message. This should be a specific paper title (e.g., "Data Center TCP (DCTCP)"), not a broad topic.

2. **Search Semantic Scholar by title.** Run the following Python script via Bash, substituting `{paper_title}` with the user's paper title:

   ```bash
   python3 << 'PYEOF'
   import json, os, subprocess, urllib.parse, sys, time, re

   # Optional: set SEMANTIC_SCHOLAR_API_KEY in your environment for higher rate limits.
   # Without it, requests are unauthenticated (lower limits; the retry loop handles 429s).
   S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
   S2_AUTH = ["-H", f"x-api-key: {S2_API_KEY}"] if S2_API_KEY else []

   paper_title = """{paper_title}"""
   query_encoded = urllib.parse.quote(paper_title)

   import sys
   sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
   from pwlib.venues import short_name, is_search_target  # the plugin's single venue table

   def normalize(s):
       return set(re.sub(r'[^a-z0-9 ]', '', s.lower()).split())

   def title_similarity(a, b):
       wa, wb = normalize(a), normalize(b)
       if not wa or not wb:
           return 0.0
       intersection = wa & wb
       return len(intersection) / max(len(wa), len(wb))

   s2_url = (
       f"https://api.semanticscholar.org/graph/v1/paper/search"
       f"?query={query_encoded}"
       f"&limit=10"
       f"&fields=title,authors,year,venue,abstract,externalIds,publicationVenue"
   )

   body = ""
   for attempt in range(4):
       result = subprocess.run(
           ["curl", "-s", *S2_AUTH, "-w", "\n%{http_code}", s2_url],
           capture_output=True, text=True
       )
       lines = result.stdout.rsplit("\n", 1)
       body = lines[0] if len(lines) > 1 else result.stdout
       status = int(lines[1]) if len(lines) > 1 else 0

       if status == 429:
           wait = 2 ** (attempt + 1)
           print(f"Rate limited. Retrying in {wait}s...", file=sys.stderr)
           time.sleep(wait)
           continue
       if status >= 500:
           if attempt < 1:
               time.sleep(3)
               continue
           break
       break

   try:
       data = json.loads(body)
   except json.JSONDecodeError:
       print(json.dumps({"error": "Invalid JSON from Semantic Scholar"}))
       sys.exit(1)

   items = data.get("data", [])
   if not items:
       print(json.dumps({"error": "No results from Semantic Scholar", "candidates": []}))
       sys.exit(0)

   scored = []
   for item in items:
       title = item.get("title") or ""
       score = title_similarity(paper_title, title)
       scored.append((score, item))
   scored.sort(key=lambda x: -x[0])

   best_score, best_item = scored[0]
   if best_score < 0.6:
       candidates = []
       for score, item in scored[:3]:
           ext = item.get("externalIds") or {}
           candidates.append({
               "title": item.get("title", ""),
               "doi": ext.get("DOI", ""),
               "score": round(score, 3),
           })
       print(json.dumps({"error": "No confident match", "best_score": round(best_score, 3), "candidates": candidates}, indent=2))
       sys.exit(0)

   item = best_item
   title = item.get("title") or "N/A"
   authors_list = item.get("authors") or []
   authors = ", ".join(a.get("name", "").strip() for a in authors_list[:4])
   if len(authors_list) > 4:
       authors += " et al."
   year = str(item.get("year") or "")
   ext_ids = item.get("externalIds") or {}
   doi = ext_ids.get("DOI", "") or ""
   pub_venue = item.get("publicationVenue") or {}
   venue_full = pub_venue.get("name") or item.get("venue") or "Unknown"
   short_venue = short_name(venue_full, year)
   abstract = item.get("abstract") or ""

   print(json.dumps({
       "title": title,
       "doi": doi,
       "authors": authors,
       "published": year if year else "Unknown",
       "venue": venue_full,
       "venue_short": short_venue,
       "abstract": abstract,
       "match_score": round(best_score, 3),
   }, indent=2))
   PYEOF
   ```

3. **Handle the result.**
   - If the script outputs `"error": "No confident match"`, show the user the top candidates and ask which one to add (or ask them to refine the title). Stop.
   - If the script outputs a successful match, proceed to step 4.
   - **Venue verification:** cross-check the returned `venue_short` against `venue` (the full name). If the short name does not plausibly match the actual venue (e.g., short says "SIGCOMM" but full is "Internet Measurement Conference"), correct the short name. For workshops, use the workshop's own name rather than the parent conference.

4. **DOI dedup against the vault.** Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault find_doi "{doi}"
   ```

   If the output is non-empty, the paper is already in the vault at that path. Read the file to report its current topic attachments (by searching for `[[{paper file stem}]]` in topic files) and tell the user the paper already exists. Do not create a duplicate. Stop.

   If the DOI is empty (Semantic Scholar has no DOI for this paper), fall back to matching by exact title: run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault list_paper_files` and Grep for a file whose first-line title matches. If found, report and stop.

5. **Load the topic tree** to understand where the paper could go:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault load_tree
   ```

   The JSON lists every topic with its description and marks leaves (`is_leaf: true`).

6. **Pick leaf parents based on the paper's content.** Using the paper's title, abstract, and venue, select **one or more existing leaf topics** whose descriptions make sense as homes for this paper. Criteria:
   - The paper's topic must plausibly fall within the leaf's description.
   - If the paper spans multiple leaves (e.g., a paper about "congestion control offloaded to SmartNICs" could attach to both `Datacenter Congestion Control` and `SmartNIC Offloading`), pick all genuinely-relevant leaves.
   - If **no** existing leaf fits well, default to attaching to the closest existing leaf and warn the user that the topic tree may need to be expanded (paper-add is scoped to one paper and should not silently mint new topics — use `/paper-writer:paper-search` for that).

7. **Write the paper file to the vault.** Construct the JSON blob with the corrected venue string (`"{venue_full} ({venue_short})"`, or just `"{venue_full}"` if the short name is empty), and run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault write_paper '{"title":"...","doi":"...","authors":"...","year":"...","venue":"...","abstract":"...","relevance":"Manually added by title search. Attached to {list of leaf topics}."}'
   ```

   The command prints the path of the newly created file. If `doi` or `abstract` is empty, pass an empty string and the helper writes `Not available`.

8. **Attach the paper to each chosen leaf.** For every leaf topic selected in step 6:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault attach_paper \
     "{paths.vault}/{leaf-title}.md" "{paper-file-stem}"
   ```

   where `{paper-file-stem}` is the paper file name without `.md` (this is the sanitized title — use `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault sanitize "{title}"` if you need to compute it).

9. **Report** to the user:
   - Paper title, DOI, Semantic Scholar match score.
   - The vault file path that was created.
   - The list of leaf topics it was attached to.
   - If the match score was below 0.8, note that the user should verify it is the correct paper.
