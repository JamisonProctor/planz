# PLANZ — LLM-Powered Local Events to Calendar (Prototype)

PLANZ is a product prototype that discovers local events from trusted sources and syncs them into a user’s calendar. It uses an LLM-powered extraction pipeline to turn messy web pages into structured event data, then publishes the results to Google Calendar.

The intent is to validate an end-to-end user outcome quickly: **useful, future events showing up in a calendar with correct time and location**, without manual copy/paste.

---

## Problem

Local event discovery is fragmented:
- Events are spread across many websites with inconsistent structure and languages.
- Details vary (time, address, recurrence, ticketing).
- Planning happens in calendars, but discovery happens on websites.
- Users re-check the same listings because nothing is captured in a durable place.

**Hypothesis:** If relevant events automatically appear in a calendar, users can plan faster and with less effort.

---

## What It Does

- Ingests event listing pages (starting with high-quality Munich sources)
- Fetches and parses content
- Uses an LLM to extract structured event candidates
- Filters out obvious non-actionable results (e.g., past-only)
- Persists events and syncs them to Google Calendar

The calendar is the primary “UI” for dogfooding and validation.

---

## Current Focus

This repository is intentionally scoped as a prototype. Priorities are:

- **Reliable runs:** repeatable execution and clear failure modes  
- **Operational visibility:** minimal progress output (heartbeat + summary)  
- **Idempotent syncing:** repeated runs should not create duplicates  
- **Quality basics:** correct times, correct address in the calendar location field, canonical event URL in the calendar URL field

---

## Non-Goals (for now)

- No frontend app
- No personalization or ranking
- No broad long-tail scraping coverage
- No deep support for dynamic JS-only calendars unless proven necessary

---

## How to Run

Typical workflow:
1. Configure required environment variables (API keys and calendar selection)
2. Run the weekly pipeline script to ingest, extract, and sync
3. Verify events in Google Calendar

Tests are included for core behaviors, and ongoing development is intended to stay test-driven.

---

## Roadmap (High Level)

- **Reliability & observability:** clean progress logs, better error surfacing, run-time tracking, safe debug modes  
- **Idempotency & dedupe:** stable event identity and calendar upserts without duplicates  
- **Enrichment:** optional detail-page fetches for better address/description when it materially improves quality  
- **Source expansion:** additional Munich sources, German/English coverage, source-quality tracking

---

## Status Notes

This is an active prototype. Expect rapid iteration around extraction quality, duplicate prevention, and operational visibility as sources and volume increase.
