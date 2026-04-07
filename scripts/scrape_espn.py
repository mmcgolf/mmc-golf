"""
MMC Golf - ESPN Leaderboard Scraper
Fetches live scores from ESPN's API and writes data/scores.json
Runs via GitHub Actions every 5 minutes during tournaments.
"""

import json
import requests
import re
import os
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# ESPN's undocumented but stable public API
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"
LEADERBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/leaderboard?event={event_id}"


def fetch_current_event_id():
    """Auto-discover the active or most recent tournament event ID."""
    r = requests.get(SCOREBOARD_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    events = data.get("events", [])
    if not events:
        raise ValueError("No active golf events found on ESPN scoreboard")
    # Prefer the first active event; fall back to the first listed
    for event in events:
        status = event.get("status", {}).get("type", {}).get("name", "")
        if status in ("STATUS_IN_PROGRESS", "STATUS_SCHEDULED"):
            return event["id"], event.get("name", "Tournament"), event.get("competitions", [{}])[0].get("venue", {}).get("fullName", "")
    # Fall back to first event (could be recently completed)
    e = events[0]
    return e["id"], e.get("name", "Tournament"), e.get("competitions", [{}])[0].get("venue", {}).get("fullName", "")


def parse_score(value):
    """Convert ESPN score string to integer. 'E' -> 0, '-5' -> -5, '+3' -> 3."""
    if value is None:
        return None
    v = str(value).strip()
    if v in ("E", "EVEN", ""):
        return 0
    try:
        return int(v.replace("+", ""))
    except ValueError:
        return None


def parse_thru(value):
    """Parse thru value - returns hole number, 'F', or tee time string."""
    if value is None:
        return None
    v = str(value).strip()
    if v in ("", "-"):
        return None
    return v


def fetch_leaderboard(event_id):
    """Fetch full leaderboard for a specific event."""
    url = LEADERBOARD_URL.format(event_id=event_id)
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def build_scores_json(event_id, event_name, venue):
    """Parse ESPN leaderboard JSON into our data format."""
    raw = fetch_leaderboard(event_id)

    # Navigate to competitors list
    competition = raw.get("leaderboard", {})
    players_raw = competition.get("players", [])

    # Fallback: try events path
    if not players_raw:
        events = raw.get("events", [])
        if events:
            comps = events[0].get("competitions", [])
            if comps:
                players_raw = comps[0].get("competitors", [])

    golfers = []
    for p in players_raw:
        if not isinstance(p, dict):
            continue
        athlete = p.get("athlete", p.get("player", {}))
        name = athlete.get("displayName", athlete.get("name", "Unknown"))

        # Strip country prefix if present (ESPN sometimes prepends flag/country)
        # e.g. "United StatesScottie Scheffler" -> "Scottie Scheffler"
        name = re.sub(r"^[A-Z][a-z].*?(?=[A-Z][a-z]+\s[A-Z])", "", name).strip()

        stats = p.get("statistics", p.get("linescores", []))
        status = p.get("status", {})

        score_to_par = parse_score(
            p.get("total", status.get("thruHoleScore", None))
        )
        today = parse_score(
            p.get("currentRoundScore", None)
        )

        _thru_s = status.get("thru", {})
        thru_raw = p.get("thru", _thru_s.get("displayValue") if isinstance(_thru_s, dict) else _thru_s)
        thru = parse_thru(thru_raw)

        position = p.get("position", {})
        pos_display = position.get("displayName", position) if isinstance(position, dict) else str(position)

        cut = p.get("status", {}).get("type", {}).get("name", "") == "STATUS_CUT"
        if not cut and score_to_par is not None and score_to_par >= 999:
            cut = True

        golfers.append({
            "name": name,
            "position": pos_display,
            "scoreToPar": score_to_par,
            "today": today,
            "thru": thru,
            "cut": cut
        })

    # Determine tournament status
    status_type = raw.get("status", {}).get("type", {}).get("name", "")
    if status_type == "STATUS_IN_PROGRESS":
        status = "In Progress"
    elif status_type == "STATUS_FINAL":
        status = "Final"
    elif status_type == "STATUS_SCHEDULED":
        status = "Upcoming"
    else:
        status = status_type or "Unknown"

    current_round = raw.get("status", {}).get("period", 1)

    return {
        "tournament": event_name,
        "venue": venue,
        "status": status,
        "round": current_round,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "golfers": golfers
    }


def main():
    print(f"[{datetime.now().isoformat()}] Fetching ESPN leaderboard...")

    try:
        event_id, event_name, venue = fetch_current_event_id()
        print(f"  Event: {event_name} (ID: {event_id})")
    except Exception as e:
        print(f"  ERROR discovering event: {e}")
        raise

    try:
        scores = build_scores_json(event_id, event_name, venue)
        print(f"  Parsed {len(scores['golfers'])} players | Status: {scores['status']}")
    except Exception as e:
        print(f"  ERROR parsing leaderboard: {e}")
        raise

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "scores.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(scores, f, indent=2)

    print(f"  Saved to data/scores.json")


if __name__ == "__main__":
    main()
