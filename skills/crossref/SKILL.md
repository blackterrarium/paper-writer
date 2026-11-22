---
name: crossref
description: Search for ACM and IEEE conference papers via Crossref API
allowed-tools: Bash
argument-hint: <conference> <year> (e.g., MobiCom 2025, INFOCOM 2024)
---

Search for conference papers matching "$ARGUMENTS" using the Crossref API.

## Steps

1. Determine the conference name, year, and publisher from the query "$ARGUMENTS". The user may provide short names like "MobiCom 2025" or full names. Map common abbreviations to their full proceeding titles and DOI prefix:

   **ACM conferences (DOI prefix `10.1145`):**
   - MobiCom → "International Conference on Mobile Computing and Networking"
   - SIGCOMM → "ACM SIGCOMM"
   - CCS → "Conference on Computer and Communications Security"
   - MobiSys → "International Conference on Mobile Systems"
   - SenSys → "Conference on Embedded Networked Sensor Systems"
   - IMC → "Internet Measurement Conference"
   - CoNEXT → "International Conference on emerging Networking EXperiments and Technologies"
   - ASPLOS → "Architectural Support for Programming Languages and Operating Systems"
   - SOSP → "Symposium on Operating Systems Principles"
   - KDD → "Knowledge Discovery and Data Mining"
   - CHI → "CHI Conference on Human Factors in Computing Systems"
   - UbiComp → "ACM International Joint Conference on Pervasive and Ubiquitous Computing"
   - PLDI → "Programming Language Design and Implementation"
   - POPL → "Symposium on Principles of Programming Languages"

   **IEEE conferences (DOI prefix `10.1109`):**
   - INFOCOM → "IEEE Conference on Computer Communications"
   - GLOBECOM → "IEEE Global Communications Conference"
   - ICC → "IEEE International Conference on Communications"
   - ICDCS → "IEEE International Conference on Distributed Computing Systems"
   - ICNP → "IEEE International Conference on Network Protocols"
   - SECON → "IEEE International Conference on Sensing, Communication, and Networking"
   - MASS → "IEEE International Conference on Mobile Ad-Hoc and Smart Systems"
   - HPCA → "IEEE International Symposium on High-Performance Computer Architecture"
   - S&P → "IEEE Symposium on Security and Privacy"

   **Joint IEEE/ACM conferences (use both prefixes `10.1145` and `10.1109`):**
   - MICRO → "IEEE/ACM International Symposium on Microarchitecture"
   - ISCA → "International Symposium on Computer Architecture"

   **USENIX conferences (OSDI, NSDI, USENIX ATC, FAST, USENIX Security):** USENIX publishes its proceedings open access on usenix.org and does not register DOIs for them with Crossref, so these papers are generally **not** in Crossref. Tell the user so and point them to the program page (`https://www.usenix.org/conference/<venue><yy>/technical-sessions`, e.g. `nsdi24`) or DBLP (`https://dblp.org/db/conf/<venue>/<venue><yyyy>.html`), then stop. Only the rare USENIX events co-published with ACM appear under `10.1145`.

   For other conferences, use the abbreviation directly in the search query. If the publisher is unknown, try `10.1145` first, then `10.1109` if no results are found.

2. Use `curl` and `python3` to query the Crossref API. Fetch up to 300 results across multiple pages. Determine the correct `doi_prefixes` list based on step 1. Use this bash command pattern:

```bash
python3 << 'PYEOF'
import json, subprocess, urllib.parse, sys, time

def fetch(url, attempts=5):
    """GET a Crossref URL; retry on rate limiting or bad responses, fail loudly."""
    for i in range(attempts):
        r = subprocess.run(["curl", "-s", "-w", "\n%{http_code}", url], capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n")
        if code == "200":
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                pass
        time.sleep(2 ** i)
    sys.exit(f"Crossref request failed after {attempts} attempts (last HTTP status {code or 'none'}): {url}")

conference_query = "<full conference name with year>"
query_encoded = urllib.parse.quote(conference_query)
doi_prefixes = ["<prefix>"]  # e.g. ["10.1145"] for ACM, ["10.1109"] for IEEE, ["10.1145", "10.1109"] for joint

all_items = []
for prefix in doi_prefixes:
    for offset in [0, 100, 200]:
        url = f"https://api.crossref.org/works?query.container-title={query_encoded}&filter=prefix:{prefix},type:proceedings-article&rows=100&offset={offset}&select=title,DOI,author,container-title"
        data = fetch(url)
        items = data.get("message", {}).get("items", [])
        if not items:
            break
        all_items.extend(items)

# Filter to matching conference proceedings (check container-title contains key terms)
key_terms = ["<key identifying words from conference name>"]
filtered = []
seen_dois = set()
for item in all_items:
    ct = (item.get("container-title") or [""])[0].lower()
    doi = item.get("DOI", "")
    if doi in seen_dois:
        continue
    if all(term.lower() in ct for term in key_terms):
        seen_dois.add(doi)
        filtered.append(item)

# Separate main papers from demos/posters/session-details
main = []
other = []
for p in filtered:
    title = (p.get("title") or [""])[0]
    if title.startswith(("Demo:", "Poster:", "Session details:")):
        other.append(p)
    else:
        main.append(p)

print(f"=== Main Conference Papers ({len(main)}) ===\n")
for i, paper in enumerate(main, 1):
    title = (paper.get("title") or ["N/A"])[0]
    doi = paper.get("DOI", "N/A")
    authors_list = paper.get("author", [])
    authors = ", ".join(f"{a.get('given','')} {a.get('family','')}" for a in authors_list[:4])
    if len(authors_list) > 4:
        authors += " et al."
    print(f"{i}. {title}")
    print(f"   Authors: {authors}")
    print(f"   DOI: https://doi.org/{doi}")
    print()

if other:
    print(f"=== Demos, Posters & Other ({len(other)}) ===")
    print(f"({len(other)} items not shown)")
PYEOF
```

3. Adapt the `key_terms` list to contain 2-3 distinctive words from the conference name that will reliably filter the container-title field. For example, for MobiCom use `["Mobile", "Computing", "Networking"]`, for INFOCOM use `["INFOCOM"]`.

4. Present the results to the user in a clean format. Summarize the topic areas covered if there are many papers.
