"""
MMC Golf - ESPN Leaderboard Scraper
Fetches live scores from ESPN's API and writes data/scores.json.
Retries up to 3 times with backoff on network errors.
"""

import json
import os
import time
import requests
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=pga"
LEADERBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=pga&event={event_id}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries

# Keywords used to confirm ESPN's "current" event is actually THIS tournament.
# ESPN's leaderboard endpoint returns whatever event is most recent/active -
# in the days between majors that can still be LAST week's (already-Final)
# event, which would otherwise get mislabeled as this tournament. Update this
# list each time you set up a new major.
TARGET_TOURNAMENT_KEYWORDS = ["open championship", "british open", "the open"]

# Used for the placeholder scores.json when no matching ESPN event is found yet
# (i.e. this tournament hasn't started and ESPN hasn't published it). Update
# these each time you set up a new major/tournament.
PLACEHOLDER_TOURNAMENT_NAME = "The Open Championship"
PLACEHOLDER_VENUE = "Royal Birkdale"


def fetch_with_retry(url, retries=MAX_RETRIES):
    """GET a URL, retrying up to `retries` times on failure."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f"  Attempt {attempt} failed: {e}. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
    raise last_err


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
    """
    Find the ESPN event that matches TARGET_TOURNAMENT_KEYWORDS.
    Returns (event_id, event_name, venue) or (None, None, None) if ESPN
    hasn't published this tournament yet (e.g. it hasn't started and the
    top "current" event is still last week's, already-completed one).
    """
    r = fetch_with_retry(SCOREBOARD_URL)
    data = r.json()
    events = data.get("events", [])
    if not events:
        return None, None, None

    for event in events:
        name = (event.get("name") or "").lower()
        if any(kw in name for kw in TARGET_TOURNAMENT_KEYWORDS):
            event_id = event["id"]
            event_name = event.get("name", "Unknown Tournament")
            venue = ""
            try:
                venue = event["competitions"][0]["venue"]["fullName"]
            except (KeyError, IndexError):
                pass
            return event_id, event_name, venue

    return None, None, None


def fetch_leaderboard(event_id):
    """Fetch full leaderboard for a specific event."""
    url = LEADERBOARD_URL.format(event_id=event_id)
    r = fetch_with_retry(url)
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

        linescores = p.get("linescores", [])
        # Filter out empty placeholder rounds (future rounds have no displayValue)
        active = [r for r in linescores if r.get("displayValue") is not None]

        # Total score = sum of all active round scores (score field only has current round)
        score_to_par = sum(parse_score(r.get("displayValue")) or 0 for r in active) if active else None

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

        # Today = most recent active round, only if player has started (thru != None)
        today = parse_score(active[-1].get("displayValue")) if (active and thru is not None) else None

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
    except Exception as e:
        print(f"  ERROR discovering event: {e}")
        raise

    if event_id is None:
        print(f"  No ESPN event matching {TARGET_TOURNAMENT_KEYWORDS} yet - "
              f"writing an 'Upcoming' placeholder instead of misattributing "
              f"another event's (possibly Final) data to this tournament.")
        scores = {
            "tournament": PLACEHOLDER_TOURNAMENT_NAME,
            "venue": PLACEHOLDER_VENUE,
            "status": "Upcoming",
            "round": 0,
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
            "golfers": []
        }
    else:
        print(f"  Event: {event_name} (ID: {event_id})")
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
