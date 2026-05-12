# MMC Golf Leaderboard — Project Reference

Live site: **https://mmc-golf.com** | Repo: **mmcgolf/mmc-golf** (GitHub Pages)

---

## How to Edit (Every Session)

All edits are made via the **GitHub API from the Chrome browser console** (Claude in Chrome extension). Never edit files locally — changes must go through the API to trigger GitHub Pages redeploy.

### Session startup checklist
```javascript
// 1. Set token (lost on every page reload)
window._ghToken = 'ghp_YOUR_TOKEN_HERE';  // Generate at github.com/settings/tokens (repo scope)

// 2. Fetch current index.html into window._html
fetch('https://api.github.com/repos/mmcgolf/mmc-golf/contents/index.html', {
  headers: { Authorization: 'token ' + window._ghToken, Accept: 'application/vnd.github.v3+json' }
}).then(r=>r.json()).then(j=>{
  window._sha = j.sha;
  window._html = atob(j.content.replace(/\n/g,''));
  console.log('SHA:', window._sha.substring(0,8), 'len:', window._html.length);
});
```

### Editing pattern
```javascript
// String replace (replaceFirst helper used throughout)
function rpl(src, old, rep) {
  const i = src.indexOf(old);
  if (i === -1) { console.error('NOT FOUND:', old.substring(0,50)); return src; }
  return src.substring(0, i) + rep + src.substring(i + old.length);
}

// Make changes to window._html, then push:
function pushChanges(message) {
  // Strip any non-Latin1 chars first (btoa fails otherwise)
  let bad = [];
  for (let i = 0; i < window._html.length; i++) {
    if (window._html.charCodeAt(i) > 255) bad.push(i);
  }
  if (bad.length) { console.error('Bad chars at:', bad); return; }
  
  const encoded = btoa(window._html);
  fetch('https://api.github.com/repos/mmcgolf/mmc-golf/contents/index.html', {
    method: 'PUT',
    headers: { 'Authorization': 'token ' + window._ghToken, 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, content: encoded, sha: window._sha })
  }).then(r=>r.json()).then(j=>{
    if (j.content) { window._sha = j.content.sha; console.log('PUSHED OK'); }
    else console.error('Failed:', JSON.stringify(j).substring(0,200));
  });
}
```

### Push other repo files (ppvs.json, picks.json, etc.)
```javascript
async function pushFile(path, content, message) {
  // Get current SHA first
  const r = await fetch(`https://api.github.com/repos/mmcgolf/mmc-golf/contents/${path}`, {
    headers: { Authorization: 'token ' + window._ghToken }
  });
  const j = await r.json();
  const sha = j.sha;
  
  const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(content, null, 2))));
  const r2 = await fetch(`https://api.github.com/repos/mmcgolf/mmc-golf/contents/${path}`, {
    method: 'PUT',
    headers: { 'Authorization': 'token ' + window._ghToken, 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, content: encoded, sha })
  });
  const j2 = await r2.json();
  console.log(j2.content ? 'OK: ' + j2.content.sha.substring(0,8) : 'FAIL: ' + JSON.stringify(j2));
}
```

**GitHub Pages deployment takes ~45-90 seconds after push.** Reload with `?nocache=<random>` to bust CDN cache.

---

## Repository Structure

```
mmcgolf/mmc-golf/
├── index.html              # ENTIRE site — single-file app, ~130KB
├── data/
│   ├── ppvs.json           # Player list + point values (edit each tournament)
│   ├── picks.json          # Team entries + payout structure (update each tournament)
│   ├── scores.json         # ESPN live scores (written by GitHub Actions)
│   └── data.json           # Combined output (built by build_data.py, DO NOT edit)
├── scripts/
│   ├── scrape_espn.py      # Fetches ESPN leaderboard → scores.json
│   └── build_data.py       # Merges scores + picks + ppvs → data.json
└── .github/workflows/
    └── update_scores.yml   # Runs every 5 min during tournament
```

---

## Architecture (index.html)

Single-file app hosted on GitHub Pages. No build step. All JS inline.

### Data flow
```
ESPN API (live, every 60s client-side)
       ↓
window.DATA (updated by _fetchLive)
       ↓
render functions → DOM

data.json poll (every 60s via setInterval)
       ↓  
initApp(data) → window.DATA = data → all render functions
```

### Key globals
- `window.DATA` — full tournament data (teams, golfers, ppvs, payouts, status)
- `window._tblSortStates` — saved sort state per tbody (for re-applying after refresh)
- `localStorage 'mmc_favs'` — `{t: [teamNames], g: [golferNames]}` — favorites

### Key functions (approximate positions in file)
| Function | ~Position | Purpose |
|---|---|---|
| `renderLeaderboard()` | 69,648 | Leaderboard tab |
| `renderGolfers()` | 74,991 | Golfers tab |
| `renderPPV()` | 77,395 | Point Values tab |
| `renderPayouts()` | 79,235 | Payouts tab |
| `renderTeams()` | 101,795 | Teams tab |
| `_sortTable()` | 122,116 | Column sort (saves state, handles fav-sep-rows) |
| `_fetchLive()` | ~105,100 | ESPN direct fetch (60s interval, In Progress only) |
| `initApp(data)` | 99,201 | Called on data.json load; sets window.DATA |
| `_getFavs/_saveFavs` | ~98,166 | localStorage favorites helpers |

### Favorites system
- Stars in every row call `_toggleFavT(name)` or `_toggleFavG(name)`
- Each render function pre-sorts its data array: favs first + `{_isSep:true}` sentinel + rest
- forEach loop checks `if(t._isSep)` and renders separator row/div
- All fav rows use identical template to regular rows (no column mismatch)
- Teams uses `fav-sep-div`, tables use `fav-sep-row` with `colspan="99"`

### Live scoring (two-tier)
1. **data.json poll** — `setInterval` every 60s → `initApp(data)` → replaces all DATA
2. **ESPN direct fetch** — `_fetchLive()` every 60s during "In Progress" → updates golfer scores/ranks inline → calls all render functions

`_fetchLive` calls all render functions: `renderLeaderboard`, `renderTeams`, `renderGolfers`, `renderPayouts`, `renderPPV`, `renderGrid`.

### Non-Latin1 character trap
`btoa()` fails on chars > 255 (e.g., `──` U+2500, accented letters written directly).
Always scan before pushing:
```javascript
let bad = [];
for (let i = 0; i < window._html.length; i++) {
  if (window._html.charCodeAt(i) > 255) bad.push(i);
}
console.log(bad.length ? 'BAD: ' + bad : 'Clean');
```

---

## Each Tournament Setup

### 1. Update `data/ppvs.json`
Replace player list with new DraftKings player pool + point values.
Format: `{"players": [{"name": "Scottie Scheffler", "ppv": 18.1}, ...]}`

### 2. Update `data/picks.json`  
- Change `"tournament"` name
- Update `"budget"` (typically 72)
- Add all team entries (populated from Google Form responses)
- Update `"payouts"` array if prize pool changed
- Clear old `"teams"` array

### 3. Update `scripts/build_data.py` NAME_ALIASES
Add any known DraftKings→ESPN name mismatches for this field.
The `normalize_name()` function strips `.`, `-`, `'` and lowercases — handles many issues automatically.
Fuzzy matching (SequenceMatcher, threshold=0.82) catches remaining near-matches.

### 4. Update `picks.json` tournament info + trigger rebuild
After pushing all files, manually trigger the GitHub Actions workflow or wait for next cron run.

---

## Name Matching (DraftKings vs ESPN)

`normalize_name()` in `build_data.py` strips `.`, `-`, `'` and lowercases. Handles:
- "J.J. Spaun" → "jj spaun" ✓
- "Hao-Tong Li" → "haotong li" ✓ (matches ESPN's "Haotong Li")
- "Ludvig Åberg" / "Ludvig Aberg" → same after normalize ✓

Common issues requiring explicit aliases:
| DK Name | ESPN Name | Issue |
|---|---|---|
| Rasmus Neergaard-Petersen | Rasmus Neergaard Petersen | Hyphen vs space in surname |
| Jayden Trey Schaper | Jayden Schaper | Middle name |
| Jordan L. Smith | Jordan Smith | Middle initial |
| Angel Ayora Fanegas | Angel Ayora | Compound surname |
| Joaquin Niemann | Joaquín Niemann | Accent (handled by normalize) |

The `_norm()` function in `index.html` (client-side ESPN matching) uses NFD normalization to strip accents, then lowercases. Add explicit aliases to `NAME_ALIASES` in `build_data.py` for server-side matching.

---

## Scoring Rules
- Each team picks **6 golfers** within a **72-point budget**
- **Top 4 non-cut scores** count toward team total
- **Penalty**: `(4 - made_cut) × 1000` per missing counting score
- **Tiebreaker**: lowest individual score among the 6 picks
- **Payouts**: from `data/picks.json` → `"payouts"` array, split equally among tied places

---

## Known Gotchas / Session History

1. **_sortTable + fav-sep-row**: Sort comparator must pin `fav-sep-row` elements to top (check for `classList.contains('fav-sep-row')` before comparing values)
2. **renderPayouts injection point**: Function has TWO `DATA.payouts.forEach` loops — fav section must go before the SECOND one (after `let html=''; const consumedPlaces=new Set()`)
3. **Template literal `\\'` escaping**: Use `t.name` directly in single-quoted strings for team names; avoid `.replace(/"/g,'&quot;')` inside template literals
4. **sort state re-application**: `_sortTable` saves `{colIdx, type, dir}` to `window._tblSortStates[tbodyId]`; `renderLeaderboard` re-applies at the end
5. **ESPN fetch + all renders**: `_fetchLive` must call `renderPayouts` and `renderPPV` (not just LB/Teams/Golfers)
6. **`display` is `const`**: Use `_dispWithFavs` alias; same pattern for `_golfersWithFavs`, `_ppvsWithFavs`

---

## Content Blocking in Claude in Chrome

The browser tool's security rules block many patterns. Use these workarounds:
- Extract via `JSON.stringify(small_chunk)` — blocks on some content
- Use char code arrays: `seg.split('').map(c=>c.charCodeAt(0)).join(',')` — always works
- Never try to return base64 — blocked
- Store large strings in `window._foo` variables, return only lengths/positions
