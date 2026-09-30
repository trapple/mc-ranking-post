# /// script
# requires-python = ">=3.12"
# dependencies = ["google-auth-oauthlib", "google-api-python-client"]
# ///
"""投票曲を YouTube プレイリストに反映する。
usage: uv run tools/playlist.py plan | accept-auto | set KEY video ID | set KEY not_found | set KEY skip REASON
                               | set KEY alias OTHER_KEY | sync [--limit N] | move VIDEO_ID POS | list"""
import collections, glob, json, os, re, socket, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tally  # noqa: E402

socket.setdefaulttimeout(30)
ROOT = tally.ROOT
CFG = tally.CFG
PL = CFG["playlist_id"]
SONGS = ROOT / "data/songs.json"
PLAN = ROOT / "data/plan.json"
TOKEN = Path.home() / ".config/mc-ranking/yt-token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube"]

def load(p, d): return json.loads(p.read_text()) if p.exists() else d
def save(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n")
def key(a, s): return f"{tally.norm(a)}|{tally.norm(s)}"

def yt():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if c and c.expired and c.refresh_token:
        try: c.refresh(Request())
        except Exception: c = None
    if not c or not c.valid:
        secret = os.environ.get("YT_CLIENT_SECRET") or sorted(glob.glob(os.path.expanduser("~/Downloads/client_secret_*.json")))[-1]
        c = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0, open_browser=True, timeout_seconds=300)
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(c.to_json()); TOKEN.chmod(0o600)
    return build("youtube", "v3", credentials=c, cache_discovery=False)

def playlist_items(y):
    out, tok = [], None
    while True:
        r = y.playlistItems().list(part="snippet", playlistId=PL, maxResults=50, pageToken=tok).execute()
        out += [{"item": i["id"], "vid": i["snippet"]["resourceId"]["videoId"], "title": i["snippet"]["title"],
                 "channel": i["snippet"].get("videoOwnerChannelTitle", "")} for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok: return out

def oembed(v):
    try:
        u = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={v}")
        d = json.load(urllib.request.urlopen(u, timeout=10))
        return f"{d['title']} | {d['author_name']}"
    except Exception:
        return None

def search(q):
    try:
        r = subprocess.run(["yt-dlp", "--socket-timeout", "20", "--flat-playlist", "--print",
                            "%(id)s | %(title)s | %(channel)s", f"ytsearch3:{q}"], capture_output=True, text=True, timeout=90)
        return [l for l in r.stdout.splitlines() if l.strip()]
    except subprocess.TimeoutExpired:
        return []

def songs_from_posts():
    """寛容モードの有効票から曲ごとに (表示名, 票数, ポスト内のYouTube ID) を集める"""
    cache, ids = load(tally.CACHE, {}), tally.load_ids()
    votes, _ = tally.counted_votes(cache, [i for i in ids if i in cache], strict=False)
    g = collections.defaultdict(lambda: {"names": collections.Counter(), "votes": 0, "vids": collections.Counter()})
    for v in votes:
        e = g[key(v["artist"], v["song"])]
        e["names"][(v["artist"], v["song"])] += 1; e["votes"] += 1
        for vid in re.findall(r"(?:youtu\.be/|[?&]v=|shorts/)([\w-]{11})", cache[v["id"]]["text"]): e["vids"][vid] += 1
    return g

def cmd_plan():
    songs, g = load(SONGS, {}), songs_from_posts()
    items = playlist_items(yt())
    plan = {}
    for k, e in sorted(g.items(), key=lambda kv: -kv[1]["votes"]):
        if k in songs: continue
        a, s = e["names"].most_common(1)[0][0]
        ns = tally.norm(s)
        hit = [i for i in items if ns and ns in tally.norm(i["title"])
               and (tally.norm(a) in tally.norm(i["title"] + i["channel"]) or len(ns) >= 4)]
        if hit:  # 既にプレイリストにある（手動追加分など）
            songs[k] = {"artist": a, "song": s, "status": "added", "video_id": hit[0]["vid"]}
            print(f"[matched] ({a})『{s}』 {e['votes']}票 -> {hit[0]['vid']} {hit[0]['title']}")
            continue
        auto = next((f"{v} | {t}" for v, _ in e["vids"].most_common(3) if (t := oembed(v)) and ns in tally.norm(t)), None)
        plan[k] = {"artist": a, "song": s, "votes": e["votes"], "auto": auto, "search": [] if auto else search(f"{a} {s}")}
    save(SONGS, songs); save(PLAN, plan)
    for k, p in plan.items():
        print(f"\n[{k}] ({p['artist']})『{p['song']}』 {p['votes']}票")
        print(f"  auto: {p['auto']}" if p["auto"] else "\n".join(f"  ? {l}" for l in p["search"]) or "  (検索結果なし)")
    print(f"\n{len(plan)} song(s) need decision; playlist has {len(items)} item(s)")

def cmd_accept_auto():
    songs, plan = load(SONGS, {}), load(PLAN, {})
    for k, p in plan.items():
        if p.get("auto") and k not in songs:
            songs[k] = {"artist": p["artist"], "song": p["song"], "status": "video", "video_id": p["auto"].split(" | ")[0]}
            print("accept", k)
    save(SONGS, songs)

def cmd_set(k, status, *rest):
    songs, plan = load(SONGS, {}), load(PLAN, {})
    base = songs.get(k) or {x: plan.get(k, {}).get(x) for x in ("artist", "song")}
    e = {"artist": base.get("artist"), "song": base.get("song"), "status": status}
    if status == "video": e["video_id"] = rest[0]
    elif status == "skip": e["reason"] = " ".join(rest)
    elif status == "alias": e["alias_of"] = rest[0]
    elif status != "not_found": sys.exit(f"unknown status {status}")
    songs[k] = e; save(SONGS, songs); print("set", k, e)

def cmd_sync(limit=200):
    songs, y = load(SONGS, {}), yt()
    have = {i["vid"] for i in playlist_items(y)}
    n = 0
    for k, e in songs.items():
        if e["status"] != "video": continue
        if e["video_id"] not in have:
            if n >= limit: break
            y.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": PL, "resourceId": {"kind": "youtube#video", "videoId": e["video_id"]}}}).execute()
            have.add(e["video_id"]); n += 1; print("added", e["video_id"], e["artist"], e["song"])
        e["status"] = "added"
        save(SONGS, songs)
    print(f"added {n}; playlist now {len(have)}")

def cmd_move(vid, pos):
    y = yt()
    it = next((i for i in playlist_items(y) if i["vid"] == vid), None) or sys.exit(f"not in playlist: {vid}")
    y.playlistItems().update(part="snippet", body={"id": it["item"], "snippet": {"playlistId": PL, "resourceId": {"kind": "youtube#video", "videoId": vid}, "position": int(pos)}}).execute()
    print("moved", vid, "->", pos)

def cmd_list():
    for n, i in enumerate(playlist_items(yt())): print(n, i["vid"], i["title"])

if __name__ == "__main__":
    c, args = sys.argv[1], sys.argv[2:]
    if c == "plan": cmd_plan()
    elif c == "accept-auto": cmd_accept_auto()
    elif c == "set": cmd_set(*args)
    elif c == "sync": cmd_sync(int(args[args.index("--limit") + 1]) if "--limit" in args else 200)
    elif c == "move": cmd_move(*args)
    elif c == "list": cmd_list()
    else: sys.exit(__doc__)
