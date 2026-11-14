# Medical & Ophthalmic AI Literature Tracker

A **public, auditable** GitHub Actions + GitHub Pages tracker for Medical AI / Medical Agent and Ophthalmic AI / Ophthalmic Agent papers. Designed to separate *retrieval completion* from *scholarly appraisal*.

## What this does

- **Scheduled GitHub Actions** daily at `17:30 UTC` (`09:30 PST` / `10:30 PDT`), ahead of a separate ChatGPT recap at `19:00 America/Los_Angeles`.
- **Manual trigger:** `Actions` → `Medical & Ophthalmic AI Literature` → `Run workflow` → choose 1/7/14/30 backfill days → **Run workflow**.
- Independent PubMed ESearch/EFetch (**EPDAT, EDAT, CRDT**), arXiv Atom API (**submission window + updated-date sorting**), medRxiv date/cursor API with alternate official host, and Crossref online-publication index queries for a fixed list of journals.
- Full query audit: query, date field/window, upstream count, fetched count, next cursor, completion/failure and matched IDs.
- Historical catalog deduplicated by DOI, paper identifier, then *exact normalized title*. Rolling re-checks of the last 7 days and bounded checks of known medRxiv versions across 30 days.
- **English GitHub Pages dashboard** with a publication calendar, daily paper counts, and combined date, keyword/journal and research-area filters across the full historical catalog. Article cards show journal names or preprint servers rather than retrieval databases.
- Machine-readable `data/catalog.json`, `data/latest.json` and `data/history.json`, with a query-completion audit on the dashboard.
- **No AI-generated scientific claims in pipeline**. Candidate grouping and priority are rules-based, not full-paper clinical appraisal. The separate ChatGPT task reads actual reports and verifies important abstracts before summarizing.

## Install / publish

> **Privacy:** GitHub Pages is a public site. This template's code and generated DOI/title audit catalog are intended to be public. Do not put patient data, private Notion exports, API tokens, personal notes or other private files into this repository. GitHub Pages is not a secure storage location.

1. **Fast route with GitHub CLI:** install [GitHub CLI](https://cli.github.com/), run `gh auth login`, then run `bash scripts/bootstrap_github.sh yyyanbj` from the extracted package. This creates the repository, uploads all files, and attempts to enable Pages automatically. You can skip the remaining manual repository-creation steps if it succeeds. Or, create a **public** repository named `medical-ophthalmic-ai-tracker` under your GitHub account. If your account is not `yyyanbj`, modify the website URL used by the ChatGPT scheduled recap. Choose `main` as the default branch.
2. **Manual alternative:** unzip this package, open a terminal inside the `medical-ophthalmic-ai-tracker` folder and run:

   ```bash
   git init -b main
   git add .
   git commit -m "Initial medical AI literature tracker"
   git remote add origin https://github.com/<YOUR_USERNAME>/medical-ophthalmic-ai-tracker.git
   git push -u origin main
   ```

   Or if you use GitHub CLI, instead of creating the empty repository in the browser, run this **one-time** command after `git commit`:

   ```bash
   gh repo create medical-ophthalmic-ai-tracker --public --source=. --remote=origin --push
   ```

3. In the repository: `Settings` → `Pages` → `Build and deployment` → `Source` → **GitHub Actions**. (This requires repository admin rights.)
4. Go to `Actions` → `Medical & Ophthalmic AI Literature` → `Run workflow` to run immediately. The page should become available at `https://<YOUR_USERNAME>.github.io/medical-ophthalmic-ai-tracker/` after a successful deployment.
5. Optional: `Settings` → `Secrets and variables` → `Actions` → **Variables** → set `CONTACT_EMAIL` to a real research mailbox. This is recommended for NCBI/Crossref API etiquette. No fake email is sent if it is not configured.

**Do not** paste a personal GitHub token into the repository. Actions uses the repo's short-lived built-in `GITHUB_TOKEN` to commit the public catalog and deploy Pages. The repository's **Settings → Actions → General → Workflow permissions** must permit writing contents; for some organization accounts an admin must allow it.

## Daily ChatGPT summary

The ChatGPT scheduled task is deliberately **read-only**. It reads:

- `https://<YOUR_USERNAME>.github.io/medical-ophthalmic-ai-tracker/data/latest.json`
- `https://<YOUR_USERNAME>.github.io/medical-ophthalmic-ai-tracker/data/history.json`

It reports the actual run time, coverage/failures, major Medical AI & Ophthalmic AI papers with primary links, peer-review state, verifiable numeric results, limitations and 3–5 trends. **If the pipeline is stale/failed, it must say so and must not invent a fresh report.**

## Known limitations, intentionally visible

- Crossref's date-indexed journal works are **not** a full crawl of each journal's official online-first pages. Pay attention to the `crossref-journal` audit source; coverage may still be incomplete.
- arXiv's API does **not** support a native `lastUpdatedDate` interval search. The tracker sorts by latest update and checks the returned update dates, stopping once older than the window.
- APIs may reject or throttle requests. Retry is bounded; failures and source caps remain **partial**, not magically marked complete.
- This is a **rolling UTC date scan**, not a precisely timed last-24-hours window. A source's original publication date may differ from index appearance date; the daily ChatGPT note must distinguish them.
- Data may be incomplete due to database/index lag, incomplete abstracts, different DOI across preprint/journal, and approximate title deduplication. No automated tool guarantees 100% recall.
- Automated score is an **unreviewed triage priority**, not an A/B quality rating and not clinical advice.
- Any exact metrics quoted by ChatGPT should be checked against the source abstract/full text; the code deliberately preserves only short abstract excerpts in the public repo.
- At present the pipeline does **not** write directly to private Notion. Add Notion sync only after configuring private credentials as GitHub Secrets and testing idempotent writes.

## Local tests

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m tracker.pipeline --days 7
# preview _site/index.html
```

## Audit data schema

`data/catalog.json`: deduplicated public paper metadata; `data/latest.json`: latest source/query audits + newly discovered papers; `data/history.json`: most recent 120 runs. `latest.json` includes `complete=false` if *any* attempted query fails or is capped. Successful GitHub workflow execution alone does **not** imply literature coverage completeness.
