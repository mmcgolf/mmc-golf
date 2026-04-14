# MMC Golf - Claude Project Memory

Read this at the start of every session.
Repo: https://github.com/mmcgolf/mmc-golf  |  Site: https://mmc-golf.com

---

## What This Is
A private golf pool for the Morris Major Championship.
181 teams of 6 golfers compete across PGA Tour majors and select events.
Single index.html hosted on GitHub Pages. Owner: Dylan Morris (morrdf3@gmail.com)

---

## Architecture

index.html is the whole app: HTML, CSS, JS, inline DATA object (~111KB)
Hosted on GitHub Pages at https://mmc-golf.com
All edits via GitHub Contents API:
  PUT https://api.github.com/repos/mmcgolf/mmc-golf/contents/index.html

### Live Score Pipeline (fully operational)
ESPN API -> scripts/scrape_espn.py -> data/scores.json
data/scores.json + picks.json + ppvs.json -> scripts/build_data.py -> data/data.json
index.html polls data/data.json every 5 min, calls initApp(data)

Workflow: .github/workflows/update_scores.yml
Schedule: */5 * * * *
Status: confirmed running successfully as of April 14 2026

Data files:
  data/picks.json   181 teams with 6 golfer picks each, plus payouts array
  data/ppvs.json    player point values
  data/scores.json  raw ESPN scores (written by scrape_espn.py)
  data/data.json    complete computed DATA object (written by build_data.py)

Scoring rules:
  6 golfers per team.
  Top 4 non-cut golfers count (sorted by scoreToPar ascending).
  Penalty: (4 - made_cut) * 1000. Tiebreaker: lowest individual score.
  teamTotal 4000 = correct pre-tournament placeholder.

---

## How to Make Changes

IMPORTANT: Cowork sandbox has NO external network access.
ALWAYS use the browser JS tool to call the GitHub API.

GitHub token: Ask Dylan for the personal access token (mmcgolf account).
It is a classic PAT starting with ghp_ with repo scope.
Store it as: window._tok = "the token"

Step 1 - Fetch file:
  (async () => {
    const r = await fetch(
      "https://api.github.com/repos/mmcgolf/mmc-golf/contents/index.html",
      { headers: {"Authorization": "token " + window._tok} }
    );
    const j = await r.json();
    window._sha = j.sha;
    window._html = atob(j.content.split("\n").join(""));
    console.log("READY sha=" + j.sha + " len=" + window._html.length);
  })();

Step 2 - Apply string replacements to window._html

Step 3 - Push:
  (async () => {
    const r = await fetch(
      "https://api.github.com/repos/mmcgolf/mmc-golf/contents/index.html",
      {
        method: "PUT",
        headers: {
          "Authorization": "token " + window._tok,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: "commit message",
          content: btoa(window._html),
          sha: window._sha
        })
      }
    );
    const j = await r.json();
    console.log("PUSH:" + r.status + " sha=" + (j.content && j.content.sha));
  })();

Critical encoding rules:
  window._html is a BINARY STRING (raw UTF-8 bytes, one JS char per byte).
  NEVER use TextEncoder - double-encodes and garbles emojis and special chars.
  Always push with plain: btoa(window._html)
  Decode with: atob(j.content.split("\n").join(""))
  Emoji search: use String.fromCharCode(bytes), e.g.
    leaf emoji = String.fromCharCode(240,159,140,191)
  If browser JS tool blocks output (Cookie/query string data),
    return: str.split("").map(c=>c.charCodeAt(0)).join(",")

---

## DATA Object (inline in index.html)

  DATA = {
    tournament, year, course,
    status: "Upcoming"|"In Progress"|"Final"|"Round Complete"|"Between Rounds",
    round, lastUpdated, totalTeams,
    teams: [{
      name,
      golfers: [{name, position:{displayName}, scoreToPar, today, thru, cut, ppv}],
      teamTotal,    // 4000 = pre-tournament (4 missing x 1000 penalty)
      validTeam, cutMade, cutMissed, pending, lowestIndividual, cutStatus, rank
    }],
    golfers: [],    // flat list of all golfers with scores
    ppvs: [],       // [{name, ppv}] sorted desc
    payouts: []     // [{place, amount}]
  }

---

## Key Window-Scoped Functions

  initApp(data)        Sets window.DATA, renders header/stats.
                       Called on load AND by 5-min poll of data/data.json.
  renderLeaderboard()  Renders leaderboard tab
  renderGolfers()      Renders golfers tab
  renderPPV()          Renders PPV tab
  renderPayouts()      Renders payouts tab
  renderTeams()        Renders teams modal
  renderGrid()         Renders ownership grid
  window._normN(name)  Unicode normalizer - strips diacritics for name matching

---

## Known Gotchas and Past Bugs

overflow-x clip for sticky headers:
  .table-wrap must use overflow-x: clip (NOT auto).
  overflow-x: auto creates scroll container breaking position:sticky on thead th.
  thead th rule: position:sticky; top:44px; z-index:2  (44px = nav height)

window._normN must be global:
  _normN is a local const inside a function scope.
  renderPPV looks for window._normN which was undefined.
  Fix: add   window._normN = _normN;   after the local declaration.

Payout splits for tied teams:
  _splitPayMap computed before display.forEach in renderLeaderboard.
  N teams tied at rank R get average of places R..R+N-1 payouts.
  Line: const payout = isPayout ? (_splitPayMap[t.rank] || 0) : 0;

Stray > in rank cells at rows 18 and 147:
  Money-line and cut-line rows close their td early.
  Fix: if (!isMoneyLine && !isCutLine) html += ">";

Nav scrollbar hidden:
  .nav-inner { scrollbar-width: none; -ms-overflow-style: none; }
  .nav-inner::-webkit-scrollbar { display: none; }

Trophy Room emoji matching:
  Emojis stored as raw UTF-8 bytes in binary string.
  Use String.fromCharCode() NOT JS emoji literals.
  leaf emoji bytes: 240, 159, 140, 191

---

## Current State April 14 2026

  Tournament: RBC Heritage 2026, starts Thu April 17
  Status: Upcoming. All scores null. teamTotals = 4000 (correct).
  Live pipeline: Active, running every 5 min (confirmed in Actions).
  Last known index.html SHA: 7a633ac622d628cda394825248b04e413b65c051

  Fixes applied this session:
  - Hidden nav scrollbar
  - window._normN exposed globally (fixes PPV tab accented name matching)
  - Trophy Room 2026 changed to Alex Hierlmeier
  - Leaderboard rank column: removed stray > at positions 18 and 147
  - Leaderboard payout splits: tied teams correctly share pooled payout
  - Sticky table headers: overflow-x:clip + top:44px

  Remaining issues:
  - today column shows raw stroke count not score-to-par, cosmetic only
  - Watch Actions logs during Heritage for name-match failures
  - Add NAME_ALIASES in build_data.py for players who do not fuzzy-match

---

## Starting a New Session

  1. Tell Claude: "Read CLAUDE.md in the mmcgolf/mmc-golf GitHub repo"
  2. Claude fetches https://api.github.com/repos/mmcgolf/mmc-golf/contents/CLAUDE.md
  3. Dylan provides the GitHub token. Claude stores it as window._tok.
  4. Fetch fresh index.html SHA before making any changes.
  5. Never assume current state - always fetch fresh from GitHub.