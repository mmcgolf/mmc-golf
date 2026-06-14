"""
MMC Golf - Data Builder
Combines scores.json + picks.json + ppvs.json into a single data.json
that the website reads. Also handles name normalization between
DraftKings player names and ESPN player names.

Run this whenever picks or PPVs are updated, or let the GitHub Actions
workflow run it automatically after every score update.
"""

import json
import os
import re
from difflib import SequenceMatcher

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"  WARNING: {filename} not found, using empty default")
        return {}
    with open(path) as f:
        return json.load(f)


def normalize_name(name):
    """Lowercase, strip punctuation, collapse spaces for fuzzy matching."""
    name = name.lower().strip()
    name = re.sub(r"[.\-']", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


# Common name variations - add more as you encounter them each year
# Format: { "dk_name": "espn_name" }
NAME_ALIASES = {
    # 2026 PGA Championship - DraftKings name -> ESPN name (normalized, lowercased)
    # normalize_name() strips . - ' and lowercases, so only add aliases where
    # normalized DK name still doesn't match normalized ESPN name.

    # Hyphen in surname becomes nothing after normalize (DK: neergaardpetersen, ESPN: neergaard petersen)
    "rasmus neergaardpetersen": "rasmus neergaard petersen",

    # Middle name in DK not used by ESPN
    "jayden trey schaper": "jayden schaper",

    # Middle initial in DK not used by ESPN
    "jordan l smith": "jordan smith",

    # Compound surname in DK, ESPN uses only first part
    "angel ayora fanegas": "angel ayora",

    # Common recurring aliases (identity mappings kept for safety)
    "tom kim": "tom kim",
    "min woo lee": "min woo lee",
    "si woo kim": "si woo kim",
    "sungjae im": "sungjae im",
    "hideki matsuyama": "hideki matsuyama",
    "corey conners": "corey conners",
    "rory mcilroy": "rory mcilroy",
    "joaquin niemann": "joaqu\u00edn niemann",
    # Add new aliases here as needed
}

NAME_CACHE_PATH = os.path.join(DATA_DIR, "name_cache.json")


def load_name_cache():
    """Load persistent dk->espn name match cache from disk."""
    if os.path.exists(NAME_CACHE_PATH):
        with open(NAME_CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_name_cache(cache):
    """Persist name match cache to disk."""
    with open(NAME_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"  Saved name cache: {len(cache)} entries")


def fuzzy_match(name, candidates, threshold=0.82):
    """
    Find best matching ESPN name for a DraftKings name.
    Returns (matched_name, score) or (None, 0) if no good match.
    """
    norm = normalize_name(name)

    # Check aliases first (exact match on normalized alias)
    if norm in NAME_ALIASES:
        alias = NAME_ALIASES[norm]
        for c in candidates:
            if normalize_name(c) == alias:
                return c, 1.0

    # Exact normalized match
    for c in candidates:
        if normalize_name(c) == norm:
            return c, 1.0

    # Fuzzy match
    best_name, best_score = None, 0
    for c in candidates:
        score = SequenceMatcher(None, norm, normalize_name(c)).ratio()
        if score > best_score:
            best_score = score
            best_name = c

    if best_score >= threshold:
        return best_name, best_score
    return None, best_score


def build_golfer_lookup(scores):
    """Build a lookup dict from normalized ESPN name -> golfer data."""
    lookup = {}
    for g in scores.get("golfers", []):
        lookup[normalize_name(g["name"])] = g
        lookup[g["name"]] = g  # also index by original
    return lookup


def resolve_pick(pick_name, golfer_lookup, espn_names, name_cache=None, wd_players=None):
    """
    Resolve a DK/pick name to ESPN golfer data.
    Returns golfer dict (possibly with score=None if not found on leaderboard).
    """
    # Direct lookup
    if pick_name in golfer_lookup:
        return golfer_lookup[pick_name].copy()

    norm = normalize_name(pick_name)
    if norm in golfer_lookup:
        return golfer_lookup[norm].copy()

    # Check persistent name cache before expensive fuzzy match
    if name_cache is not None and norm in name_cache:
        cached_espn = name_cache[norm]
        if cached_espn in golfer_lookup:
            return golfer_lookup[cached_espn].copy()
        norm_cached = normalize_name(cached_espn)
        if norm_cached in golfer_lookup:
            return golfer_lookup[norm_cached].copy()

    # Fuzzy fallback
    matched, score = fuzzy_match(pick_name, espn_names)
    if matched:
        g = golfer_lookup[matched].copy()
        if score < 1.0:
            print(f"  NAME MATCH: '{pick_name}' -> '{matched}' (score={score:.2f})")
            if name_cache is not None:
                name_cache[norm] = matched  # persist for future runs
        return g

    # Check WD list before giving up
    if wd_players:
        norm = normalize_name(pick_name)
        if any(normalize_name(w) == norm for w in wd_players):
            print(f"  WD: '{pick_name}' - treating as missed cut")
            return {"name": pick_name, "position": "WD", "scoreToPar": None, "today": None, "thru": "WD", "cut": True}
    # Not found - return a placeholder (pre-tournament or withdrew)
    print(f"  NAME NOT FOUND: '{pick_name}' - not on ESPN leaderboard yet")
    return {
        "name": pick_name,
        "position": None,
        "scoreToPar": None,
        "today": None,
        "thru": None,
        "cut": False
    }


def calc_team_total(golfers):
    """Top 4 counting scores from 6 picks. Returns (total, made_cut, pending)."""
    scored = [(g["scoreToPar"], g) for g in golfers
              if not g["cut"] and g["scoreToPar"] is not None]
    scored.sort(key=lambda x: x[0])
    cut_count = sum(1 for g in golfers if g["cut"])
    pending = sum(1 for g in golfers
                  if not g["cut"] and g["scoreToPar"] is None)
    made_cut = len(scored)

    if made_cut >= 4:
        total = sum(s for s, _ in scored[:4])
        valid = True
    else:
        total = sum(s for s, _ in scored) + (4 - made_cut) * 1000
        valid = False

    lowest = scored[0][0] if scored else None

    if made_cut >= 5:
        cut_status = "safe"
    elif made_cut == 4:
        cut_status = "exact"
    else:
        cut_status = "danger"

    return total, valid, made_cut, cut_count, pending, lowest, cut_status


def main():
    print("Building data.json...")

    scores = load_json("scores.json")
    picks_data = load_json("picks.json")
    ppvs_data = load_json("ppvs.json")

    golfer_lookup = build_golfer_lookup(scores)
    espn_names = [g["name"] for g in scores.get("golfers", [])]

    wd_players = picks_data.get("wd_players", [])

    # Load name match cache (avoids fuzzy matching on every 5-min cycle)
    name_cache = load_name_cache()
    _cache_size_before = len(name_cache)

    # Deduplicate: if someone submitted multiple times, keep the latest entry
    raw_teams = picks_data.get("teams", [])
    seen_names = {}
    for t in raw_teams:
        seen_names[t["name"]] = t  # later entries overwrite earlier ones
    deduped_teams = list(seen_names.values())
    print(f"  Teams: {len(raw_teams)} raw, {len(deduped_teams)} after dedup")

    # Build teams
    teams = []
    for team in deduped_teams:
        resolved_golfers = []
        for pick in team.get("picks", []):
            name = pick["name"]
            ppv = pick.get("ppv", 0)
            g = resolve_pick(name, golfer_lookup, espn_names, name_cache, wd_players)
            g["ppv"] = ppv
            resolved_golfers.append(g)

        total, valid, made_cut, cut_count, pending, lowest, cut_status = calc_team_total(resolved_golfers)

        teams.append({
            "name": team["name"],
            "golfers": resolved_golfers,
            "teamTotal": total,
            "validTeam": valid,
            "cutMade": made_cut,
            "cutMissed": cut_count,
            "pending": pending,
            "lowestIndividual": lowest,
            "cutStatus": cut_status,
            "rank": 0  # assigned after sort
        })

    # Sort by total, tiebreak by lowest individual
    teams.sort(key=lambda t: (t["teamTotal"], (t["lowestIndividual"] or 999)))

    # Assign ranks
    for i, t in enumerate(teams):
        if (i > 0 and t["teamTotal"] == teams[i-1]["teamTotal"]
                and t["lowestIndividual"] == teams[i-1]["lowestIndividual"]):
            t["rank"] = teams[i-1]["rank"]
        else:
            t["rank"] = i + 1

    # Build PPVs from actual team picks (ensures all picked players appear in PPV tab)
    ppv_map = {}
    for team in picks_data.get("teams", []):
        for pick in team.get("picks", []):
            name = pick["name"]
            ppv = pick.get("ppv", 0)
            if name not in ppv_map:
                ppv_map[name] = ppv
    # Also include any extras from ppvs.json
    for p in ppvs_data.get("players", []):
        if p.get("name") and p["name"] not in ppv_map:
            ppv_map[p["name"]] = p.get("ppv", 0)
    ppvs = sorted([{"name": k, "ppv": v} for k, v in ppv_map.items()], key=lambda p: -p["ppv"])

    # Payouts
    payouts_raw = picks_data.get("payouts", [])
    payouts = [{"place": i + 1, "amount": amt} for i, amt in enumerate(payouts_raw)]

    out = {
        "tournament": scores.get("tournament", "The Masters"),
        "year": picks_data.get("year", 2026),
        "course": scores.get("venue", "Augusta National Golf Club"),
        "status": scores.get("status", "Upcoming"),
        "round": scores.get("round", 1),
        "lastUpdated": scores.get("lastUpdated", ""),
        "totalTeams": len(teams),
        "teams": teams,
        "golfers": scores.get("golfers", []),
        "ppvs": ppvs,
        "payouts": payouts
    }

    # Save name cache if any new matches were discovered
    if len(name_cache) > _cache_size_before:
        save_name_cache(name_cache)

    out_path = os.path.join(DATA_DIR, "data.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"  Done. {len(teams)} teams, {len(ppvs)} players, {len(out['golfers'])} on leaderboard.")
    print(f"  Saved to data/data.json")


if __name__ == "__main__":
    main()
