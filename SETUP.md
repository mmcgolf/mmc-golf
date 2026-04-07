# MMC Golf — Setup Guide

This guide walks you through getting the site live on GitHub Pages for The Masters 2026. Takes about 15 minutes. No coding experience required.

---

## What You'll Need

- A GitHub account (free) — create one at **github.com** if you don't have one
- The zip file Dylan sends you (mmc-golf.zip)
- Your PPV list (Monday night before the tournament)
- Your picks export from Google Forms (Wednesday night before the tournament)

---

## Step 1 — Create a GitHub Account

1. Go to **https://github.com** and click **Sign up**
2. Choose a username (e.g. `dylanmorris-golf`), enter your email, and set a password
3. Verify your email when GitHub sends you a confirmation link

---

## Step 2 — Create a New Repository

1. After logging in, click the **+** in the top-right corner → **New repository**
2. Name it: `mmc-golf`
3. Set it to **Public** (required for free GitHub Pages hosting)
4. Leave everything else at its defaults — **do NOT** check "Initialize this repository"
5. Click **Create repository**

---

## Step 3 — Upload All the Files

1. On the empty repo page, click **uploading an existing file**
2. Unzip `mmc-golf.zip` on your computer
3. **Drag all the files and folders** from the unzipped folder into the GitHub upload window
   - Make sure you upload the folder structure as-is: `data/`, `scripts/`, `.github/`, `index.html`, etc.
4. Scroll down, type a commit message like `Initial upload`, and click **Commit changes**

---

## Step 4 — Enable GitHub Pages

1. In your repository, go to **Settings** (top navigation bar)
2. In the left sidebar, click **Pages**
3. Under **Branch**, select `main` and keep the folder as `/ (root)`
4. Click **Save**
5. After about 60 seconds, you'll see a green banner: *"Your site is live at https://[your-username].github.io/mmc-golf/"*

That URL is your live leaderboard! Bookmark it and share it with participants.

---

## Step 5 — Enable Automatic Score Updates (GitHub Actions)

The site updates scores every 5 minutes during the tournament automatically. You just need to turn it on:

1. In your repository, click the **Actions** tab
2. You may see a message: *"Workflows aren't being run on this forked repository"* — click **I understand my workflows, go ahead and enable them**
3. In the left sidebar, click **Update Live Scores**
4. Click the **Enable workflow** button if prompted

That's it — the bot will wake up every 5 minutes during the Masters and push updated scores.

---

## Monday Night — Enter the 2026 PPVs

Once you have your PPV list ready:

1. Open `data/ppvs.json` in your repository (click on the file, then the ✏️ pencil icon to edit)
2. Replace the player list with your 2026 values using this format:

```json
{
  "players": [
    { "name": "Scottie Scheffler", "ppv": 19.5 },
    { "name": "Rory McIlroy",      "ppv": 17.0 },
    { "name": "Jon Rahm",          "ppv": 15.5 }
  ]
}
```

3. The `"name"` values must match the names you use in your picks list (DraftKings names are fine)
4. Scroll down and click **Commit changes**

---

## Wednesday Night — Enter the 2026 Picks

After exporting your Google Form responses, you need to convert them into `picks.json` format. Here's how:

### From Google Sheets (Form Responses):

Each row in your responses sheet is one participant. For each row, you need their name and 6 player picks.

The `picks.json` format is:

```json
{
  "year": 2026,
  "tournament": "The Masters",
  "budget": 72,
  "payouts": [
    { "place": 1,  "label": "1st",  "amount": 500 },
    { "place": 2,  "label": "2nd",  "amount": 250 },
    { "place": 3,  "label": "3rd",  "amount": 150 }
  ],
  "teams": [
    {
      "name": "Dylan Morris",
      "picks": [
        { "name": "Scottie Scheffler", "ppv": 18.9 },
        { "name": "Rory McIlroy",      "ppv": 16.9 },
        { "name": "Jon Rahm",          "ppv": 15.0 },
        { "name": "Bryson DeChambeau", "ppv": 14.5 },
        { "name": "Xander Schauffele", "ppv": 14.0 },
        { "name": "Tommy Fleetwood",   "ppv": 13.7 }
      ]
    }
  ]
}
```

**Tips:**
- Each participant is one object in the `"teams"` array
- The `"ppv"` for each pick should match the PPV value from your ppvs.json
- Player names must match your PPVs list exactly (the system does fuzzy matching for minor differences)
- Update the `"payouts"` section to reflect your actual payout structure and amounts

Once your `picks.json` is ready:

1. Go to your repository → `data/picks.json`
2. Click the ✏️ pencil icon
3. Replace the contents with your new file
4. Click **Commit changes**
5. Then go to the **Actions** tab → **Update Live Scores** → click **Run workflow** → **Run workflow** to force an immediate rebuild

---

## Player Name Mismatches (DraftKings vs. ESPN)

Sometimes a player's name on DraftKings differs slightly from ESPN (e.g., "Tom Kim" vs "Kim, Tom", accented characters, etc.). The system handles most of these automatically with fuzzy matching.

If you see a player showing up as "not found" in the live site, you can add a name alias:

1. Open `scripts/build_data.py` in your repository
2. Find the `NAME_ALIASES` dictionary near the top
3. Add an entry: `"dk name": "espn name"` (both in lowercase)

Example:
```python
NAME_ALIASES = {
    "joaquin niemann": "joaquín niemann",
    "byeong hun an": "byeong hun an",
    # Add new entries here:
    "tom kim": "tom kim",
}
```

---

## Sharing the Site

Your live URL will be:
```
https://[your-github-username].github.io/mmc-golf/
```

Send this to all participants on Thursday morning when the tournament starts. The leaderboard updates automatically every 5 minutes while play is in progress.

---

## For Future Majors

At the start of each new tournament:

1. Update `data/ppvs.json` with the new PPV values
2. Update `data/picks.json` with your new participants and picks
3. Update the `"year"` and `"tournament"` fields in `picks.json`
4. Clear `data/scores.json` back to the empty placeholder (optional — the scraper will overwrite it anyway)
5. Make sure the GitHub Actions workflow is enabled

The site and all automation carry over automatically — you only need to update the data files.
