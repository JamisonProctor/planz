# Repository Guidelines (AGENTS.md)

This document defines **non-negotiable rules** for humans and coding agents working in this repository.
If behavior, architecture, or workflow changes, this file MUST be updated accordingly.

---

## Project Overview

PLANZ is a **calendar delivery pipeline** for real-world events.

Core principle:
> We do not build an event directory.  
> We deliver relevant events directly into calendars, reliably and idempotently.

The system is designed to evolve into a commercial service. Decisions should favor:
- correctness
- traceability
- cost control
- extensibility

---

## Architecture Overview

The system is a **multi-stage pipeline**:

1. **Source Scope**
   - Current source focus is a single high-value listing: `https://www.muenchen.de/veranstaltungen/event/kinder`
   - LLM-based internet search is removed for now
   - New work should improve extraction quality, pagination, and sync reliability for this source before adding broader discovery again
   - AcquisitionIssue registry tracks uncapturable URLs and reasons
   - Playwright fallback: controlled by `PLANZ_USE_PLAYWRIGHT` and `PLANZ_PLAYWRIGHT_ALLOWLIST`
   - Diagnostic script: `python -m app.scripts.diagnose_source_url <url>`
   - Smoke extraction: `python -m app.scripts.extract_single_url <url> [--persist]`
   - muenchen.de listings currently work with plain fetch; Playwright stays optional for JS-only sites
   - `extract_muenchen_kinder` must parse listing entries, fetch each event detail page, and pass both listing-page context and detail-page content into extraction so dates/locations visible only on one side are still captured
   - For muenchen.de kids events, the event detail URL (not the listing URL) is the canonical source URL used for DB rows and calendar source links
   - If a muenchen.de kids listing card exposes a ticket icon/link, that ticket URL overrides the calendar/source link for the event while the detail URL remains the extraction target
   - Ticket-link events must be visually marked with a leading ticket emoji in the event title so calendar users can identify them immediately
   - Pagination helper for muenchen.de kids listings; cap via `PLANZ_MAX_LISTING_PAGES`
   - Pagination stops when next link repeats or content hash unchanged; logged URLs: "Listing pages to process: ..."
   - Run `python -m app.scripts.migrate_db` before first use to backfill and enforce unique external keys
   - External idempotency: `external_key` (detail_url + start_time hash) enforces DB uniqueness; calendar tagging uses `extendedProperties.private.planz_key`
   - Calendar events keep clean titles; tagging via `extendedProperties.private.planz=true` (wipe uses this tag)
   - Calendar location is plain address; source points to detail page; description includes single “More info” link
   - Calendar upserts include `extendedProperties.private.planz_key` and retry on Google `rateLimitExceeded` with backoff; wipe uses the tag to delete only PLANZ events
   - Calendar upserts must include `extendedProperties.private.planz=true`; legacy wipe may also match old muenchen.de events via `extendedProperties.private.planz_source` or Google `source.url` when `--force-legacy` is used
   - Calendar search/list calls enforce `timeMax > timeMin`; malformed windows are logged once and skipped (no crashes)
   - Event idempotency: deterministic `external_key`/event_key derived from detail_url+start_time; store updates existing rows (no duplicates); content changes clear sync markers to trigger re-sync
   - CLI observability: listing extraction logs one status line per page plus a DONE summary; heartbeat logs every ~30s on long steps unless LOG_LEVEL=DEBUG; `--verbose` or `LOG_LEVEL=DEBUG` enables detailed logs
   - `extract_muenchen_kinder` supports `--no-sync` to skip calendar sync for data-only runs

2. **Fetch**
 - Fetch raw page content for allowed SourceUrls
   - Persist fetch metadata, hashes, and excerpts
   - Never refetch unnecessarily

3. **Extraction**  
   - LLM-based extraction of IRL events from fetched content
   - Idempotent via content hash comparison
   - Produces structured `Event` rows
   - Extraction stats persisted per `SourceUrl` (status/count/error)
   - Future-only: events ending before today are discarded
   - Multi-day events are expanded into one `Event` row per calendar day in the span
   - For multi-day events, only Saturdays, Sundays, and Bavaria public holidays are marked as calendar candidates
   - Non-candidate daily rows are still stored for traceability but must not sync to Google Calendar

4. **Calendar Sync**  
  - Sync only *future, unsynced* events to Google Calendar
    - Persist `CalendarSync` records for idempotency
    - Never spam calendars
  - No grace window in production; recent-past syncing is disabled
  - Rows with `is_calendar_candidate=false` are intentionally excluded from sync

5. **Orchestration**
   - `run_weekly.py` executes: fetch → extract → sync
   - Designed for scheduled execution (cron / GitHub Actions later)

---

## Project Structure

Current canonical structure:

app/
core/            # Pure utilities (URLs, parsing, etc.)
db/
base.py
session.py
models/
services/
discovery/
fetch/
extract/
calendar/
scripts/
llm_discover_sources.py
fetch_sources.py
extract_events.py
run_weekly.py
tests/

Rules:
- Services contain **business logic**
- Scripts are **thin orchestration layers**
- No LLM, HTTP, or Google API calls inside tests

---

## Testing (MANDATORY)

**Test-Driven Development is required for all changes.**

Rules:
- Write tests FIRST
- Tests must fail before implementation
- All tests must pass before committing
- Use pytest exclusively
- Tests must be deterministic and offline

Strict prohibitions:
- ❌ No real OpenAI calls in tests
- ❌ No real HTTP calls in tests
- ❌ No real Google API calls in tests

Use mocks, fakes, or stubs.

---

## Timezones & Datetimes

- Application logic uses **timezone-aware datetimes**
- SQLite may coerce to naive — tests must account for this
- Commit/flush boundaries matter; avoid hidden coercion

Be explicit and consistent.

---

## Commit Discipline

- Use **Conventional Commits**
  - `feat:`
  - `fix:`
  - `test:`
  - `refactor:`
  - `chore:`
- One logical change per commit
- Commits must correspond to **user-visible behavior or guarantees**

Agents must **propose** commit messages but never run git commands.

---

## Environment & Secrets

- Secrets must NEVER be committed
- Required environment variables:
  - `OPENAI_API_KEY` (only required for real extraction or discovery runs)
  - `GOOGLE_CALENDAR_ID` (defaults to `primary` if omitted)
- Google Calendar credentials:
  - `credentials.json` and `token.json` are local-only
- `.env` is supported via `python-dotenv`; scripts load environment automatically

---

## Pipeline Observability

Weekly runs must print a clear summary, even on no-op runs. At minimum:
- Source URL inventory (total / allowed / disabled)
- Fetch counts and error hints
- Extraction counts with skip reasons (no content, unchanged hash, disabled domain)
- Sync counts with skip reasons (already synced, past)

If a run does no work, the reason must be explicit (e.g., no sources, missing key, unchanged hashes).

---

## Acquisition Issue Registry

Rejected or uncapturable URLs are tracked in `AcquisitionIssue` with a reason and timestamps.
This is used to understand failure modes (blocked, JS-only, archive, etc.) without losing provenance.
Review backlog via SQLite queries or admin endpoints when added.

---

## SQLite Migrations (REQUIRED)

SQLite schema changes are not automatic. Any new columns or tables must include a migration step.

- Use `app/db/migrations/sqlite.ensure_sqlite_schema(engine)` for local upgrades.
- Scripts must call `ensure_sqlite_schema` at startup.
- Deleting the DB is NOT an acceptable long-term strategy.

---

## Dev-Only Extraction Override

`PLANZ_FORCE_EXTRACT` is a development-only escape hatch:
- When set to `true`/`1`/`yes`, extraction ignores unchanged content hashes.
- Must never be enabled in production.
- Intended for debugging and early development only.

---

## Manual Smoke Test

1) Ensure `https://www.muenchen.de/veranstaltungen/event/kinder` exists as an allowed `SourceUrl` in the local DB
2) `python -m app.scripts.run_weekly`
3) `python -m app.scripts.extract_single_url https://www.muenchen.de/veranstaltungen/event/kinder`
4) Check calendar for `[PLZ]` events
5) `python -m app.scripts.extract_muenchen_kinder --persist`
6) `python -m app.scripts.calendar_wipe_planz --dry-run --days 120` (only deletes `[PLZ]`/planz-marked)

---

## Last Run Outcome Checklist

- Fetch produced ok content (fetched_ok > 0)
- Extraction created events (events_created_total > 0)
- Sync created calendar events (events_synced > 0)
- Calendar wipe dry-run reviewed before destructive run

---

## Series Cache

- EventSeries caches detail pages by series_key (detail_url preferred, else domain+title+location)
- Detail pages fetched once per series; repeated dates reuse cached description
- Updated lazily during extraction; prevents redundant detail fetch costs

---

## Agent Responsibilities (CRITICAL)

Any coding agent operating in this repo MUST:

1. Follow TDD strictly
2. Avoid unnecessary refactors
3. Preserve existing behavior unless tests reveal a bug
4. **Update this AGENTS.md file when:**
   - workflow rules change
   - architectural stages change
   - testing rules change
   - new non-obvious constraints are introduced

If unsure, ASK before changing behavior.

Failure to update AGENTS.md when required is considered a defect.

---

IMPORTANT (PROCESS RULES):

- We use strict Test-Driven Development (tests first, then implementation).
- No real network, OpenAI, or Google API calls in tests.
- You must NOT run git commands.

AGENTS.md RULE:
If your changes introduce or modify:
- workflow rules
- architectural stages
- testing expectations
- agent responsibilities
- non-obvious constraints

Then you MUST update AGENTS.md as part of this change.

At the very end of your response, include:

COMMIT MESSAGE:
<one concise Conventional Commit message>

Do NOT include anything after the commit message.
