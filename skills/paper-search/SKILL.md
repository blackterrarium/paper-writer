---
name: paper-search
description: Search for relevant academic papers across top systems/networking/security inside the Obsidian vault
---

# Paper search from Obisdian vault

## Overview

Search for relevant academic papers across top systems/networking/security conferences using the Semantic Scholar API, then insert the results directly into the Obsidian paper vault at `vault/paper-writer/`.

The vault layout is documented in `vault/paper-writer/Vault Layout.md`:
- Each paper is a `.md` file at the vault root.
- Topics form a multi-rooted tree: intermediate topics list children under `## Subtopics`, leaf topics list papers under `## Papers`.
- Papers attach only to **leaf** topics (possibly multiple).

This skill never reads or writes the legacy `search-results/` folder. All vault mutations go through `${CLAUDE_PLUGIN_ROOT}/scripts/pw.py`.

## Steps

1. **Parse topics and generate related topics.** Extract the list of topic descriptions from `$ARGUMENTS` or the user's message. Each topic is a short phrase or sentence describing a research area (e.g., "in-network computing for machine learning"). For each user-provided topic, generate **3 closely related topic phrases** that might surface relevant papers the original query would miss — different angles, adjacent subfields, or alternative framings. Build the full search list: for each original topic, you will search the original topic **plus** its 3 related topics (4 searches per original topic). For each topic (original or related), also extract 3–5 key search terms to use as the query string.

2. **Load the current vault topic tree.** Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault load_tree
   ```

   The output is JSON with `root` (top-level topic titles) and `topics` (map from title to `{path, description, subtopics, papers, is_leaf}`). Keep this in context — it is the authoritative view of what leaves and intermediates already exist.

3. **Plan topic placement (minimal-change rule).** For each search topic (original AND related), pick the **best-fitting existing leaf** where its papers should land. Prioritize minimizing changes to the topic tree in this order:
   1. Map the topic onto an existing leaf with no tree edits. Prefer this whenever the fit is plausible.
   2. If no existing leaf fits, add a new leaf under the closest existing intermediate topic (one new file, one wikilink edit).
   3. Only if the topic doesn't fit any existing intermediate either, convert an existing leaf into an intermediate with new leaves underneath — this is disruptive, so avoid it unless necessary.
   4. Never add a new root-level topic unless the search topic does not fit under any existing root at all.

   Produce two artifacts in your working context:
   - A `{search_topic → target_leaf_title}` mapping (one target per search topic).
   - A list of tree edits needed (new topic files to create, new subtopic wikilinks to add).

   **Apply the tree edits now**, before searching, so the vault stays consistent even if the rest of the skill is interrupted. For each edit:

   - To create a new leaf topic file:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault create_topic \
       "vault/paper-writer/{New Topic Title}.md" "{one-sentence description}" --leaf
     ```
   - To attach a new leaf under an existing parent:
     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault add_subtopic \
       "vault/paper-writer/{Parent Topic}.md" "{New Topic Title}"
     ```
   - To convert an existing leaf into an intermediate: read the file, move its `## Papers` list to a new child leaf (via `create_topic --leaf` + `attach_paper`), then edit the original file to replace `## Papers` with `## Subtopics` using Read/Edit.

4. **Run the Semantic Scholar search.** Create a temp directory for intermediate JSON I/O, then run the search script below. Substitute `{topics_json}` with a JSON array of `{"topic": "...", "query": "..."}` objects covering every search topic (original + related), and `{tmp_dir}` with the path from `mktemp -d`.

   ```bash
   tmp_dir=$(mktemp -d -t paper-search-XXXXXX)
   echo "$tmp_dir"
   python3 << 'PYEOF'
   import json, subprocess, urllib.parse, sys, time, os, re

   tmp_dir = """{tmp_dir}"""
   topics = json.loads("""{topics_json}""")

   # Optional: set SEMANTIC_SCHOLAR_API_KEY in your environment for higher rate limits.
   # Without it, requests are unauthenticated (lower limits; the retry loop handles 429s).
   S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
   S2_AUTH = ["-H", f"x-api-key: {S2_API_KEY}"] if S2_API_KEY else []

   SHORT_NAMES = {
       "mobile computing and networking": "MobiCom", "mobicom": "MobiCom",
       "sigcomm": "SIGCOMM",
       "computer and communications security": "CCS",
       "mobile systems": "MobiSys", "mobisys": "MobiSys",
       "embedded networked sensor": "SenSys", "sensys": "SenSys",
       "internet measurement": "IMC",
       "emerging networking experiments": "CoNEXT", "conext": "CoNEXT",
       "architectural support for programming": "ASPLOS", "asplos": "ASPLOS",
       "operating systems principles": "SOSP", "sosp": "SOSP",
       "knowledge discovery": "KDD", "kdd": "KDD",
       "human factors": "CHI", "chi conference": "CHI",
       "ubiquitous computing": "UbiComp", "ubicomp": "UbiComp",
       "programming language design": "PLDI", "pldi": "PLDI",
       "principles of programming languages": "POPL", "popl": "POPL",
       "operating systems design and implementation": "OSDI", "osdi": "OSDI",
       "networked systems design": "NSDI", "nsdi": "NSDI",
       "microarchitecture": "MICRO", "micro": "MICRO",
       "computer architecture": "ISCA", "isca": "ISCA",
       "infocom": "INFOCOM",
       "global communications": "GLOBECOM", "globecom": "GLOBECOM",
       "international conference on communications": "ICC",
       "distributed computing systems": "ICDCS", "icdcs": "ICDCS",
       "network protocols": "ICNP", "icnp": "ICNP",
       "sensing, communication": "SECON", "secon": "SECON",
       "mobile ad-hoc": "MASS", "mass": "MASS",
       "high-performance computer architecture": "HPCA", "hpca": "HPCA",
       "security and privacy": "S&P",
       "cloud computing": "SoCC", "socc": "SoCC",
       "networked systems design and implementation": "NSDI",
       "symposium on networked systems design and implementation": "NSDI",
       "operating systems design": "OSDI",
       "annual technical conference": "ATC", "usenix annual": "ATC",
       "security symposium": "USENIX Security",
       "file and storage": "FAST", "fast": "FAST",
   }

   CONFERENCES = [
       "mobile computing and networking", "mobicom",
       "sigcomm",
       "computer and communications security",
       "mobile systems", "mobisys",
       "embedded networked sensor", "sensys",
       "internet measurement",
       "emerging networking experiments", "conext",
       "architectural support for programming", "asplos",
       "operating systems principles", "sosp",
       "knowledge discovery", "kdd",
       "human factors", "chi conference",
       "ubiquitous computing", "ubicomp",
       "programming language design", "pldi",
       "principles of programming languages", "popl",
       "operating systems design and implementation", "osdi",
       "networked systems design", "nsdi",
       "microarchitecture", "micro",
       "computer architecture", "isca",
       "infocom",
       "global communications", "globecom",
       "international conference on communications",
       "distributed computing systems", "icdcs",
       "network protocols", "icnp",
       "sensing, communication", "secon",
       "mobile ad-hoc", "mass",
       "high-performance computer architecture", "hpca",
       "security and privacy",
       "cloud computing", "socc",
       "networked systems design and implementation",
       "symposium on networked systems design and implementation",
       "operating systems design",
       "annual technical conference", "usenix annual",
       "security symposium",
       "file and storage",
   ]

   last_request_time = 0.0

   def s2_request(url, max_retries=3):
       global last_request_time
       elapsed = time.time() - last_request_time
       if elapsed < 1.2:
           time.sleep(1.2 - elapsed)

       for attempt in range(max_retries + 1):
           last_request_time = time.time()
           result = subprocess.run(
               ["curl", "-s", *S2_AUTH, "-w", "\n%{http_code}", url],
               capture_output=True, text=True
           )
           lines = result.stdout.rsplit("\n", 1)
           body = lines[0] if len(lines) > 1 else result.stdout
           status = int(lines[1]) if len(lines) > 1 else 0

           if status == 429:
               wait = 2 ** (attempt + 1)
               print(f"  Rate limited. Retrying in {wait}s...", file=sys.stderr)
               time.sleep(wait)
               last_request_time = time.time()
               continue
           if status >= 500:
               if attempt < 1:
                   time.sleep(3)
                   last_request_time = time.time()
                   continue
               return None
           if status not in (200, 0):
               return None

           try:
               data = json.loads(body)
           except json.JSONDecodeError:
               return None

           if "error" in data or "message" in data:
               return None
           return data
       return None

   def slugify(s, max_len=60):
       s = re.sub(r'[^a-z0-9 ]', '', s.lower())
       s = re.sub(r'\s+', '-', s.strip())
       return s[:max_len].rstrip('-')

   def format_paper(item):
       title = item.get("title") or "N/A"
       ext_ids = item.get("externalIds") or {}
       doi = ext_ids.get("DOI", "") or ""
       authors_list = item.get("authors") or []
       authors = ", ".join(a.get("name", "").strip() for a in authors_list[:4])
       if len(authors_list) > 4:
           authors += " et al."
       year = str(item.get("year") or "")
       pub_venue = item.get("publicationVenue") or {}
       venue_full = pub_venue.get("name") or item.get("venue") or "Unknown"
       venue_lower = venue_full.lower()
       short_venue = ""
       for frag, abbrev in SHORT_NAMES.items():
           if frag in venue_lower:
               short_venue = abbrev
               break
       if short_venue and year:
           short_venue = f"{short_venue} {year}"
       abstract = item.get("abstract") or ""
       return {
           "title": title, "doi": doi, "authors": authors,
           "published": year if year else "Unknown",
           "venue": venue_full, "venue_short": short_venue,
           "abstract": abstract,
       }

   def is_target_conference(item):
       pub_venue = item.get("publicationVenue") or {}
       venue_name = pub_venue.get("name") or item.get("venue") or ""
       venue_lower = venue_name.lower()
       return any(frag in venue_lower for frag in CONFERENCES)

   for i, entry in enumerate(topics):
       topic = entry["topic"]
       query = entry["query"]
       query_encoded = urllib.parse.quote(query)
       slug = slugify(topic)

       print(f"[{i+1}/{len(topics)}] Searching: {topic}", file=sys.stderr)

       all_items = []
       for offset in [0, 100]:
           url = (
               f"https://api.semanticscholar.org/graph/v1/paper/search"
               f"?query={query_encoded}"
               f"&offset={offset}&limit=100"
               f"&fields=title,authors,year,venue,abstract,externalIds,publicationVenue"
           )
           data = s2_request(url)
           if not data:
               break
           items = data.get("data", [])
           if not items:
               break
           all_items.extend(items)

       filtered = []
       general = []
       seen_ids = set()
       for item in all_items:
           paper_id = item.get("paperId", "")
           if paper_id in seen_ids:
               continue
           seen_ids.add(paper_id)
           title = item.get("title") or ""
           if title.startswith(("Demo:", "Poster:", "Session details:")):
               continue
           if is_target_conference(item):
               filtered.append(item)
           else:
               general.append(item)

       results = filtered[:]
       if len(results) < 5:
           results.extend(general[:10 - len(results)])

       output = {
           "topic": topic,
           "papers": [
               {**format_paper(item), "from_target_conference": is_target_conference(item)}
               for item in results[:30]
           ],
       }

       out_path = os.path.join(tmp_dir, f"{slug}.json")
       with open(out_path, "w") as f:
           json.dump(output, f, indent=2)

       print(f"  Found {len(filtered)} target + {len(general)} general papers", file=sys.stderr)

   print(json.dumps({"status": "ok", "topics_searched": len(topics), "tmp_dir": tmp_dir}))
   PYEOF
   ```

   The script writes one `{slug}.json` per search topic into `$tmp_dir`. These files are intermediate fan-out I/O only; they are deleted in step 7.

5. **Fan out Sonnet agents for relevance assessment and vault insertion — one per search topic, all in a single message.** Use `model: "sonnet"` for each agent. Pass each agent its specific topic, the JSON file path, and the target leaf file path decided in step 3. The agent's prompt:

   > You are a research paper relevance assessor and vault inserter. Your task is to process papers found for the search topic **"{topic}"** and insert the relevant ones into the paper vault, attached to the leaf topic **{target_leaf_title}** (`vault/paper-writer/{target_leaf_title}.md`).
   >
   > The target leaf's description: {target_leaf_description}
   >
   > **Step 1: Read the JSON results** at `{tmp_dir}/{slug}.json` using the Read tool.
   >
   > **Step 2: For each paper**, decide whether it is genuinely relevant to the search topic "{topic}" based on title and abstract. Discard clearly irrelevant ones. For each relevant paper:
   >
   > a. **Apply venue verification:** cross-check `venue` against `venue_short`. If the short name does not match the full venue name (e.g., short says "SIGCOMM" but full is "Internet Measurement Conference"), correct it. For workshops, use the workshop's own name (e.g., "HotNets", "SPIN") rather than the parent conference. The corrected short name is for the `Venue` field: format as `{venue_full} ({venue_short})`, or just `{venue_full}` if there is no short name.
   >
   > b. **Check the vault for the DOI** (skip if the DOI is empty — fall back to step c unconditionally). Run:
   >
   > ```bash
   > python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault find_doi "{doi}"
   > ```
   >
   > If the output is non-empty, the paper already exists in the vault at that path. Do **not** write a new paper file. Instead, attach the existing paper to the target leaf (step d) using the existing paper's title (read the file's `# {Title}` line to get it).
   >
   > c. **If the paper is new**, write it to the vault via:
   >
   > ```bash
   > python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault write_paper '{"title":"...","doi":"...","authors":"...","year":"...","venue":"{venue_full} ({venue_short})","abstract":"...","relevance":"1-2 sentence relevance assessment to the topic \"{topic}\""}'
   > ```
   >
   > Use `Bash` and quote the JSON carefully. If `doi` is empty, pass an empty string; the helper writes `Not available`. If `abstract` is empty, pass an empty string; the helper writes `Not available`. If the short venue is empty, pass just `{venue_full}` as venue.
   >
   > d. **Attach the paper to the target leaf:**
   >
   > ```bash
   > python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pw.py" vault attach_paper \
   >   "vault/paper-writer/{target_leaf_title}.md" "{paper_title}"
   > ```
   >
   > where `{paper_title}` is the paper's exact title as it appears in its vault file name (without the `.md` suffix). For newly written papers, this is the sanitized title printed by `write_paper`. For existing papers, this is the filename stem.
   >
   > **Step 3: Return a JSON summary** with keys `created` (list of paper titles newly written), `attached_existing` (list of paper titles that already existed and were attached to this leaf), and `skipped` (list with reasons).

6. **Existing-paper placement review.** After all agents complete, for each leaf that received new papers in step 5, briefly review the adjacent leaves under the same parent topic (using the topic tree from step 2). If any paper currently attached to a sibling leaf is an obviously better fit for the newly-refined leaf, add a wikilink on that leaf too via `attach_paper`. This is the optional "paper update" step from `Vault Skills.md`. Keep the scope to direct siblings — do not traverse the whole tree.

7. **Clean up the temp directory.**

   ```bash
   rm -rf "$tmp_dir"
   ```

8. **Report** to the user:
   - Search topics processed (original + related).
   - New paper files created in the vault.
   - Existing papers attached to new/refined leaves.
   - Any topic tree edits (new leaves created, new subtopic links added).
