"""Pull the current Clan War League season from the official Clash of Clans API
and write cwl_latest.json in the shape the CWL tracker page reads.
Season-aware: works every month; between seasons it keeps last season's results and marks offSeason.
Usage: python3 fetch_cwl.py   (reads config.json next to this file)"""
import json, sys, os, urllib.request, urllib.parse, urllib.error, datetime, hashlib, difflib, unicodedata

def LOCAL_STAMP():
    n = datetime.datetime.now()
    return f"{n:%b} {n.day}, {n.hour % 12 or 12}:{n:%M} {n:%p} CT"

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.clashofclans.com/v1"
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
KEY, TAG = cfg["apiKey"].strip(), cfg["clanTag"].strip().upper()
if "PASTE" in KEY or "PASTE" in TAG:
    sys.exit("ERROR: fill in clanTag and apiKey in config.json first")
if not TAG.startswith("#"): TAG = "#" + TAG
CT = datetime.timezone(datetime.timedelta(hours=-6))
UTC = datetime.timezone.utc

def get(path, ok404=False):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if ok404 and e.code == 404: return None
        sys.exit(f"ERROR {e.code} on {path}: {body}")

def stamp():
    return {"updated": LOCAL_STAMP(),
            "updatedISO": datetime.datetime.now(UTC).isoformat(timespec="seconds")}

def emit(doc):
    json.dump(doc, open(os.path.join(HERE, "cwl_latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    compact = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print("SHA256", hashlib.sha256(compact.encode("utf-8")).hexdigest())

q = urllib.parse.quote
clan_info = get(f"/clans/{q(TAG)}")
LEAGUE = (clan_info.get("warLeague") or {}).get("name") or cfg.get("league", "")
group = get(f"/clans/{q(TAG)}/currentwar/leaguegroup", ok404=True)

if not group or not group.get("rounds") or group.get("state") == "notInWar":
    # Between seasons: keep last season's final numbers, mark off-season, no error.
    try: prev = json.load(open(os.path.join(HERE, "cwl_latest.json"), encoding="utf-8"))
    except Exception: prev = {"me": clan_info.get("name"), "clans": [], "rounds": [], "dest": {}, "totalRounds": 7, "roster": 30}
    prev.update({"offSeason": True, "myWar": None, "league": LEAGUE, **stamp()})
    emit(prev)
    print("OK off-season (no active CWL group) | last season:", prev.get("season", "none"))
    sys.exit(0)

clans = {c["tag"]: c["name"] for c in group["clans"]}
me = clans.get(TAG)
if not me: sys.exit(f"ERROR: clan {TAG} not found in league group")

def norm(n): return "".join(ch for ch in unicodedata.normalize("NFKC", n).casefold() if ch.isalnum())
def match(name):
    """Map a hand-typed schedule name to the exact API clan name."""
    byn = {norm(v): v for v in clans.values()}
    if norm(name) in byn: return byn[norm(name)]
    best = difflib.get_close_matches(norm(name), list(byn), n=1, cutoff=0.6)
    if best: return byn[best[0]]
    sys.exit(f"ERROR: schedule name {name!r} matches no clan in the group: {list(clans.values())}")

STATUS = {"preparation": "upcoming", "inWar": "live", "warEnded": "final"}
try: _sf = json.load(open(os.path.join(HERE, "schedule.json"), encoding="utf-8"))
except Exception: _sf = {}
sched = _sf.get("rounds", {}) if _sf.get("season") == group.get("season") else {}   # never reuse last month's pairings

rounds, dest, teamsize = [], {n: 0.0 for n in clans.values()}, None
my_war = None
for i, rnd in enumerate(group.get("rounds", []), start=1):
    wars = []
    for wt in rnd.get("warTags", []):
        if not wt or wt == "#0": continue
        w = get(f"/clanwarleagues/wars/{q(wt)}")
        if w.get("state") not in STATUS: continue
        a, b = w["clan"], w["opponent"]
        teamsize = w.get("teamSize") or teamsize
        st = STATUS[w["state"]]
        winner = ""
        if st == "final":
            if a["stars"] != b["stars"]: winner = a["name"] if a["stars"] > b["stars"] else b["name"]
            elif a["destructionPercentage"] != b["destructionPercentage"]:
                winner = a["name"] if a["destructionPercentage"] > b["destructionPercentage"] else b["name"]
        if st != "upcoming":
            ts = w.get("teamSize", 0)
            dest[a["name"]] += a["destructionPercentage"] * ts
            dest[b["name"]] += b["destructionPercentage"] * ts
        if st == "live" and TAG in (a.get("tag"), b.get("tag")):
            mine, opp = (a, b) if a.get("tag") == TAG else (b, a)
            mem = sorted(mine.get("members", []), key=lambda m: m.get("mapPosition", 99))
            et = w.get("endTime", "")
            try: et_iso = datetime.datetime.strptime(et, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=UTC).isoformat()
            except ValueError: et_iso = ""
            my_war = {"round": i, "opponent": opp["name"], "endTime": et_iso, "roster": len(mem),
                      "done": sum(1 for m in mem if m.get("attacks")),
                      "pending": [{"n": m["name"], "th": m.get("townhallLevel"), "pos": m.get("mapPosition")} for m in mem if not m.get("attacks")]}
        wars.append(dict(a=a["name"], b=b["name"], aStars=a["stars"], bStars=b["stars"],
                         aAtk=a["attacks"], bAtk=b["attacks"], status=st, winner=winner,
                         aDestPct=round(a["destructionPercentage"], 2), bDestPct=round(b["destructionPercentage"], 2)))
    if not wars and str(i) in sched:   # round not posted by the API yet: keep the known schedule (same season only)
        wars = [dict(a=match(x), b=match(y), aStars=0, bStars=0, aAtk=0, bAtk=0, status="upcoming", winner="") for x, y in sched[str(i)]]
    rounds.append({"n": i, "wars": wars})

out = {"me": me, "league": LEAGUE, "offSeason": False, "season": group.get("season", ""),
       "groupState": group.get("state", ""), "roster": teamsize or 30, "totalRounds": len(rounds) or 7,
       "promote": int(cfg.get("cwlPromote", 2)), "demote": int(cfg.get("cwlDemote", 2)), "clans": list(clans.values()), "myWar": my_war,
       "dest": {k: round(v) for k, v in dest.items()}, "rounds": rounds, **stamp(), "source": "api"}
emit(out)

done_all = bool(rounds) and all(r["wars"] for r in rounds) and all(w["status"] == "final" for r in rounds for w in r["wars"])
if group.get("state") == "ended" or done_all:
    sf = os.path.join(HERE, "season_state.json")
    try: ss = json.load(open(sf, encoding="utf-8"))
    except Exception: ss = {}
    if ss.get("endNotified") != out["season"]:
        ss["endNotified"] = out["season"]; json.dump(ss, open(sf, "w", encoding="utf-8"))
        print("SEASON_END_NEW", out["season"])
print("OK", out["updated"], "| clans:", len(clans), "| rounds:", len(rounds),
      "| live/final wars:", sum(1 for r in rounds for w in r["wars"] if w["status"] != "upcoming"))
