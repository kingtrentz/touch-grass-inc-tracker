"""Touch Grass Inc Tracker war stats: regular wars + CWL, per-player history, Discord posts.
Writes stats_latest.json (compact) next to this file. Run: python3 war_stats.py"""
import json, os, sys, hashlib, datetime, urllib.request, urllib.parse, urllib.error, time

def LOCAL_STAMP():
    n = datetime.datetime.now()
    return f"{n:%b} {n.day}, {n.hour % 12 or 12}:{n:%M} {n:%p} CT"

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda f: os.path.join(HERE, f)
API = "https://api.clashofclans.com/v1"
cfg = json.load(open(P("config.json"), encoding="utf-8"))
KEY, TAG = cfg["apiKey"].strip(), cfg["clanTag"].strip().upper()
if not TAG.startswith("#"): TAG = "#" + TAG
q = urllib.parse.quote
UTC = datetime.timezone.utc
NOW = datetime.datetime.now(UTC)

def get(path, ok404=False):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if ok404 and e.code == 404: return None
        sys.exit(f"ERROR {e.code} on {path}: {body}")

def soft_get(path):
    """Like get(), but a private war log (403) or missing data returns None instead of stopping the run."""
    try: return get(path, ok404=True)
    except SystemExit: return None

def ts(s):
    try: return datetime.datetime.strptime(s, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=UTC)
    except Exception: return None

def load(f, default):
    try: return json.load(open(P(f), encoding="utf-8"))
    except Exception: return default

hist = load("history.json", {"wars": {}})
W = hist["wars"]

# ---------- capture one war's detail into history ----------
def capture(w, wid, kind, rnd=None):
    if w.get("state") not in ("preparation", "inWar", "warEnded"): return
    a, b = w["clan"], w["opponent"]
    if TAG not in (a.get("tag"), b.get("tag")): return
    us, them = (a, b) if a["tag"] == TAG else (b, a)
    def ranked(side):
        mem = sorted(side.get("members", []), key=lambda m: m.get("mapPosition", 999))
        return {m["tag"]: (i + 1, m) for i, m in enumerate(mem)}
    R_us, R_them = ranked(us), ranked(them)
    apm = w.get("attacksPerMember") or (1 if kind == "cwl" else 2)
    members = []
    for tagm, (rank, m) in R_us.items():
        att = []
        for x in m.get("attacks", []) or []:
            dr = R_them.get(x.get("defenderTag"))
            att.append([x["stars"], round(x["destructionPercentage"], 1), dr[0] if dr else None, dr[1].get("townhallLevel") if dr else None])
        bo = m.get("bestOpponentAttack")
        members.append({"tag": tagm, "n": m["name"], "th": m.get("townhallLevel"), "rank": rank, "att": att,
                        "defN": m.get("opponentAttacks", 0), "defS": bo["stars"] if bo else None, "defD": round(bo["destructionPercentage"], 1) if bo else None})
    st = w["state"]
    res = ""
    if st == "warEnded":
        if us["stars"] != them["stars"]: res = "win" if us["stars"] > them["stars"] else "lose"
        elif us["destructionPercentage"] != them["destructionPercentage"]: res = "win" if us["destructionPercentage"] > them["destructionPercentage"] else "lose"
        else: res = "tie"
    W[wid] = {"id": wid, "kind": kind, "round": rnd, "state": st, "end": w.get("endTime", ""), "start": w.get("startTime", ""),
              "size": w.get("teamSize"), "apm": apm, "res": res,
              "us": {"s": us["stars"], "d": round(us["destructionPercentage"], 2), "a": us.get("attacks", 0)},
              "opp": {"n": them["name"], "tag": them["tag"], "s": them["stars"], "d": round(them["destructionPercentage"], 2), "a": them.get("attacks", 0)},
              "members": members,
              "usTH": [m.get("townhallLevel") for _, m in sorted(R_us.values(), key=lambda x: x[0])],
              "oppTH": [m.get("townhallLevel") for _, m in sorted(R_them.values(), key=lambda x: x[0])]}

# ---------- fetch ----------
clan = get(f"/clans/{q(TAG)}")
roster = get(f"/clans/{q(TAG)}/members?limit=50").get("items", [])
LOG_PUBLIC = bool(clan.get("isWarLogPublic"))
wl = ((soft_get(f"/clans/{q(TAG)}/warlog?limit=60") or {}).get("items", [])) if LOG_PUBLIC else []
cw = (soft_get(f"/clans/{q(TAG)}/currentwar") or {}) if LOG_PUBLIC else {}
if not LOG_PUBLIC: print("OK note: clan war log is private, so regular wars can't be tracked (CWL still works). Set it to public in clan settings.")
if cw.get("state") in ("preparation", "inWar", "warEnded"):
    capture(cw, "R-" + (cw.get("preparationStartTime") or cw.get("startTime") or "x"), "regular")
group = get(f"/clans/{q(TAG)}/currentwar/leaguegroup", ok404=True)
cwl = None
clanHist = {}
if group and group.get("rounds"):
    names = {c["tag"]: c["name"] for c in group["clans"]}
    tot = {t: {"n": n, "s": 0, "d": 0.0, "w": 0} for t, n in names.items()}
    clanHist = {n: [] for n in names.values()}
    rounds_final = []
    for i, rnd in enumerate(group["rounds"], 1):
        states = []
        for wt in rnd.get("warTags", []):
            if not wt or wt == "#0": continue
            w = get(f"/clanwarleagues/wars/{q(wt)}")
            states.append(w.get("state"))
            capture(w, "C-" + group.get("season", "") + "-" + wt, "cwl", i)
            if w.get("state") in ("inWar", "warEnded"):
                for side, other in ((w["clan"], w["opponent"]), (w["opponent"], w["clan"])):
                    t = tot[side["tag"]]; t["s"] += side["stars"]; t["d"] += side["destructionPercentage"] * (w.get("teamSize") or 0)
                    if w["state"] == "warEnded": clanHist.setdefault(side["name"], []).append((side["stars"], side["destructionPercentage"]))
                    if w["state"] == "warEnded" and (side["stars"], side["destructionPercentage"]) > (other["stars"], other["destructionPercentage"]):
                        t["w"] += 1
        rounds_final.append(bool(states) and all(s == "warEnded" for s in states))
    table = sorted(({"n": v["n"], "s": v["s"] + 10 * v["w"], "d": round(v["d"]), "me": t == TAG} for t, v in tot.items()), key=lambda r: (-r["s"], -r["d"]))
    done = sum(1 for f in rounds_final if f)
    cwl = {"season": group.get("season", ""), "state": group.get("state", ""), "roundsDone": done, "table": table}

hist["updated"] = NOW.isoformat(timespec="seconds")
json.dump(hist, open(P("history.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---------- aggregate players ----------
cur = {m["tag"]: m for m in roster}
agg = {}
wars_sorted = sorted(W.values(), key=lambda x: x["end"])
for w in wars_sorted:
    if w["state"] == "preparation": continue
    ended = w["state"] == "warEnded"
    for m in w["members"]:
        a = agg.setdefault(m["tag"], {"wars": 0, "avail": 0, "usedEnded": 0, "att": 0, "stars": 0, "tri": 0, "destr": 0.0,
                                      "up": 0, "same": 0, "down": 0, "defN": 0, "defWars": 0, "defStars": 0, "lastMiss": "", "streak": 0, "tr": 0, "trN": 0, "defD": 0.0})
        a["wars"] += 1
        if ended:
            a["avail"] += w["apm"]; a["usedEnded"] += len(m["att"])
            if len(m["att"]) < w["apm"]: a["lastMiss"] = w["end"]
        for s, d, dr, _ in m["att"]:
            a["att"] += 1; a["stars"] += s; a["tri"] += (s == 3); a["destr"] += d
            if dr is not None:
                a["tr"] += dr; a["trN"] += 1
                if dr < m["rank"]: a["up"] += 1
                elif dr > m["rank"]: a["down"] += 1
                else: a["same"] += 1
        a["defN"] += m["defN"]
        if m["defN"] and m["defS"] is not None: a["defWars"] += 1; a["defStars"] += m["defS"]; a["defD"] += m["defD"] or 0   # untested bases left out
players = []
for tagm, m in cur.items():
    a = agg.get(tagm)
    row = [m["name"], m.get("townHallLevel"), m.get("role", "member")]
    if a:
        row += [a["wars"], a["usedEnded"], a["avail"], a["att"], a["stars"], a["tri"], round(a["destr"] / a["att"], 1) if a["att"] else None,
                a["up"], a["same"], a["down"], a["defWars"], a["defStars"], round(a["tr"] / a["trN"], 1) if a["trN"] else None,
                round(a["defD"] / a["defWars"], 1) if a["defWars"] else None]
    else:
        row += [0] * 6 + [None] + [0] * 5 + [None, None]
    players.append(row)
PCOLS = ["n", "th", "role", "wars", "used", "avail", "att", "stars", "tri", "avgD", "up", "same", "down", "defWars", "defStars", "avgT", "givenD"]

# ---------- current war (ours) ----------
_ws = sorted(W.values(), key=lambda x: x["end"])
live = next((w for w in _ws if w["state"] == "inWar"), None) or next((w for w in _ws if w["state"] == "preparation"), None)
curw = None
if live:
    pend = [{"n": m["n"], "th": m["th"], "left": live["apm"] - len(m["att"])} for m in sorted(live["members"], key=lambda m: m["rank"]) if len(m["att"]) < live["apm"]]
    e = ts(live["end"]); s0 = ts(live["start"])
    curw = {"id": live["id"], "kind": live["kind"], "round": live["round"], "state": live["state"], "opp": live["opp"]["n"], "size": live["size"], "apm": live["apm"],
            "us": live["us"], "them": live["opp"], "end": e.isoformat() if e else "", "start": s0.isoformat() if s0 else "",
            "pending": pend if live["state"] == "inWar" else [], "attacksLeft": sum(p["left"] for p in pend) if live["state"] == "inWar" else None}
    import collections
    curw["usTH"] = dict(collections.Counter(live.get("usTH") or [])); curw["oppTH"] = dict(collections.Counter(live.get("oppTH") or []))

# ---------- war log (regular wars only) ----------
log = []
for it in wl:
    o = it.get("opponent", {})
    if not o.get("name"): continue   # CWL season summary rows have no opponent
    e = ts(it.get("endTime", ""))
    log.append([e.strftime("%Y-%m-%d") if e else "", it.get("result") or "", it.get("teamSize"), it["clan"].get("stars"), o.get("stars"),
                round(it["clan"].get("destructionPercentage", 0), 1), round(o.get("destructionPercentage", 0), 1), o["name"], it.get("attacksPerMember")])

# ---------- drill-down: each player's recent wars (compact) ----------
tracked = [w for w in sorted(W.values(), key=lambda x: x["end"], reverse=True) if w["state"] != "preparation"]
dwars = []
for w in tracked:
    e = ts(w["end"])
    label = f"CWL R{w['round']}" if w["kind"] == "cwl" else f"{w['size']}v{w['size']}"
    dwars.append([label, w["opp"]["n"], w["res"] or "live", e.strftime("%Y-%m-%d") if e else "", w["apm"]])
widx = {w["id"]: i for i, w in enumerate(tracked)}
names_idx = {m["tag"]: i for i, m in enumerate(cur.values())}
dp = {}
for w in tracked:
    for m in w["members"]:
        if m["tag"] not in names_idx: continue
        rows = dp.setdefault(str(names_idx[m["tag"]]), [])
        if len(rows) < 6:
            rows.append([widx[w["id"]], m["rank"], [[a[0], a[1], a[2]] for a in m["att"]], m["defS"]])
drill = {"wars": dwars[:40], "p": dp}

# ---------- yearly donations ledger (game resets donations each season) ----------
year = datetime.datetime.now().year
led = load("donations.json", {"year": year, "since": NOW.isoformat(timespec="seconds"), "p": {}})
if led.get("year") != year:   # new calendar year: archive and start fresh from current counters
    json.dump(led, open(P(f"donations_{led.get('year')}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    led = {"year": year, "since": NOW.isoformat(timespec="seconds"),
           "p": {m["tag"]: {"n": m["name"], "bg": 0, "br": 0, "lg": m.get("donations", 0), "lr": m.get("donationsReceived", 0),
                            "base_g": m.get("donations", 0), "base_r": m.get("donationsReceived", 0)} for m in roster}}
for m in roster:
    g, r = m.get("donations", 0), m.get("donationsReceived", 0)
    e = led["p"].get(m["tag"])
    if e is None:
        led["p"][m["tag"]] = {"n": m["name"], "bg": 0, "br": 0, "lg": g, "lr": r, "base_g": 0, "base_r": 0}; continue
    e["n"] = m["name"]
    if g < e["lg"] or r < e["lr"]:   # season reset happened: bank last season's final counts
        e["bg"] += e["lg"] - e["base_g"]; e["br"] += e["lr"] - e["base_r"]; e["base_g"] = e["base_r"] = 0
    e["lg"], e["lr"] = g, r
json.dump(led, open(P("donations.json"), "w", encoding="utf-8"), ensure_ascii=False)
don = {"year": year, "since": led["since"],
       "rows": [[m["name"], led["p"][m["tag"]]["bg"] + led["p"][m["tag"]]["lg"] - led["p"][m["tag"]]["base_g"],
                 led["p"][m["tag"]]["br"] + led["p"][m["tag"]]["lr"] - led["p"][m["tag"]]["base_r"]] for m in roster]}

# ---------- war MVPs (one per tracked war) ----------
def _score(w, m):
    """MVP order: attack stars, then fewest stars given up on defense, then hitting up / tougher bases, then attack %, then lowest % given up."""
    att = m["att"]
    if not att: return None
    stars = sum(a[0] for a in att); dest = sum(a[1] for a in att)
    ups = [m["rank"] - a[2] for a in att if a[2] is not None and a[2] < m["rank"]]
    on1 = any(a[2] == 1 and a[0] > 0 for a in att)
    slots = w["apm"] if w["state"] == "warEnded" else len(att)
    if m["defN"] and m["defS"] is not None: dS, dD = m["defS"], m["defD"] or 0
    else: dS, dD = 1.5, 50   # untested base (nobody attacked it): middle of the pack, can't beat a proven 0-1★ defense
    tgt = [a[2] for a in att if a[2] is not None]
    missed = max(0, slots - len(att)) if w["state"] == "warEnded" else 0   # every missed attack = -1 star
    key = (round((stars - missed) / max(1, slots), 3), -dS, min(sum(ups), 10) + (1 if on1 else 0), -(sum(tgt) / len(tgt) if tgt else 99),
           round(dest / max(1, slots), 1), -dD)
    return key, stars, ups, on1
def _mvp(w):
    best = None
    for m in w["members"]:
        r = _score(w, m)
        if r is None: continue
        if best is None or r[0] > best[0]: best = (r[0], m, r[1], r[2], r[3])
    if not best: return None
    _, m, stars, ups, on1 = best
    att = m["att"]
    tri_up = [a for a in att if a[0] == 3 and a[2] is not None and a[2] < m["rank"]]
    n_tri_up = sum(1 for x in w["members"] if any(a[0] == 3 and a[2] is not None and a[2] < x["rank"] for a in x["att"]))
    why = []
    if w["apm"] == 1:
        a = att[0]; why.append(f"{a[0]}★ {a[1]:.0f}% on #{a[2]}" + (f", hitting up {m['rank'] - a[2]} spots" if a[2] and a[2] < m["rank"] else ""))
    else:
        why.append(("perfect " if stars == 3 * w["apm"] else "") + f"{stars}★ from {len(att)} hits" + (f", hit up {sum(ups)} spots" if ups else ""))
    if tri_up and n_tri_up <= 2: why.append("only 3★ above their spot" if n_tri_up == 1 else "one of 2 to 3★ above their spot")
    if w["apm"] == 1 and att[0][0] == 3:
        tri_targets = [a[2] for x in w["members"] for a in x["att"] if a[0] == 3 and a[2] is not None]
        if len(tri_targets) > 1 and att[0][2] == min(tri_targets): why.append(f"toughest of {len(tri_targets)} triples")
    elif on1: why.append("took stars off the #1 base")
    if m["defN"] and m["defS"] == 0: why.append("nobody got a star on their base")
    elif m["defN"] and m["defS"] == 1: why.append(f"only gave up 1★ on defense ({m['defD']:.0f}%)")
    elif m["defN"] and m["defS"] == 2: why.append(f"held their base to 2★ ({m['defD']:.0f}%)")
    return m, "; ".join(why)
mvps = []
for w in tracked:
    if w["state"] not in ("inWar", "warEnded"): continue
    r = _mvp(w)
    if not r: continue
    e = ts(w["end"])
    label = f"CWL R{w['round']}" if w["kind"] == "cwl" else f"{w['size']}v{w['size']}"
    mvps.append([label, w["opp"]["n"], e.strftime("%Y-%m-%d") if e else "", w["res"] or "live", r[0]["n"], r[1], w["id"]])
mvps = mvps[:40]

# ---------- CWL clan leaderboard (this season) ----------
cwlBoard = None
_season = (group or {}).get("season") or max((w["id"][2:9] for w in W.values() if w["kind"] == "cwl"), default="")
if _season:
    cw_wars = [w for w in W.values() if w["kind"] == "cwl" and w["id"].startswith(f"C-{_season}-") and w["state"] in ("inWar", "warEnded")]
    mvp_ids = {}
    for row in mvps:
        if row[6].startswith(f"C-{_season}-") and row[3] != "live": mvp_ids[row[4]] = mvp_ids.get(row[4], 0) + 1
    B = {}
    for w in sorted(cw_wars, key=lambda x: x["end"]):
        for m in w["members"]:
            b = B.setdefault(m["tag"], {"n": m["n"], "th": m["th"], "wars": 0, "att": 0, "s": 0, "tri": 0, "d": 0.0, "miss": 0, "tr": 0, "dS": 0, "dN": 0})
            b["n"], b["th"] = m["n"], m["th"]; b["wars"] += 1
            for a in m["att"]:
                b["att"] += 1; b["s"] += a[0]; b["tri"] += (a[0] == 3); b["d"] += a[1]; b["tr"] += a[2] or 30
            if w["state"] == "warEnded" and len(m["att"]) < w["apm"]: b["miss"] += w["apm"] - len(m["att"])
            if m["defN"] and m["defS"] is not None: b["dS"] += m["defS"]; b["dN"] += 1   # untested bases left out of the average
    rows = sorted(B.values(), key=lambda b: (-(b["s"] - b["miss"]), b["dS"] / b["dN"] if b["dN"] else 1.5, b["tr"] / max(1, b["att"]), -b["d"], b["miss"], -mvp_ids.get(b["n"], 0)))
    cwlBoard = {"season": _season, "wars": len(cw_wars),
                "cols": ["n", "th", "wars", "att", "s", "tri", "avgD", "miss", "mvps", "given", "net"],
                "rows": [[b["n"], b["th"], b["wars"], b["att"], b["s"], b["tri"], round(b["d"] / b["att"], 1) if b["att"] else None, b["miss"], mvp_ids.get(b["n"], 0), round(b["dS"] / b["dN"], 1) if b["dN"] else None, b["s"] - b["miss"]] for b in rows]}

# ---------- current war: top 3 so far ----------
curTop = []
if live and live["state"] == "inWar":
    sc = []
    for m in live["members"]:
        r = _score(live, m)
        if r: sc.append((r[0], m, r[1], 0))
    sc.sort(key=lambda x: x[0], reverse=True)
    for _, m, stars, dest in sc[:3]:
        line = " · ".join(f"{a[0]}★ {a[1]:.0f}% on #{a[2]}" for a in m["att"])
        if m["defN"] and m["defS"] is not None: line += f" · base gave up {m['defS']}★"
        curTop.append([m["n"], m["th"], m["rank"], stars, line])

# ---------- next war preview + projection ----------
from collections import Counter
nxt = None
prep = sorted((w for w in W.values() if w["state"] == "preparation" and (ts(w["start"]) or NOW) > NOW), key=lambda x: x["start"])
if prep:
    w = prep[0]
    me_name = clan.get("name") or ""
    def _avg(lst): return (round(sum(x[0] for x in lst) / len(lst), 1), round(sum(x[1] for x in lst) / len(lst), 1), len(lst)) if lst else (None, None, 0)
    if w["kind"] == "cwl":
        uA, uD, uN = _avg(clanHist.get(me_name, []))
        oA, oD, oN = _avg(clanHist.get(w["opp"]["n"], []))
    else:
        recent = [r for r in log[:10] if r[2]]
        uA = round(sum(r[3] / r[2] for r in recent) / len(recent) * w["size"], 1) if recent else None
        uD = round(sum(r[5] for r in recent) / len(recent), 1) if recent else None
        uN, oA, oD, oN = len(recent), None, None, 0
    # who's in our lineup + any missed attacks this CWL / tracked
    missed = {}
    for x in W.values():
        if x["state"] != "warEnded": continue
        if w["kind"] == "cwl" and not x["id"].startswith(w["id"][:12]): continue
        for m in x["members"]:
            if len(m["att"]) < x["apm"]: missed[m["tag"]] = missed.get(m["tag"], 0) + x["apm"] - len(m["att"])
    lineup = [[m["n"], m["th"], missed.get(m["tag"], 0)] for m in sorted(w["members"], key=lambda m: m["rank"])]
    st0 = ts(w["start"])
    nxt = {"kind": w["kind"], "round": w["round"], "opp": w["opp"]["n"], "start": st0.isoformat() if st0 else "", "size": w["size"],
           "usTH": dict(Counter(w.get("usTH") or [])), "oppTH": dict(Counter(w.get("oppTH") or [])),
           "usAvg": uA, "usD": uD, "usN": uN, "oppAvg": oA, "oppD": oD, "oppN": oN, "lineup": lineup}

# ---------- regular war scouting (opponent record + recent form) ----------
def soft(path):
    try: return get(path, ok404=True)
    except SystemExit: return None
scout = None
if live and live["kind"] == "regular":
    ot = live["opp"]["tag"]
    oc = soft(f"/clans/{q(ot)}") or {}
    owl = ((soft(f"/clans/{q(ot)}/warlog?limit=10") or {}).get("items", [])) if oc.get("isWarLogPublic") else []
    orows = [it for it in owl if (it.get("opponent") or {}).get("name") and it.get("teamSize")]
    recent = [r for r in log[:10] if r[2]]
    scout = {"opp": live["opp"]["n"], "size": live["size"], "level": oc.get("clanLevel"), "w": oc.get("warWins"), "l": oc.get("warLosses"),
             "t": oc.get("warTies"), "streak": oc.get("warWinStreak"), "league": (oc.get("warLeague") or {}).get("name"),
             "public": bool(oc.get("isWarLogPublic")), "members": oc.get("members"),
             "oppN": len(orows), "oppWins": sum(1 for it in orows if it.get("result") == "win"),
             "oppAvg": round(sum(it["clan"]["stars"] / it["teamSize"] for it in orows) / len(orows) * live["size"], 1) if orows else None,
             "oppD": round(sum(it["clan"].get("destructionPercentage", 0) for it in orows) / len(orows), 1) if orows else None,
             "usN": len(recent), "usWins": sum(1 for r in recent if r[1] == "win"),
             "usAvg": round(sum(r[3] / r[2] for r in recent) / len(recent) * live["size"], 1) if recent else None,
             "usD": round(sum(r[5] for r in recent) / len(recent), 1) if recent else None,
             "usTH": dict(Counter(live.get("usTH") or [])), "oppTH": dict(Counter(live.get("oppTH") or []))}

# ---------- CWL season ledger (Last CWL tile: league, place, stars, promoted) ----------
seasons = load("cwl_seasons.json", {})
if cwl and cwl.get("table"):
    tbl = cwl["table"]; n_cl = len(tbl)
    place = next((i + 1 for i, r in enumerate(tbl) if r.get("me")), None)
    rec = seasons.get(cwl["season"], {})
    if not rec.get("league"): rec["league"] = (clan.get("warLeague") or {}).get("name")   # frozen at first sight
    pro, dem = int(cfg.get("cwlPromote", 2)), int(cfg.get("cwlDemote", 2))
    rec.update({"season": cwl["season"], "place": place, "of": n_cl, "stars": tbl[place - 1]["s"] if place else None,
                "done": cwl.get("roundsDone", 0), "final": cwl.get("roundsDone", 0) >= 7 or cwl.get("state") in ("ended", "warEnded"),
                "result": "promoted" if place and place <= pro else ("demoted" if place and place > n_cl - dem else "stayed")})
    seasons[cwl["season"]] = rec
    json.dump(seasons, open(P("cwl_seasons.json"), "w", encoding="utf-8"), ensure_ascii=False)
cwlLast = seasons[max(seasons)] if seasons else None

first = min((w["end"] for w in W.values() if w["state"] != "preparation"), default="")
out = {"clan": {"name": clan.get("name"), "tag": TAG, "level": clan.get("clanLevel"), "members": clan.get("members"),
                "w": clan.get("warWins"), "l": clan.get("warLosses"), "t": clan.get("warTies"), "streak": clan.get("warWinStreak"),
                "league": (clan.get("warLeague") or {}).get("name")},
       "log": log, "logCols": ["date", "res", "size", "s", "os", "d", "od", "opp", "apm"],
       "players": players, "pCols": PCOLS, "historySince": (ts(first).isoformat() if ts(first) else ""),
       "warsTracked": sum(1 for w in W.values() if w["state"] != "preparation"),
       "current": curw, "cwl": cwl, "mvps": mvps, "cwlBoard": cwlBoard, "curTop": curTop, "next": nxt, "scout": scout, "warLogPublic": LOG_PUBLIC, "cwlLast": cwlLast, "drill": drill, "don": don, "regularTracked": sum(1 for w in W.values() if w["kind"] == "regular" and w["state"] == "warEnded"),
       "updated": LOCAL_STAMP(),
       "updatedISO": NOW.isoformat(timespec="seconds")}
json.dump(out, open(P("stats_latest.json"), "w", encoding="utf-8"), ensure_ascii=False)
compact = json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
print("SHA256", hashlib.sha256(compact.encode("utf-8")).hexdigest())
print("OK", out["updated"], "| wars tracked:", out["warsTracked"], "| log:", len(log), "| players:", len(players), "| bytes:", len(compact.encode()))

# ---------- Discord ----------
if "--no-discord" not in sys.argv:
    import discord_notify
    discord_notify.run(cfg, out, W, P)
