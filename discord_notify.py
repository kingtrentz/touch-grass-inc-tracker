"""Posts your clan's war updates to a Discord webhook. Called by war_stats.py.
Events (each posted once, tracked in discord_state.json):
  - connect: one hello message the first time a webhook is configured
  - reminder: our live war has <=4h and <=1h left and people still need to attack
  - recap: one of our wars (regular or CWL) ended
  - standings: a CWL round finished for the whole group
First run with a webhook marks everything already finished as posted, so old wars are never spammed."""
import json, datetime, urllib.request, urllib.error, time

UTC = datetime.timezone.utc
CT = datetime.timezone(datetime.timedelta(hours=-6))

def esc(s):
    s = str(s)
    for ch in "\\*_~`|>#[]()":
        s = s.replace(ch, "\\" + ch)
    return s

def hm(td):
    m = max(0, int(td.total_seconds() // 60)); return f"{m // 60}h {m % 60:02d}m"

BOT = {"name": "Clan Ops"}
def post(url, content):
    body = json.dumps({"content": content[:1990], "allowed_mentions": {"parse": []}, "username": BOT["name"]}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "TouchGrassIncTracker (1.0)"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r: return r.status
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(float(json.loads(e.read() or b"{}").get("retry_after", 2))); continue
            raise RuntimeError(f"Discord webhook error {e.code}: {e.read().decode('utf-8','replace')[:200]}")

def run(cfg, out, W, P):
    BOT["name"] = ((out.get("clan") or {}).get("name") or "Clan") + " Ops"
    url = (cfg.get("discordWebhook") or "").strip()
    if not url or "PASTE" in url:
        print("DISCORD skipped (no webhook set)"); return
    try: st = json.load(open(P("discord_state.json"), encoding="utf-8"))
    except Exception: st = None
    site = f"https://{cfg.get('githubUser','').lower()}.github.io/{cfg.get('githubRepo','')}/" if cfg.get("githubUser") and cfg.get("githubRepo") else ""
    links = " · ".join(x for x in [f"Current war: <{site}>" if site else "", f"CWL tracker: <{site}cwl.html>" if site else "",
                                   f"Clan history: <{site}history.html>" if site else ""] if x)
    ended = [w for w in W.values() if w["state"] == "warEnded"]
    cwl = out.get("cwl")
    if st is None:   # first run with a webhook: baseline, then say hello
        st = {"posted": [f"recap:{w['id']}" for w in ended]}
        if cwl: st["posted"] += [f"stand:{cwl['season']}:{r}" for r in range(1, cwl["roundsDone"] + 1)]
        post(url, "🔐 **" + ((out.get("clan") or {}).get("name") or "Clan") + " Ops is online.** I'll post attack reminders, war recaps and CWL standings here.\n" + links)
        st["posted"].append("connect")
    done = set(st["posted"]); msgs = []
    now = datetime.datetime.now(UTC)
    goal = "we promote" if (out.get("current") or {}).get("kind") == "cwl" else "we win"

    # reminders
    c = out.get("current")
    if c and c["state"] == "inWar" and c.get("pending") and c.get("end"):
        left = datetime.datetime.fromisoformat(c["end"]) - now
        wid = c.get("id") or "x"
        for hrs in (1, 4):
            k = f"rem{hrs}:{wid}"
            if left <= datetime.timedelta(hours=hrs) and left.total_seconds() > 0 and k not in done:
                names = ", ".join(esc(p["n"]) + (f" (x{p['left']})" if p["left"] > 1 else "") for p in c["pending"])
                label = f"CWL Round {c['round']}" if c["kind"] == "cwl" else "War"
                msgs.append((k, f"⏰ **{hm(left)} left** · {label} vs {esc(c['opp'])} · {c['us']['s']}★ to {c['them']['s']}★\n"
                                f"Still to attack ({len(c['pending'])}): {names}\nEveryone attack = {goal}. 🫡"))
                for h2 in (1, 4): done.add(f"rem{h2}:{wid}") if h2 >= hrs else None
                break

    # recaps
    for w in sorted(ended, key=lambda x: x["end"]):
        k = f"recap:{w['id']}"
        if k in done: continue
        icon = {"win": "🏆 WIN", "lose": "❌ LOSS", "tie": "🤝 TIE"}.get(w["res"], w["res"].upper())
        label = f"CWL Round {w['round']}" if w["kind"] == "cwl" else "War"
        hitters = sorted(w["members"], key=lambda m: (-sum(a[0] for a in m["att"]), -sum(a[1] for a in m["att"])))
        top = [m for m in hitters if m["att"]][:3]
        tri = sum(1 for m in w["members"] for a in m["att"] if a[0] == 3)
        missed = [m for m in w["members"] if len(m["att"]) < w["apm"]]
        lines = [f"🏁 **{icon}** · {label} vs {esc(w['opp']['n'])}",
                 f"**{w['us']['s']}★ – {w['opp']['s']}★** · {w['us']['d']:.1f}% vs {w['opp']['d']:.1f}%",
                 f"Triples: {tri} · Attacks used: {w['us']['a']}/{w['size'] * w['apm']}"]
        if top: lines.append("Top hitters: " + ", ".join(f"{esc(m['n'])} ({sum(a[0] for a in m['att'])}★)" for m in top))
        lines.append("Missed: " + (", ".join(esc(m["n"]) for m in missed) if missed else "nobody 🫡"))
        msgs.append((k, "\n".join(lines)))

    # CWL standings after each finished round
    if cwl:
        for r in range(1, cwl["roundsDone"] + 1):
            k = f"stand:{cwl['season']}:{r}"
            if k in done: continue
            rows = []
            for i, t in enumerate(cwl["table"], 1):
                mark = "⬆️" if i <= 2 else ("⬇️" if i >= len(cwl["table"]) - 1 else "▫️")
                name = f"**{esc(t['n'])}**" if t["me"] else esc(t["n"])
                rows.append(f"{mark} {i}. {name}: {t['s']}★")
            me = next(i for i, t in enumerate(cwl["table"]) if t["me"])
            third = cwl["table"][2]["s"] if len(cwl["table"]) > 2 else 0
            cush = (cwl["table"][me]["s"] - third) if me < 2 else (cwl["table"][me]["s"] - cwl["table"][1]["s"])
            msgs.append((k, f"📊 **CWL standings after Round {r}**\n" + "\n".join(rows) +
                            f"\n{'Promo cushion' if me < 2 else 'To promo spot'}: {cush:+d}★" + (f"\n{links}" if links else "")))

    for k, m in msgs:
        post(url, m); done.add(k); print("DISCORD posted", k)
    st["posted"] = sorted(done)
    json.dump(st, open(P("discord_state.json"), "w", encoding="utf-8"))
    if not msgs: print("DISCORD nothing new")
