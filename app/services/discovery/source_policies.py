BLOCKED_DOMAINS = {
    "www.meetup.com",
    "meetup.com",
    "www.eventbrite.com",
    "eventbrite.com",
}


def is_domain_allowed(domain: str) -> bool:
    return domain not in BLOCKED_DOMAINS
