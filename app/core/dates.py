from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Day-wise boundaries are in India time (the user's timezone), not the server's.
IST = ZoneInfo("Asia/Kolkata")


def today() -> date:
    return datetime.now(IST).date()


def resolve_period(period: str, reference: date | None = None) -> tuple[date, date]:
    reference = reference or today()
    if period == "today":
        return reference, reference
    if period == "week":
        return reference - timedelta(days=6), reference  # last 7 days, inclusive
    raise ValueError(f"unknown period: {period!r}")
