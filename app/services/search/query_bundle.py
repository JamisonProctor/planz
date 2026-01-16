from __future__ import annotations


def build_query_bundle(location: str, window_days: int) -> list[dict[str, str]]:
    de_city = "München"
    en_city = "Munich"
    queries = [
        {
            "language": "de",
            "intent": "kids_free_weekend",
            "query": f"kinder veranstaltungen kostenlos dieses wochenende {de_city}",
        },
        {
            "language": "de",
            "intent": "kids_calendar",
            "query": f"kinder kalender termine {de_city}",
        },
        {
            "language": "de",
            "intent": "museum_program",
            "query": f"museum kinder programm {de_city}",
        },
        {
            "language": "de",
            "intent": "library_program",
            "query": f"bibliothek kinder programm {de_city}",
        },
        {
            "language": "de",
            "intent": "family_events",
            "query": f"familien veranstaltungen {de_city}",
        },
        {
            "language": "en",
            "intent": "kids_free_weekend",
            "query": f"free kids events this weekend {en_city}",
        },
        {
            "language": "en",
            "intent": "kids_calendar",
            "query": f"kids events calendar {en_city}",
        },
        {
            "language": "en",
            "intent": "museum_program",
            "query": f"museum kids program {en_city}",
        },
        {
            "language": "en",
            "intent": "library_program",
            "query": f"library kids program {en_city}",
        },
        {
            "language": "de",
            "intent": "upcoming_program",
            "query": f"programm termine {de_city} {window_days} tage",
        },
    ]

    return queries
