from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


COMMON_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Paris",
    "Africa/Lagos",
    "Africa/Nairobi",
    "Asia/Dubai",
    "Asia/Tokyo",
    "Australia/Sydney",
    "UTC",
]


@dataclass
class TemporalContext:
    timezone: str
    current_datetime: str
    current_date: str
    current_time: str
    day_of_week: str
    utc_datetime: str
    utc_offset: str

    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    day_of_year: int
    week_of_year: int
    quarter: int
    is_weekend: bool

    temporal_initialized: bool = True
    timezone_valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_timezone(timezone_name: str) -> str:
    return (timezone_name or "").strip()


def is_valid_timezone(timezone_name: str) -> bool:
    requested_timezone = normalize_timezone(timezone_name)

    if not requested_timezone:
        return False

    try:
        ZoneInfo(requested_timezone)
        return True
    except ZoneInfoNotFoundError:
        return False


def suggest_timezones(query: str, limit: int = 10) -> List[str]:
    normalized_query = normalize_timezone(query).lower().replace(" ", "_")

    if not normalized_query:
        return COMMON_TIMEZONES[:limit]

    try:
        candidates = sorted(available_timezones())
    except Exception:
        candidates = COMMON_TIMEZONES

    matches = [
        tz for tz in candidates
        if normalized_query in tz.lower()
    ]

    if matches:
        return matches[:limit]

    return [
        tz for tz in COMMON_TIMEZONES
        if normalized_query in tz.lower()
    ][:limit]


def calculate_quarter(month: int) -> int:
    return ((month - 1) // 3) + 1


def build_temporal_context(timezone_name: str) -> TemporalContext:
    requested_timezone = normalize_timezone(timezone_name)

    if not requested_timezone:
        raise ValueError("Timezone is required for Temporal Awareness.")

    try:
        tz = ZoneInfo(requested_timezone)
    except ZoneInfoNotFoundError as error:
        suggestions = suggest_timezones(requested_timezone)
        suggestion_text = ", ".join(suggestions) if suggestions else "No close matches found."

        raise ValueError(
            f"Invalid timezone: {requested_timezone}. "
            f"Use a valid IANA timezone such as America/New_York, Europe/London, "
            f"Africa/Nairobi, Asia/Tokyo, or Australia/Sydney. "
            f"Suggestions: {suggestion_text}"
        ) from error

    now_local = datetime.now(tz)
    now_utc = datetime.now(timezone.utc)

    return TemporalContext(
        timezone=requested_timezone,
        current_datetime=now_local.isoformat(),
        current_date=now_local.date().isoformat(),
        current_time=now_local.time().isoformat(timespec="seconds"),
        day_of_week=now_local.strftime("%A"),
        utc_datetime=now_utc.isoformat(),
        utc_offset=now_local.strftime("%z"),

        year=now_local.year,
        month=now_local.month,
        day=now_local.day,
        hour=now_local.hour,
        minute=now_local.minute,
        second=now_local.second,
        day_of_year=int(now_local.strftime("%j")),
        week_of_year=int(now_local.strftime("%U")),
        quarter=calculate_quarter(now_local.month),
        is_weekend=now_local.weekday() >= 5,

        metadata={
            "source": "system_clock",
            "timezone_standard": "IANA",
            "fallback_used": False,
        },
    )