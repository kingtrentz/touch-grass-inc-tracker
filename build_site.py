"""Touch Grass Inc Tracker: runs every 10 minutes on your PC, free, no paid services.
1) pulls CWL + war data from the Clash API (fetch_cwl.py, war_stats.py; war_stats also posts Discord updates)
2) builds site/index.html (Current War), site/history.html (Historical) and site/cwl.html (CWL Tracker) from templates/
3) uploads changed pages to GitHub Pages (needs github_token.txt)
Log: run_log.txt (last 400 lines). Run by hand: double-click run_now.bat"""
import json, os, sys, subprocess, hashlib, base64, urllib.request, urllib.error, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *f: os.path.join(HERE, *f)
LOG = P("run_log.txt")

def log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    try: print(line)
    except Exception: pass
    try:
        old = open(LOG, encoding="utf-8").read().splitlines()[-399:] if os.path.exists(LOG) else []
        open(LOG, "w", encoding="utf-8").write("\n".join(old + [line]) + "\n")
    except Exception: pass

def run(script):
    flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW: no popup windows on Windows
    try:
        r = subprocess.run([sys.executable, script], cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=300, creationflags=flags)
    except Exception as e:
        log(f"{script}: could not run ({e})"); return False
    for ln in (r.stdout or "").splitlines():
        if ln.startswith(("OK", "ERROR", "DISCORD", "SEASON_END")): log(f"{script}: {ln}")
    for ln in (r.stderr or "").strip().splitlines()[-5:]:
        log(f"{script} (error output): {ln}")
    return r.returncode == 0

def main():
    try: cfg = json.load(open(P("config.json"), encoding="utf-8"))
    except Exception as e:
        log(f"ERROR config.json can't be read ({e}). Check the quotes and commas."); return 1
    minute = int(cfg.get("updateMinute", 5))
    missing = [k for k in ("clanTag", "apiKey") if "PASTE" in str(cfg.get(k, "PASTE"))]
    if missing:
        log(f"ERROR config.json still has placeholders for: {', '.join(missing)}. Open config.json and fill them in."); return 1

    ok_cwl = run("fetch_cwl.py")
    ok_stats = run("war_stats.py")

    def esc(x): return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    clan_name = cfg.get("clanName") or ""
    if not clan_name:
        try: clan_name = (json.load(open(P("stats_latest.json"), encoding="utf-8")).get("clan") or {}).get("name") or ""
        except Exception: clan_name = ""
    clan_name = clan_name or "Our Clan"
    # ---- build pages from templates + latest data (uses last good data if a fetch failed)
    pages = {}
    for tpl, data_file, out in (("current.html", "stats_latest.json", "index.html"), ("stats.html", "stats_latest.json", "history.html"), ("cwl.html", "cwl_latest.json", "cwl.html")):
        try:
            html = open(P("templates", tpl), encoding="utf-8").read()
            data = json.load(open(P(data_file), encoding="utf-8"))
            if out == "cwl.html":   # clan leaderboard comes from the war stats data
                try:
                    _st = json.load(open(P("stats_latest.json"), encoding="utf-8"))
                    data["board"] = _st.get("cwlBoard")
                    _c, _n = _st.get("current") or {}, _st.get("next") or {}
                    data["cur"] = {k: _c.get(k) for k in ("kind", "round", "state", "start", "end")} if _c else None
                    data["curNext"] = {k: _n.get(k) for k in ("kind", "round", "start", "opp")} if _n else None
                except Exception: data["board"] = None
        except Exception as e:
            log(f"ERROR building {out}: {e}"); continue
        blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        html = (html.replace("__DATA__", blob).replace("__MINUTE__", str(minute))
                    .replace("__CLAN__", esc(clan_name)).replace("__BOARD__", esc(cfg.get("leaderboardName") or "🐐 Leaderboard")).replace("__ME__", esc(cfg.get("myPlayerName", "")).replace('"', ''))
                    .replace("__RALLY__", esc(cfg.get("rallyLine") or "Get your attacks in 🫡 Everyone attacks = we win.")))
        os.makedirs(P("site"), exist_ok=True)
        open(P("site", out), "w", encoding="utf-8", newline="\n").write(html)
        pages[out] = html.encode("utf-8")
    pages[".nojekyll"] = b""
    # old Current War address forwards to the home page
    pages["current.html"] = b'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=index.html"><title>Clan Tracker</title><a href="index.html">Current War</a>'

    log(f"built pages: {', '.join(k for k in pages if k != '.nojekyll')}")

    # ---- upload to GitHub Pages
    try: token = open(P("github_token.txt"), encoding="utf-8").read().strip()
    except Exception: token = ""
    if "--no-upload" in sys.argv:
        log("Test mode (--no-upload): pages built in the site folder only."); return 0 if (ok_cwl or ok_stats) else 1
    if not token or "PASTE" in token:
        log("GitHub token not set yet (github_token.txt). Pages built locally in the site folder only."); return 0 if (ok_cwl or ok_stats) else 1
    user, repo = cfg.get("githubUser", ""), cfg.get("githubRepo", "")
    api = f"https://api.github.com/repos/{user}/{repo}"
    H = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "touch-grass-inc-tracker"}
    def gh(method, url, body=None):
        req = urllib.request.Request(url, method=method, headers=H, data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try: return e.code, json.loads(e.read() or b"{}")
            except Exception: return e.code, {}
        except Exception as e:
            return 0, {"message": str(e)}

    code, info = gh("GET", api)
    if code != 200:
        log(f"ERROR GitHub repo {user}/{repo} not reachable ({code}): {info.get('message','')}. Check the token and repo name."); return 1
    branch = info.get("default_branch", "main")

    try: st = json.load(open(P("push_state.json"), encoding="utf-8"))
    except Exception: st = {}
    # one commit per run for all changed files (GitHub Pages rebuilds once per commit)
    changed = {path: c for path, c in pages.items() if st.get(path) != hashlib.sha256(c).hexdigest()}
    pushed = 0
    if changed:
        code, ref = gh("GET", f"{api}/git/ref/heads/{branch}")
        if code != 200:
            log(f"ERROR reading branch {branch} ({code}): {ref.get('message','')}. If the repo is brand new, open it on GitHub and add a README file first, then run again."); return 1
        head = ref["object"]["sha"]
        code, cm = gh("GET", f"{api}/git/commits/{head}")
        if code != 200:
            log(f"ERROR reading latest commit ({code})"); return 1
        tree = []
        for path, content in changed.items():
            code, blob = gh("POST", f"{api}/git/blobs", {"content": base64.b64encode(content).decode(), "encoding": "base64"})
            if code != 201:
                log(f"ERROR uploading {path} ({code}): {blob.get('message','')}"); return 1
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        code, t = gh("POST", f"{api}/git/trees", {"base_tree": cm["tree"]["sha"], "tree": tree})
        if code != 201:
            log(f"ERROR building tree ({code}): {t.get('message','')}"); return 1
        code, c = gh("POST", f"{api}/git/commits", {"message": f"Update {datetime.datetime.now():%b %d %H:%M}", "tree": t["sha"], "parents": [head]})
        if code != 201:
            log(f"ERROR creating commit ({code}): {c.get('message','')}"); return 1
        code, r = gh("PATCH", f"{api}/git/refs/heads/{branch}", {"sha": c["sha"]})
        if code != 200:
            log(f"ERROR updating branch ({code}): {r.get('message','')}"); return 1
        for path, content in changed.items(): st[path] = hashlib.sha256(content).hexdigest()
        pushed = len(changed)
    if not st.get("pagesEnabled"):
        try:   # already live? then stop trying to enable it
            with urllib.request.urlopen(f"https://{user}.github.io/{repo}/", timeout=15) as r:
                if r.status == 200: st["pagesEnabled"] = True; log("GitHub Pages is live.")
        except Exception: pass
    if not st.get("pagesEnabled"):
        code, res = gh("POST", f"{api}/pages", {"source": {"branch": branch, "path": "/"}})
        if code in (201, 409): st["pagesEnabled"] = True; log("GitHub Pages is on.")
        else: log(f"NOTE couldn't turn on GitHub Pages automatically ({code}: {res.get('message','')}). "
                  "Turn it on once: repo Settings > Pages > Deploy from a branch > main > / (root) > Save.")
    json.dump(st, open(P("push_state.json"), "w", encoding="utf-8"))
    log(f"OK uploaded {pushed} changed file(s) in one commit. Site: https://{user}.github.io/{repo}/")
    return 0

def ping(ok):
    """Tell healthchecks.io this run finished (or failed). If pings stop, it emails you."""
    try: url = open(P("healthcheck_url.txt"), encoding="utf-8").read().strip()
    except Exception: return
    if not url.startswith("https://") or "PASTE" in url: return
    try: urllib.request.urlopen(url if ok else url.rstrip("/") + "/fail", timeout=10).read()
    except Exception as e: log(f"NOTE healthcheck ping failed ({e})")

if __name__ == "__main__":
    rc = main()
    ping(rc == 0)
    sys.exit(rc)
