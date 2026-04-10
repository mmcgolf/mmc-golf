"""
MMC Golf - ESPN Leaderboard Scraper
Fetches live scores from ESPN's API and writes data/scores.json.
"""

import json
import os
import requests
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=pga"
LEADERBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=pga&event={event_id}"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def parse_score(value):
    """Parse score string like '+4', '-2', 'E' into integer."""
    if value is None:
        return None
    v = str(value).strip()
    if v in ("E", "EVEN", ""):
        return 0
    try:
        return int(v.replace("+", ""))
    except ValueError:
        return None


def fetch_current_event_id():
    """Auto-discover the active tournament event ID."""
    r = requests.get(SCOREBOARD_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    events = data.get("events", [])
    if not events:
        raise ValueError("No events found in ESPN scoreboard response")
    event = events[0]
    event_id = event["id"]
    event_name = event.get("name", "Unknown Tournament")
    venue = ""
    try:
        venue = event["competitions"][0]["venue"]["fullName"]
    except (KeyError, IndexError):
        pass
    return event_id, event_name, venue


def fetch_leaderboard(event_id):
    """Fetch full leaderboard for a specific event."""
    url = LEADERBOARD_URL.format(event_id=event_id)
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def build_scores_json(event_id, event_name, venue):
    """Parse ESPN leaderboard JSON into our data format."""
    raw = fetch_leaderboard(event_id)

    try:
        competition = raw["events"][0]["competitions"][0]
        players_raw = competition["competitors"]
    except (KeyError, IndexError):
        players_raw = []
        competition = {}

    golfers = []
    for p in players_raw:
        athlete = p.get("athlete", {})
        name = athlete.get("displayName", athlete.get("name", "Unknown"))

        score_display = p.get("score", {}).get("displayValue", None)
        score_to_par = parse_score(score_display)

        linescores = p.get("linescores", [])
        today = None
        if linescores:
            today = parse_score(linescores[-1].get("displayValue"))

        status = p.get("status", {})
        thru_raw = status.get("thru", None)
        if thru_raw is not None:
            thru_int = int(thru_raw)
            status_name = status.get("type", {}).get("name", "")
            if thru_int == 18 and status_name == "STATUS_FINISH":
                thru = "F"
            elif thru_int == 0:
                thru = None
            else:
                thru = str(thru_int)
        else:
            thru = None

        pos_display = status.get("position", {}).get("displayName", "")
        cut = status.get("type", {}).get("name", "") == "STATUS_CUT"

        golfers.append({
            "name": name,
            "position": {"displayName": pos_display} if pos_display else {},
            "scoreToPar": score_to_par,
            "today": today,
            "thru": thru,
            "cut": cut
        })

    try:
        comp_status = competition["status"]["type"]["name"]
    except KeyError:
        comp_status = ""

    if comp_status == "STATUS_IN_PROGRESS":
        status = "In Progress"
    elif comp_status == "STATUS_FINAL":
        status = "Final"
    elif comp_status == "STATUS_SCHEDULED":
        status = "Upcoming"
    elif comp_status in ("STATUS_PLAY_COMPLETE", "STATUS_END_PERIOD"):
        status = "Round Complete"
    elif comp_status == "STATUS_BETWEEN_PERIODS":
        status = "Between Rounds"
    else:
        status = comp_status or "Unknown"

    try:
        current_round = competition["status"]["period"]
    except KeyError:
        current_round = 1

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
        print(f"  Parsed {len(scores['golfers'])} players | Status: {scores['status']} | Round: {scores['round']}")
    except Exception as e:
        print(f"  ERROR parsing leaderboard: {e}")
        raise

    out_path = os.path.join(DATA_DIR, "scores.json")
    with open(out_path, "w") as f:
        json.dump(scores, f, indent=2)
    print(f"  Wrote {out_path}")


if __name__ == "__main__":
    main()
