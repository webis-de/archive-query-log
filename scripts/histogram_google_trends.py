import argparse
import csv
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Dict, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import to_rgb
from matplotlib.transforms import blended_transform_factory
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

TITLE_FONT_SIZE = 26
AXIS_LABEL_FONT_SIZE = 10
VERTICAL_LINE_LABEL_FONT_SIZE = 10
TICK_FONT_SIZE = 10
SPIKE_MULTIPLIER = 3.0
RECENT_YEARS = 1
TRENDS_LIGHTEN_FACTOR = 0.85
TRENDS_LINE_ALPHA = 0.7
TRENDS_LINESTYLE = "-"
TRENDS_MARKER_SIZE = 4.5
TRENDS_SPIKE_MARKER_SIZE = 70
TRENDS_Y_SCALE_MODE = "symlog"  # options: "linear", "symlog"
TRENDS_SYMLOG_LINTHRESH = 5.0

FIG_WIDTH_PT = 347.12354
PT_TO_INCH = 1 / 72
FIG_WIDTH_IN = FIG_WIDTH_PT * PT_TO_INCH
FIG_HEIGHT_WITH_TRENDS = FIG_WIDTH_IN * 0.72
FIG_HEIGHT_SERP_ONLY = FIG_WIDTH_IN * 0.45
SUBPLOT_VERTICAL_GAP = 0.5
SUBPLOT_LEFT_MARGIN = 0.12
LABEL_GAP_FRACTIONS = (0.3, 0.65)
LABEL_SERP_ONLY_POSITIONS = (0.1, 0.22)
Y_LABEL_PAD = 32
Y_LABEL_X_COORD = -0.1
LABEL_OFFSET_DAYS = {
    "valentines_day": -20,
}
OVERLAPPING_TRENDS_GROUPS = [
    {
        "anchor_event": "christmas",
        "paths": [
            "only2024_overlapping_sets/christmas-easter-halloween-4th-july-valentines-day-multiTimeline.csv",
            "only2024_overlapping_sets/christmas-labor-day-mothers-day-multiTimeline.csv",
        ],
    },
]

EVENT_PALETTE = {
    "valentines_day": {
        "serp": "#FF6F52",  # webisredA3
        "trends_base": "#FF6F52",  # webisredTL1
    },
    "easter": {
        "serp": "#62BA61",  # webisgreenA3
        "trends_base": "#62BA61",  # webisgreenTL1
    },
    "mothers_day": {
        "serp": "#E8A01D",  # webisyellowA3
        "trends_base": "#E8A01D",  # webisyellowTL1
    },
    "independence_day_us": {
        "serp": "#FFAB9E",  # webisredA2
        "trends_base": "#FFAB9E",  # webisredTL2
    },
    "labor_day": {
        "serp": "#12753E",  # webisgreenA1
        "trends_base": "#12753E",  # webisgreenTL2
    },
    "halloween": {
        "serp": "#D6ACFA",  # webispurpleA2
        "trends_base": "#D6ACFA",  # webispurpleLD
    },
    "thanksgiving": {
        "serp": "#BB86F3",  # webispurpleA3
        "trends_base": "#BB86F3",  # webispurpleTL1
    },
    "christmas": {
        "serp": "#68B4C2",  # webisblueA3
        "trends_base": "#68B4C2",  # webisblueTL1
    },
}

HOLIDAY_EVENTS = [
    {
        "key": "valentines_day",
        "label": "Valentine's Day",
        "phrase": "valentine's day",
        "event_date": "02-14",
    },
    {
        "key": "easter",
        "label": "Easter",
        "phrase": "easter",
        "event_date": "04-01",
    },
    {
        "key": "mothers_day",
        "label": "Mother's Day",
        "phrase": "mother's day",
        "dynamic_date": "second_sunday_may",
    },
    {
        "key": "independence_day_us",
        "label": "July 4th",
        "phrase": "4th of July",
        "event_date": "07-04",
    },
    {
        "key": "labor_day",
        "label": "Labor Day",
        "phrase": "labor day",
        "dynamic_date": "first_monday_september",
    },
    {
        "key": "halloween",
        "label": "Halloween",
        "phrase": "halloween",
        "event_date": "10-31",
    },
    {
        "key": "christmas",
        "label": "Christmas",
        "phrase": "christmas",
        "event_date": "12-24",
    },
]

DEFAULT_TRENDS_SOURCES = {
    "valentines_day": "holidays-seperate-google-trends/valentines-day-multiTimeline.csv",
    "easter": "holidays-seperate-google-trends/easter-multiTimeline.csv",
    "mothers_day": "holidays-seperate-google-trends/mothers-day-multiTimeline.csv",
    "independence_day_us": "holidays-seperate-google-trends/independence-day-multiTimeline.csv",
    "labor_day": "holidays-seperate-google-trends/labor-day-multiTimeline.csv",
    "halloween": "holidays-seperate-google-trends/halloween-multiTimeline.csv",
    "thanksgiving": "holidays-seperate-google-trends/thanksgiving-multiTimeline.csv",
    "christmas": "holidays-seperate-google-trends/christmasmultiTimeline.csv",
}

# legacy hook kept for future manual tweaks if needed
EVENT_LABEL_OFFSETS: Dict[str, Dict[str, float]] = {}

ES_HOST = os.getenv("ELASTICSEARCH_HOST")
ES_PORT = os.getenv("ELASTICSEARCH_PORT")
ES_USERNAME = os.getenv("ELASTICSEARCH_USERNAME")
ES_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD")

es = Elasticsearch(
    hosts=f"https://{ES_HOST}:{ES_PORT}",
    http_auth=(ES_USERNAME, ES_PASSWORD),
    max_retries=5,
    retry_on_status=(502, 503, 504),
    retry_on_timeout=True,
)


def build_match_clause(phrase: str) -> dict:
    return {"match_phrase": {"url_query": phrase}}


def lighten_color(color: str, amount: float = TRENDS_LIGHTEN_FACTOR) -> tuple[float, float, float]:
    """Return a lighter variant of *color* by mixing it with white."""

    r, g, b = to_rgb(color)
    return (
        r + (1 - r) * (1 - amount),
        g + (1 - g) * (1 - amount),
        b + (1 - b) * (1 - amount),
    )


def calculate_easter(year: int) -> datetime:
    """Compute the Gregorian Easter date for *year* (Meeus/Jones/Butcher algorithm)."""

    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day)


def _nth_weekday_of_month(year: int, month: int, weekday: int, occurrence: int) -> datetime:
    """Return the date of the `occurrence`-th `weekday` (0=Mon) in `month` of `year`."""

    first_day = datetime(year, month, 1)
    offset = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + timedelta(days=offset)
    return first_occurrence + timedelta(weeks=max(occurrence - 1, 0))


def resolve_event_date(event: dict, year: int) -> Optional[datetime]:
    if event.get("key") == "easter":
        return calculate_easter(year)

    dynamic_key = event.get("dynamic_date")
    if dynamic_key == "second_sunday_may":
        return _nth_weekday_of_month(year, 5, 6, 2)
    if dynamic_key == "first_monday_september":
        return _nth_weekday_of_month(year, 9, 0, 1)
    if dynamic_key == "fourth_thursday_november":
        return _nth_weekday_of_month(year, 11, 3, 4)

    date_str = event.get("event_date")
    if not date_str:
        return None

    month, day = map(int, date_str.split("-"))
    try:
        return datetime(year=year, month=month, day=day)
    except ValueError:
        return None


def _normalize_label(label: str) -> str:
    lowered = label.lower()
    lowered = lowered.split(":", 1)[0]
    lowered = lowered.split("(", 1)[0]
    lowered = lowered.replace("'", "")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return lowered.strip()


def parse_google_trends_csv(path: str) -> Dict[str, Dict[datetime, float]]:
    """Load a Google Trends CSV into `{normalized_header -> {week_date -> max_value}}`."""

    series_by_label: Dict[str, Dict[datetime, float]] = {}

    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.reader(handle)

        date_headers = {"month", "monat", "week", "woche", "date", "datum"}
        date_idx: Optional[int] = None
        value_columns: Dict[int, str] = {}

        for raw_row in reader:
            row = [cell.strip() if cell is not None else "" for cell in raw_row]
            if not row or all(cell == "" for cell in row):
                continue

            header_detected = False
            if date_idx is None or any(cell.lower() in date_headers for cell in row):
                for idx, cell in enumerate(row):
                    if cell.lower() in date_headers:
                        date_idx = idx
                        header_detected = True
                        break
                if header_detected:
                    value_columns.clear()
                    for idx, cell in enumerate(row):
                        if idx == date_idx:
                            continue
                        normalized = _normalize_label(cell)
                        if normalized:
                            value_columns[idx] = normalized
                            series_by_label.setdefault(normalized, {})
                    continue

            if date_idx is None or not value_columns:
                continue

            if date_idx >= len(row):
                continue

            month_cell = row[date_idx]
            if not month_cell:
                continue

            parsed_month: Optional[datetime] = None
            for fmt in ("%Y-%m", "%Y-%m-%d", "%d.%m.%Y"):
                try:
                    parsed_month = datetime.strptime(month_cell, fmt)
                    break
                except ValueError:
                    continue

            if parsed_month is None:
                    continue

            for col_idx, normalized in value_columns.items():
                if col_idx >= len(row):
                    continue
                value_cell = row[col_idx]
                if not value_cell:
                    continue

                cleaned_value = value_cell.replace(",", "").strip()
                if cleaned_value == "<1":
                    numeric_value = 0.0
                else:
                    try:
                        numeric_value = float(cleaned_value)
                    except ValueError:
                        continue

                week_bucket = series_by_label.setdefault(normalized, {})
                existing = week_bucket.get(parsed_month)
                if existing is None or numeric_value > existing:
                    week_bucket[parsed_month] = numeric_value

    return series_by_label


def _merge_series_max(
    primary: Optional[Dict[datetime, float]],
    secondary: Dict[datetime, float],
) -> Dict[datetime, float]:
    """Return a copy of the union of both series preferring larger values on overlaps."""

    result: Dict[datetime, float] = dict(primary) if primary else {}
    for date_point, value in secondary.items():
        existing = result.get(date_point)
        if existing is None or value > existing:
            result[date_point] = value
    return result


def calibrate_trends_with_anchor(
    trends_by_event: Dict[str, Dict[datetime, float]],
    normalized_event_lookup: Dict[str, str],
    script_dir: Path,
) -> None:
    """Rescale single-key Google Trends series using overlapping anchor groups."""

    if not OVERLAPPING_TRENDS_GROUPS:
        return

    original_series = {event_key: dict(series) for event_key, series in trends_by_event.items()}
    ratio_samples: Dict[str, list[float]] = {}
    overlapping_series: Dict[str, Dict[datetime, float]] = {}

    for group in OVERLAPPING_TRENDS_GROUPS:
        anchor_event = group.get("anchor_event")
        if not anchor_event:
            continue
        normalized_anchor = _normalize_label(anchor_event)
        for relative_path in group.get("paths", []):
            csv_path = script_dir / relative_path
            if not csv_path.exists():
                continue
            parsed = parse_google_trends_csv(str(csv_path))
            if normalized_anchor not in parsed:
                continue
            for label, group_series in parsed.items():
                if label == normalized_anchor:
                    continue
                event_key = normalized_event_lookup.get(label)
                if not event_key:
                    continue
                overlapping_series[event_key] = _merge_series_max(
                    overlapping_series.get(event_key),
                    group_series,
                )
                base_series = original_series.get(event_key)
                if not base_series:
                    continue
                ratios = []
                for date_point, group_value in group_series.items():
                    base_value = base_series.get(date_point)
                    if base_value is None or base_value <= 0:
                        continue
                    ratios.append(group_value / base_value)
                if ratios:
                    ratio_samples.setdefault(event_key, []).extend(ratios)

    for event_key, ratios in ratio_samples.items():
        positive = [value for value in ratios if value > 0]
        if not positive:
            continue
        scale_factor = median(positive)
        if scale_factor <= 0:
            continue
        base_series = original_series.get(event_key)
        if not base_series:
            continue
        scaled_series = {
            date_point: min(value * scale_factor, 100.0) for date_point, value in base_series.items()
        }
        if event_key in overlapping_series:
            scaled_series.update(overlapping_series[event_key])
        trends_by_event[event_key] = scaled_series

    for event_key, series in overlapping_series.items():
        if event_key in ratio_samples:
            continue
        if event_key in trends_by_event:
            trends_by_event[event_key] = _merge_series_max(trends_by_event[event_key], series)
        else:
            trends_by_event[event_key] = dict(series)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot holiday SERP histograms per event and compare with Google Trends",
    )
    parser.add_argument(
        "--trends-csv",
        dest="trends_csv",
        action="append",
        help=(
            "Optional mapping of event key to Google Trends CSV. "
            "Format: event_key=path/to.csv (flag may be repeated)."
        ),
    )
    parser.add_argument(
        "--output",
        dest="output",
        default="holiday-google-trends.pdf",
        help="Path to the output figure (default: holiday-google-trends.pdf)",
    )

    args = parser.parse_args()

    trends_by_event: Dict[str, Dict[datetime, float]] = {}
    normalized_event_lookup: Dict[str, str] = {}
    for event in HOLIDAY_EVENTS:
        for alias in {event["key"], event["label"], event["phrase"]}:
            normalized = _normalize_label(alias)
            if normalized:
                normalized_event_lookup[normalized] = event["key"]

    script_dir = Path(__file__).resolve().parent

    if args.trends_csv:
        for mapping in args.trends_csv:
            if "=" in mapping:
                event_key, csv_path = mapping.split("=", 1)
                event_key = event_key.strip()
                csv_path = csv_path.strip()
                if not event_key or not csv_path:
                    raise ValueError("Both event key and CSV path must be provided in --trends-csv")

                parsed = parse_google_trends_csv(csv_path)
                normalized_target = _normalize_label(event_key)
                matched_values = None
                if normalized_target in parsed:
                    matched_values = parsed[normalized_target]
                elif len(parsed) == 1:
                    matched_values = next(iter(parsed.values()))

                if matched_values is None:
                    available = ", ".join(parsed.keys()) or "<none>"
                    raise ValueError(
                        f"Could not find trends column matching '{event_key}' in {csv_path}. "
                        f"Available series: {available}"
                    )

                canonical_event = normalized_event_lookup.get(normalized_target, event_key)
                bucket = trends_by_event.setdefault(canonical_event, {})
                for date_point, value in matched_values.items():
                    if math.isnan(value):
                        continue
                    existing = bucket.get(date_point)
                    if existing is None or value > existing:
                        bucket[date_point] = value
            else:
                csv_path = mapping.strip()
                parsed = parse_google_trends_csv(csv_path)
                for normalized_label, values in parsed.items():
                    event_key = normalized_event_lookup.get(normalized_label)
                    if not event_key:
                        continue
                    bucket = trends_by_event.setdefault(event_key, {})
                    for date_point, value in values.items():
                        if math.isnan(value):
                            continue
                        existing = bucket.get(date_point)
                        if existing is None or value > existing:
                            bucket[date_point] = value
    else:
        for event_key, relative_path in DEFAULT_TRENDS_SOURCES.items():
            csv_path = script_dir / relative_path
            if not csv_path.exists():
                continue

            parsed = parse_google_trends_csv(str(csv_path))
            normalized_target = _normalize_label(event_key)
            if normalized_target in parsed:
                matched_values = parsed[normalized_target]
            elif len(parsed) == 1:
                matched_values = next(iter(parsed.values()))
            else:
                available = ", ".join(parsed.keys()) or "<none>"
                raise ValueError(
                    f"Could not find trends column matching '{event_key}' in {csv_path}. "
                    f"Available series: {available}"
                )
            bucket = trends_by_event.setdefault(event_key, {})
            for date_point, value in matched_values.items():
                if math.isnan(value):
                    continue
                existing = bucket.get(date_point)
                if existing is None or value > existing:
                    bucket[date_point] = value

    calibrate_trends_with_anchor(trends_by_event, normalized_event_lookup, script_dir)

    query = {
    "query": {
        "bool": {
            "must": [
                {"range": {
                    "capture.timestamp": {
                        "gte": "now-1y/y",   # start of last year
                        "lt":  "now/y"       # start of this year
                    }
                }}
            ],
            "should": [build_match_clause(event["phrase"]) for event in HOLIDAY_EVENTS],
            "minimum_should_match": 1,
        }
    },
    "size": 0,
    "aggs": {
        "per_event": {
            "filters": {
                "filters": {
                    event["key"]: build_match_clause(event["phrase"])
                    for event in HOLIDAY_EVENTS
                }
            },
            "aggs": {
                "queries_over_time": {
                    "date_histogram": {
                        "field": "capture.timestamp",
                        "calendar_interval": "week",
                        "min_doc_count": 0,
                        "extended_bounds": {
                            "min": "now-1y/y",
                            "max": "now/y"
                        }
                    }
                }
            },
        }
    },
}


    search_results = es.search(index="aql_serps", body=query)

    aggregations = search_results.get("aggregations", {})
    per_event = aggregations.get("per_event", {}).get("buckets", {})

    series = []
    all_dates = []
    for event in HOLIDAY_EVENTS:
        event_bucket = per_event.get(event["key"], {})
        timeline = event_bucket.get("queries_over_time", {}).get("buckets", [])
        pairs = sorted(
            (
                datetime.fromtimestamp(point["key"] / 1000),
                point.get("doc_count", 0),
            )
            for point in timeline
        )
        if not pairs:
            continue

        series.append({"event": event, "pairs": pairs})
        all_dates.extend(date for date, _ in pairs)

    if not series or not all_dates:
        raise ValueError("No per-event histogram buckets found in the Elasticsearch response")

    latest_date = max(all_dates)
    cutoff = latest_date - timedelta(days=365 * RECENT_YEARS)

    filtered_series = []
    for entry in series:
        filtered_pairs = [pair for pair in entry["pairs"] if pair[0] >= cutoff]
        if not filtered_pairs:
            continue

        raw_counts = [count for _, count in filtered_pairs]
        if not any(raw_counts):
            continue

        filtered_series.append(
            {
                "event": entry["event"],
                "dates": [date for date, _ in filtered_pairs],
                "counts": raw_counts,
            }
        )

    if not filtered_series:
        raise ValueError("No holiday events contained data within the trailing window")

    trends_series: Dict[str, Dict[str, list]] = {}
    for entry in filtered_series:
        event_key = entry["event"]["key"]
        lookup = trends_by_event.get(event_key)
        if not lookup:
            continue

        sorted_points = sorted(lookup.items(), key=lambda item: item[0])
        if not sorted_points:
            continue

        window_start = entry["dates"][0] - timedelta(days=31)
        window_end = entry["dates"][-1] + timedelta(days=31)
        filtered_points = [
            (date_point, value)
            for date_point, value in sorted_points
            if window_start <= date_point <= window_end
        ]
        if not filtered_points:
            continue

        trend_dates = [date_point for date_point, _ in filtered_points]
        trend_values = [value for _, value in filtered_points]
        trends_series[event_key] = {"dates": trend_dates, "values": trend_values}

    if trends_series:
        fig, (ax_serp, ax_trends) = plt.subplots(
            2,
            figsize=(FIG_WIDTH_IN, FIG_HEIGHT_WITH_TRENDS),
            sharex=True,
            gridspec_kw={"height_ratios": [1, 1], "hspace": SUBPLOT_VERTICAL_GAP},
        )
    else:
        fig, ax_serp = plt.subplots(figsize=(FIG_WIDTH_IN, FIG_HEIGHT_SERP_ONLY))
        ax_trends = None

    color_cycle = plt.get_cmap("tab10")
    all_counts = []
    annotations = []
    highlight_points = []
    trend_highlight_points = []
    scaled_trends: Dict[str, Dict[str, list]] = {}
    serp_envelope_points: Dict[datetime, float] = {}
    trend_envelope_points: Dict[datetime, float] = {}
    serp_spike_segments = []
    trend_spike_segments = []
    event_date_lines = []

    for idx, series_entry in enumerate(filtered_series):
        event = series_entry["event"]
        palette_entry = EVENT_PALETTE.get(event["key"], {})
        color = palette_entry.get("serp", color_cycle(idx % color_cycle.N))
        dates = series_entry["dates"]
        counts = series_entry["counts"]
        plot_counts = [max(count, 1) for count in counts]
        all_counts.extend(plot_counts)

        baseline = max(1.0, median(counts))
        spike_threshold = baseline * SPIKE_MULTIPLIER
        spike_indices = [i for i, value in enumerate(counts) if value >= spike_threshold]
        if not spike_indices:
            spike_indices = [max(range(len(counts)), key=lambda i: counts[i])]

        spike_idx = max(spike_indices, key=lambda i: counts[i]) if spike_indices else None
        if spike_idx is not None:
            spike_date = dates[spike_idx]
            spike_value = plot_counts[spike_idx]
            highlight_points.append(
                {
                    "event": event,
                    "date": spike_date,
                    "value": spike_value,
                    "color": color,
                }
            )

            core_start_idx = max(0, spike_idx - 1)
            core_end_idx = min(len(dates) - 1, spike_idx + 1)
            serp_spike_segments.append(
                {
                    "color": color,
                    "dates": [dates[i] for i in range(core_start_idx, core_end_idx + 1)],
                    "values": [plot_counts[i] for i in range(core_start_idx, core_end_idx + 1)],
                    "linestyle": "-",
                }
            )

            if core_start_idx > 0:
                left_idx = core_start_idx - 1
                serp_spike_segments.append(
                    {
                        "color": color,
                        "dates": [dates[left_idx], dates[core_start_idx]],
                        "values": [plot_counts[left_idx], plot_counts[core_start_idx]],
                        "linestyle": "--",
                    }
                )

            if core_end_idx < len(dates) - 1:
                right_idx = core_end_idx + 1
                serp_spike_segments.append(
                    {
                        "color": color,
                        "dates": [dates[core_end_idx], dates[right_idx]],
                        "values": [plot_counts[core_end_idx], plot_counts[right_idx]],
                        "linestyle": "--",
                    }
                )

            for idx_local in range(core_start_idx, core_end_idx + 1):
                serp_envelope_points[dates[idx_local]] = max(
                    serp_envelope_points.get(dates[idx_local], 0),
                    plot_counts[idx_local],
                )

        if ax_trends is not None:
            trend_entry = trends_series.get(event["key"])
            if trend_entry:
                trend_values = trend_entry["values"]
                if trend_values:
                    scaled_values = [max(0.0, min(value, 100.0)) for value in trend_values]
                    trend_base = palette_entry.get("trends_base", color)
                    trend_color = lighten_color(trend_base)

                    scaled_trends[event["key"]] = {
                        "dates": trend_entry["dates"],
                        "values": scaled_values,
                    }

                    max_idx = max(range(len(scaled_values)), key=lambda i: scaled_values[i])
                    trend_highlight_points.append(
                        {
                            "event": event,
                            "date": trend_entry["dates"][max_idx],
                            "value": scaled_values[max_idx],
                            "color": trend_color,
                        }
                    )

                    core_start_idx = max(0, max_idx - 1)
                    core_end_idx = min(len(scaled_values) - 1, max_idx + 1)
                    trend_spike_segments.append(
                        {
                            "color": trend_color,
                            "dates": [
                                trend_entry["dates"][i] for i in range(core_start_idx, core_end_idx + 1)
                            ],
                            "values": [scaled_values[i] for i in range(core_start_idx, core_end_idx + 1)],
                            "linestyle": "-",
                        }
                    )

                    if core_start_idx > 0:
                        left_idx = core_start_idx - 1
                        trend_spike_segments.append(
                            {
                                "color": trend_color,
                                "dates": [
                                    trend_entry["dates"][left_idx],
                                    trend_entry["dates"][core_start_idx],
                                ],
                                "values": [
                                    scaled_values[left_idx],
                                    scaled_values[core_start_idx],
                                ],
                                "linestyle": "--",
                            }
                        )

                    if core_end_idx < len(scaled_values) - 1:
                        right_idx = core_end_idx + 1
                        trend_spike_segments.append(
                            {
                                "color": trend_color,
                                "dates": [
                                    trend_entry["dates"][core_end_idx],
                                    trend_entry["dates"][right_idx],
                                ],
                                "values": [
                                    scaled_values[core_end_idx],
                                    scaled_values[right_idx],
                                ],
                                "linestyle": "--",
                            }
                        )

                    for idx_local in range(core_start_idx, core_end_idx + 1):
                        trend_envelope_points[trend_entry["dates"][idx_local]] = max(
                            trend_envelope_points.get(trend_entry["dates"][idx_local], 0.0),
                            scaled_values[idx_local],
                        )

        years = sorted({date.year for date in dates})
        for year in years:
            event_dt = resolve_event_date(event, year)
            if event_dt is None:
                continue
            event_date_lines.append(
                {
                    "event": event,
                    "date": event_dt,
                    "color": color,
                }
            )

    if not all_counts:
        raise ValueError("No counts found after filtering; cannot plot")

    ymin = max(1, min(value for value in all_counts if value > 0))
    ymax = max(all_counts)
    ax_serp.set_yscale("log")
    ax_serp.set_ylim(ymin, ymax * 1.4 if ymax > 1 else 10)
    ax_serp.set_ylabel("AQL", fontsize=AXIS_LABEL_FONT_SIZE, labelpad=Y_LABEL_PAD)
    ax_serp.yaxis.set_label_coords(Y_LABEL_X_COORD, 0.5)
    ax_serp.tick_params(axis="y", labelsize=TICK_FONT_SIZE)

    auto_locator = mdates.AutoDateLocator(minticks=4, maxticks=10)
    formatter = mdates.ConciseDateFormatter(auto_locator)

    if ax_trends is not None:
        if TRENDS_Y_SCALE_MODE == "symlog":
            ax_trends.set_yscale("symlog", linthresh=TRENDS_SYMLOG_LINTHRESH)
            ax_trends.set_ylim(0, 100)
            ax_trends.yaxis.set_major_locator(mticker.FixedLocator([0, 100]))
            ax_trends.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda value, _: "100" if value >= 100 else "0")
            )
            ax_trends.yaxis.set_minor_locator(mticker.NullLocator())
            ax_trends.text(
                -0.045,
                0.5,
                "%",
                transform=ax_trends.transAxes,
                va="center",
                ha="center",
                fontsize=TICK_FONT_SIZE,
            )
            trends_label_x = Y_LABEL_X_COORD
        else:
            ax_trends.set_ylim(0, 100)
            ax_trends.yaxis.set_major_locator(mticker.MultipleLocator(20))
            trends_label_x = Y_LABEL_X_COORD
        ax_trends.set_ylabel("Google Trends", fontsize=AXIS_LABEL_FONT_SIZE, labelpad=Y_LABEL_PAD)
        ax_trends.yaxis.set_label_coords(trends_label_x, 0.5)
        ax_trends.tick_params(axis="y", labelsize=TICK_FONT_SIZE)
        ax_trends.xaxis.set_major_locator(auto_locator)
        ax_trends.xaxis.set_major_formatter(formatter)
        ax_trends.tick_params(axis="x", labelrotation=0, labelsize=TICK_FONT_SIZE)
        ax_serp.tick_params(axis="x", labelbottom=False)
    else:
        ax_serp.xaxis.set_major_locator(auto_locator)
        ax_serp.xaxis.set_major_formatter(formatter)
        ax_serp.tick_params(axis="x", labelrotation=0, labelsize=TICK_FONT_SIZE)

    leftmost = min(entry["dates"][0] for entry in filtered_series)
    rightmost = max(entry["dates"][-1] for entry in filtered_series)
    ax_serp.set_xlim(leftmost - timedelta(days=15), rightmost + timedelta(days=15))

    for segment in serp_spike_segments:
        ax_serp.plot(
            segment["dates"],
            segment["values"],
            color=segment["color"],
            linewidth=1.4,
            alpha=1.0,
            linestyle=segment.get("linestyle", "-"),
            zorder=4,
        )

    filtered_event_dates = [
        entry
        for entry in event_date_lines
        if leftmost - timedelta(days=30) <= entry["date"] <= rightmost + timedelta(days=30)
    ]
    if filtered_event_dates:
        fig = ax_serp.figure
        if ax_trends is not None:
            serp_pos = ax_serp.get_position()
            trends_pos = ax_trends.get_position()
            gap_bottom = trends_pos.y1
            gap_top = serp_pos.y0
            if gap_top <= gap_bottom:
                label_positions = (
                    gap_bottom + 0.015,
                    gap_bottom + 0.055,
                )
            else:
                gap_span = gap_top - gap_bottom
                label_positions = tuple(
                    gap_bottom + gap_span * fraction for fraction in LABEL_GAP_FRACTIONS
                )
            label_transform = blended_transform_factory(ax_serp.transData, fig.transFigure)
        else:
            label_positions = LABEL_SERP_ONLY_POSITIONS
            label_transform = blended_transform_factory(ax_serp.transData, ax_serp.transAxes)

        offsets_x_days = [0]
        for idx_entry, entry in enumerate(filtered_event_dates):
            event_color = entry["color"]
            event_date = entry["date"]
            ax_serp.axvline(
                event_date,
                color=event_color,
                linestyle=":",
                linewidth=1.1,
                alpha=1,
                zorder=1,
            )

            y_position = label_positions[idx_entry % len(label_positions)]
            base_offset = offsets_x_days[idx_entry % len(offsets_x_days)]
            manual_offset = LABEL_OFFSET_DAYS.get(entry["event"]["key"], 0)

            label_date = event_date + timedelta(days=base_offset + manual_offset)

            ax_serp.text(
                label_date,
                y_position,
                entry["event"]["label"],
                color=event_color,
                fontsize=VERTICAL_LINE_LABEL_FONT_SIZE,
                ha="center",
                va="center",
                transform=label_transform,
                bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 0.4},
                clip_on=False,
            )

    for note in annotations:
        upper_bound = ax_serp.get_ylim()[1]
        y_position = min(note["value"] * 1.2, upper_bound * 0.95)
        ax_serp.text(
            note["date"],
            y_position,
            f"{note['label']}\n{note['date'].strftime('%b %Y')}",
            color=note["color"],
            fontsize=11,
            ha="center",
            va="bottom",
            fontweight="bold",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 1.2},
        )

    handles, labels = ax_serp.get_legend_handles_labels()
    if handles:
        for handle in handles:
            handle.set_alpha(0.6)
        # legend = ax_serp.legend(
        #     handles,
        #     labels,
        #     loc="upper left",
        #     fontsize=TICK_FONT_SIZE,
        #     framealpha=0.85,
        # )
        # legend.set_zorder(4)
        # legend.get_frame().set_edgecolor("none")

    for point in highlight_points:
        date = point["date"]
        value = point["value"]
        color = point["color"]
        ax_serp.scatter(
            [date],
            [value],
            color=color,
            s=85,
            marker="o",
            edgecolors="white",
            linewidths=1.0,
            zorder=10,
            clip_on=False,
        )

    if ax_trends is not None:
        for idx, series_entry in enumerate(filtered_series):
            event = series_entry["event"]
            trend_entry = scaled_trends.get(event["key"])
            if trend_entry:
                palette_entry = EVENT_PALETTE.get(event["key"], {})
                base_color = palette_entry.get("serp", color_cycle(idx % color_cycle.N))
                trend_base = palette_entry.get("trends_base", base_color)
                trend_color = lighten_color(trend_base)

        for point in trend_highlight_points:
            trend_color = point["color"]
            ax_trends.scatter(
                [point["date"]],
                [point["value"]],
                color=trend_color,
                s=TRENDS_SPIKE_MARKER_SIZE,
                marker="o",
                edgecolors="white",
                linewidths=0.8,
                zorder=10,
                clip_on=False,
            )
            # ax_trends.text(
            #     point["date"],
            #     min(point["value"] + 0.08, 0.92),
            #     f"{point['event']['label']}\n{point['date'].strftime('%b %Y')}",
            #     color=trend_color,
            #     fontsize=10,
            #     ha="center",
            #     va="bottom",
            #     fontweight="bold",
            #     bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1.0},
            # )

        for segment in trend_spike_segments:
            ax_trends.plot(
                segment["dates"],
                segment["values"],
                color=segment["color"],
                linewidth=1.4,
                alpha=0.95,
                linestyle=segment.get("linestyle", "-"),
                zorder=4,
            )

        filtered_trend_event_dates = [
            entry
            for entry in event_date_lines
            if leftmost - timedelta(days=30) <= entry["date"] <= rightmost + timedelta(days=30)
        ]
        if filtered_trend_event_dates:
            xaxis_transform_trends = ax_trends.get_xaxis_transform()
            offsets_bottom = [0.85, 0.77, 0.69, 0.61]
            usage_bottom: Dict[datetime, int] = {}
            for entry in filtered_trend_event_dates:
                event_color = entry["color"]
                ax_trends.axvline(
                    entry["date"],
                    color=event_color,
                    linestyle=":",
                    linewidth=1.0,
                    alpha=1,
                    zorder=1,
                )

                count = usage_bottom.get(entry["date"], 0)
                usage_bottom[entry["date"]] = count + 1
                label_offset = offsets_bottom[count % len(offsets_bottom)]

                # ax_trends.text(
                #     entry["date"],
                #     label_offset,
                #     entry["event"]["label"],
                #     color=event_color,
                #     fontsize=8,
                #     ha="center",
                #     va="top",
                #     transform=xaxis_transform_trends,
                #     bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "none", "pad": 0.3},
                # )

        # ax_trends.set_xlabel("Year", fontsize=AXIS_LABEL_FONT_SIZE)
    # else:
            # ax_serp.set_xlabel("Year", fontsize=AXIS_LABEL_FONT_SIZE)

    fig.tight_layout()
    if ax_trends is not None:
        fig.subplots_adjust(left=SUBPLOT_LEFT_MARGIN, hspace=SUBPLOT_VERTICAL_GAP)
    else:
        fig.subplots_adjust(left=SUBPLOT_LEFT_MARGIN)
    plt.savefig(args.output, dpi=300, bbox_inches="tight", pad_inches=0.03)


if __name__ == "__main__":
    main()
