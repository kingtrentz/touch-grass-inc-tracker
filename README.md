# Touch Grass Inc Tracker 🌱

A free, self-updating war room for your Clash of Clans clan. It runs on your own PC every 10 minutes and publishes three pages to a free GitHub Pages site your whole clan can open:

- **Current War**: live score, who still needs to attack, this war's top 3, keys to victory, a scouting report and projection, plus a live countdown.
- **Clan History**: record, streaks, last CWL result, a leaderboard ranked by an MVP formula, war MVPs, recent form and donations.
- **CWL Tracker**: standings with promotion and demotion lines, round-by-round results, a clan leaderboard for the season and a round countdown.

Light and dark mode included. It costs nothing to run.

---

## What you need

- A **Windows PC** that stays on and logged in most of the time. A locked screen is fine.
- A free **Clash of Clans developer account**.
- A free **GitHub account**.
- About **30 to 45 minutes** for the one-time setup.
- **Your clan's War Log set to Public.** A leader or co-leader can change this in clan settings. If it's private, CWL still works, but regular wars can't be tracked because the game hides them.

---

## Setup, step by step

### 1. Download this kit
On this page, click the green **Code** button → **Download ZIP**. Unzip it somewhere you'll keep it, like your Documents folder. Don't run it from the Downloads folder.

### 2. Install Python
Open the **Microsoft Store**, search **Python 3**, and install the newest version.

### 3. Get your Clash of Clans API key
1. On the PC that will run the tracker, search Google for **what is my IP** and copy the number it shows.
2. Go to **developer.clashofclans.com**, create an account and log in.
3. Open **My Account** → **Create New Key**. Give it any name and description, and paste your IP into **Allowed IP Addresses**.
4. Copy the long **token** it gives you. That's your API key.

> The key only works from that IP. If your home internet IP ever changes, the tracker stops updating until you create a new key with the new IP.

### 4. Make your GitHub repo
1. Sign in to **github.com** → click **+** (top right) → **New repository**.
2. Name it whatever you want (example: `my-clan-tracker`), set it to **Public**, and **check "Add a README file"**. The tracker needs the repo to not be empty.
3. Click **Create repository**.

### 5. Make a GitHub token
1. On GitHub, click your profile picture → **Settings** → **Developer settings** (bottom left) → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Repository access**: choose **Only select repositories** and pick the repo from step 4.
3. **Permissions → Repository permissions**: set **Contents** to **Read and write**. Optionally set **Pages** to **Read and write** too, which lets the tracker turn on your site for you.
4. Generate it and copy the token. GitHub only shows it once.

### 6. Fill in your settings
In the kit folder, open these in Notepad:

- **config.json**: replace the `PASTE_...` values:
  - `clanTag`: your clan tag with the `#`, like `"#2ABC123"` (use zeros, not the letter O)
  - `apiKey`: the key from step 3
  - `githubUser`: your GitHub username
  - `githubRepo`: the repo name from step 4
- **github_token.txt**: replace `PASTE_TOKEN_HERE` with the token from step 5.

Keep the quotes and commas exactly as they are. The other settings are optional (see below).

### 7. Run setup
Double-click **setup.bat**. It runs the first update, then sets Windows to update every 10 minutes on its own. When it finishes, it prints your site link.

### 8. Turn on your site (if setup didn't)
On GitHub, open your repo → **Settings** → **Pages** → under **Branch**, choose **main** and **/ (root)** → **Save**. Wait 2 or 3 minutes.

### 9. Open it
Your site is at `https://YOUR-USERNAME.github.io/YOUR-REPO/`. Share that link with your clan.

---

## Optional settings (config.json)

| Setting | What it does |
|---|---|
| `clanName` | Overrides the clan name shown on the pages. Leave `""` to use the name from the game. |
| `myPlayerName` | Your in-game name. Optional. |
| `leaderboardName` | Title of the leaderboard on Clan History. Default `🐐 Leaderboard`. |
| `rallyLine` | The one-line attack reminder on the CWL Tracker. |
| `cwlPromote` / `cwlDemote` | How many clans promote and demote in your CWL league (check the Group tab in game). Default 2 and 2. |
| `discordWebhook` | Paste a Discord webhook URL to get automatic attack reminders, war recaps and CWL standings in a channel. Needs the **Manage Webhooks** permission on that server. |

**Down alerts (optional):** make a free check at **healthchecks.io** (period 1 hour, grace 1 hour), copy its ping URL into **healthcheck_url.txt**, and you'll get an email if updates ever stop.

---

## How MVP works

Attack stars first, then the fewest stars your base gave up, then hitting up and tougher bases, then attack %, then the lowest % given up. A base nobody attacked counts as untested (between 1★ and 2★ given). An attack still unused when the war ends costs **−1★**. Town Hall level isn't weighed, since rushed bases are everywhere. The same order ranks the leaderboard and the suggested lineup (which unlocks after 10 tracked wars).

The game only shows attack detail for the current war, so stats start from your first update and build up over time.

---

## If something goes wrong

Open **run_log.txt** in the kit folder. The last lines say what happened.

- **`accessDenied.invalidIp`**: your IP changed. Make a new API key with your new IP (step 3) and paste it into config.json.
- **`inMaintenance`**: Supercell's servers are down for maintenance. The tracker picks back up on its own.
- **War log is private**: set it to Public in clan settings, or just use the CWL Tracker.
- **Site not updating**: make sure the PC is on and logged in. To update right away, double-click **run_now.bat**.

**Never share config.json or github_token.txt.** They hold your keys. Only the built pages get uploaded to GitHub.

---

## Credits

Built by **kingtrents⚡️** (Den of Thieves) with Claude. Free to use and share, not for sale.

This material is unofficial and is not endorsed by Supercell. For more information see Supercell's Fan Content Policy: www.supercell.com/fan-content-policy.
