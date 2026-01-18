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

1. **Search + Verify**  
   - OpenAI Responses API web_search provider (via abstraction)
   - `PLANZ_SEARCH_DEBUG=true` logs observed `web_search_call.action` shape for troubleshooting
   - SDK responses may return typed action objects (e.g., `action.sources`), which are parsed before dict/model_dump fallbacks
   - web_search sources can be typed objects; normalization handles dict/object/model_dump shapes
   - DE+EN multi-query bundle (`kostenlos`/`free`, `München`/`Munich`)
   - SearchRun/SearchQuery/SearchResult stored for provenance
   - SourceUrl provenance recorded via SearchResult linkage
   - Verification gate: blocked domains, fetchable, min length, date tokens, no archive signals
   - Prefer URLs with terms like `termine`/`kalender`/`veranstaltungen`/`programm`
   - Domain blocklist for v1: Meetup/Eventbrite are blocked
   - AcquisitionIssue registry tracks uncapturable URLs and reasons

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
   - Multi-day events with weekends are sliced into Saturday/Sunday only (v1)
   - Weekday inclusion may become a user preference later

4. **Calendar Sync**  
   - Sync only *future, unsynced* events to Google Calendar
    - Persist `CalendarSync` records for idempotency
    - Never spam calendars
   - No grace window in production; recent-past syncing is disabled

5. **Orchestration**
   - `run_weekly.py` executes: search → verify → fetch → extract → sync
   - Designed for scheduled execution (cron / GitHub Actions later)
   - Search can be disabled with `PLANZ_ENABLE_SEARCH=false`

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
