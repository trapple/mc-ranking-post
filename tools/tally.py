"""投票ポストを公式ルールで集計する。新しいポストだけ fxtwitter で取得し、
集計に必要な最小限（本文・アカウント名なし）を data/votes.json にためる。
usage: [MODE=strict|lenient] python3 tools/tally.py
       python3 tools/tally.py --active   # 投票期間（締切+6時間まで）なら true を出力"""
import collections, functools, hashlib, hmac, itertools, json, os, re, secrets, sys, time, unicodedata, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "data/config.json").read_text())
START = datetime.fromisoformat(CFG["theme_start_jst"])
DEADLINE = datetime.fromisoformat(CFG["deadline_jst"])
STORE = ROOT / "data/votes.json"
MODE = os.environ.get("MODE", "strict")
YT_RE = re.compile(r"(?:youtu\.be/|[?&]v=|shorts/)([\w-]{11})")


@functools.cache
def salt():
    s = os.environ.get("MC_SALT")
    if s: return s.encode()
    f = Path.home() / ".config/mc-ranking/salt"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_hex(32)); f.chmod(0o600)
    return f.read_text().strip().encode()


def user_hash(name):
    return hmac.new(salt(), name.lower().encode(), hashlib.sha256).hexdigest()[:16]


def load_store():
    return json.loads(STORE.read_text()) if STORE.exists() else {}


def save_store(store):
    STORE.write_text(json.dumps(store, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace('},"', '},\n"') + "\n")


def load_ids():
    """data/urls/*.txt に集めたポストID"""
    ids = set()
    for f in sorted((ROOT / "data/urls").glob("*.txt")):
        ids |= set(re.findall(r"status/(\d+)", f.read_text()))
    return ids


def redact(x):
    """公開リポジトリに残すので、カッコ内のメンションは伏せる"""
    return re.sub(r"@\w+", "@***", x.strip())


def record(text, user, ts):
    """本文から集計に必要な情報だけを取り出す"""
    tags = {t.lower() for t in re.findall(r"#([^\s#]+)", text)}
    return {"code": 200, "ts": ts, "u": user_hash(user),
            "tags": "vtuber楽曲ランキング" in tags and "ミューコミvr" in tags,
            "a": [redact(x) for x in re.findall(r"\(([^()]*)\)", text)],
            "s": [redact(x) for x in re.findall(r"『([^『』]*)』", text)],
            "yt": sorted(set(YT_RE.findall(text)))}


def fetch(pid):
    """集計用レコード / {"code": 404} / 一時エラー時は {"code": None}（次回再取得）"""
    for _ in range(3):
        try:
            req = urllib.request.Request(f"https://api.fxtwitter.com/i/status/{pid}", headers={"User-Agent": "mc-ranking-tally"})
            t = json.load(urllib.request.urlopen(req, timeout=15)).get("tweet") or {}
            if t.get("created_timestamp"):
                return record(t.get("text") or "", (t.get("author") or {}).get("screen_name") or "", t["created_timestamp"])
            return {"code": 404}
        except urllib.error.HTTPError as e:
            if e.code == 404: return {"code": 404}
        except Exception:
            pass
        time.sleep(2)
    return {"code": None}


def update_store(store, ids):
    new = sorted(i for i in ids | set(store) if store.get(i, {}).get("code") is None)  # 未取得 + 前回一時エラー
    print(f"fetching {len(new)} new post(s)", file=sys.stderr)
    for n, pid in enumerate(new, 1):
        store[pid] = fetch(pid)
        if n % 200 == 0:
            save_store(store); print(f"  {n}/{len(new)}", file=sys.stderr)
        time.sleep(0.3)
    save_store(store)


def parse(r, strict):
    """有効なら (artist, song)、無効なら理由文字列を返す"""
    if r.get("code") != 200: return "取得不可(削除/非公開)"
    dt = datetime.fromtimestamp(r["ts"], JST)
    if not (START <= dt <= DEADLINE): return "期間外"
    if not r["tags"]: return "ハッシュタグ不足"
    if not r["a"] or not r["s"]: return "()/『』なし(全角カッコ等)"
    if strict and (len(set(r["a"])) > 1 or len(set(r["s"])) > 1): return "()/『』が複数"
    return r["a"][0], r["s"][0]


def norm(s): return re.sub(r"[\s　・、。！!？?：:/／\-－~〜「」]", "", unicodedata.normalize("NFKC", s)).lower()


def counted_votes(store, strict):
    valid, invalid = [], collections.Counter()
    for pid, r in store.items():
        x = parse(r, strict)
        if isinstance(x, str): invalid[x] += 1; continue
        valid.append({"id": pid, "user": r["u"], "dt": datetime.fromtimestamp(r["ts"], JST), "artist": x[0], "song": x[1]})
    valid.sort(key=lambda v: (v["dt"], v["id"]))
    seen, out = set(), []
    for v in valid:
        k = (v["user"], v["dt"].date())  # 1人1日1回（JST日付）
        if k in seen: invalid["同日2回目以降"] += 1; continue
        seen.add(k); out.append(v)
    return out, invalid


def variant_candidates(tally):
    """表記ゆれ候補: 曲名が同じでアーティスト名が包含関係、またはアーティスト名が同じで曲名が包含関係"""
    items = [((a, s), c, norm(a), norm(s)) for (a, s), c in tally.most_common()]
    by_song, by_artist = collections.defaultdict(list), collections.defaultdict(list)
    for it in items:
        by_song[it[3]].append(it); by_artist[it[2]].append(it)
    pairs = set()
    for group in by_song.values():
        pairs |= {(x[0], y[0]) for x, y in itertools.combinations(group, 2) if x[2] in y[2] or y[2] in x[2]}
    for group in by_artist.values():
        pairs |= {(x[0], y[0]) for x, y in itertools.combinations(group, 2) if x[3] in y[3] or y[3] in x[3]}
    return [f"({a1})『{s1}』{tally[(a1, s1)]}  <->  ({a2})『{s2}』{tally[(a2, s2)]}"
            for (a1, s1), (a2, s2) in sorted(pairs, key=lambda p: (-tally[p[0]], -tally[p[1]]))]


def active(now=None):
    return (now or datetime.now(JST)) <= DEADLINE + timedelta(hours=6)


def main():
    if "--active" in sys.argv:
        print("true" if active() else "false"); return
    store = load_store()
    update_store(store, load_ids())
    votes, invalid = counted_votes(store, MODE == "strict")
    tally = collections.Counter((v["artist"], v["song"]) for v in votes)
    lines = [f"mode={MODE} posts={len(store)} counted={len(votes)} invalid={dict(invalid)}"]
    if votes: lines.append(f"range: {votes[0]['dt']:%m/%d %H:%M} - {votes[-1]['dt']:%m/%d %H:%M} JST")
    rank, prev = 0, None
    for i, ((a, s), n) in enumerate(tally.most_common(), 1):
        if n != prev: rank, prev = i, n
        lines.append(f"{rank}\t{n}\t({a})\t『{s}』")
    lines.append("\n## 表記ゆれ候補")
    lines += variant_candidates(tally)
    out = "\n".join(lines)
    print(out)
    if not os.environ.get("CI"):  # 履歴はローカルのみ（CI では捨てられる）
        d = ROOT / "data/rankings"; d.mkdir(exist_ok=True)
        (d / f"{datetime.now(JST):%Y%m%d-%H%M}_{MODE}.txt").write_text(out + "\n")


if __name__ == "__main__":
    main()
