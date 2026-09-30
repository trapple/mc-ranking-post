"""投票ポストを公式ルールで集計する。新しいポストだけ fxtwitter で取得して data/posts.json にためる。
usage: [MODE=strict|lenient] python3 tools/tally.py"""
import collections, itertools, json, os, re, sys, time, unicodedata, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "data/config.json").read_text())
START = datetime.fromisoformat(CFG["theme_start_jst"])
DEADLINE = datetime.fromisoformat(CFG["deadline_jst"])
CACHE = ROOT / "data/posts.json"
MODE = os.environ.get("MODE", "strict")

def load_ids():
    ids = {}
    for f in sorted((ROOT / "data/urls").glob("*.txt")):
        for m in re.finditer(r"(?:x|twitter)\.com/(\w+)/status/(\d+)", f.read_text()):
            ids[m.group(2)] = m.group(1)
    return ids

def fetch(pid):
    for _ in range(3):
        try:
            req = urllib.request.Request(f"https://api.fxtwitter.com/i/status/{pid}", headers={"User-Agent": "mc-ranking-tally"})
            d = json.load(urllib.request.urlopen(req, timeout=15))
            t = d.get("tweet") or {}
            return {"user": (t.get("author") or {}).get("screen_name"), "ts": t.get("created_timestamp"),
                    "text": t.get("text") or "", "code": d.get("code")}
        except urllib.error.HTTPError as e:
            if e.code == 404: return {"code": 404}
        except Exception:
            pass
        time.sleep(2)
    return {"code": "ERR"}  # 次回再取得される

def parse(p, strict):
    """有効なら (artist, song)、無効なら理由文字列を返す"""
    if p.get("code") != 200 or not p.get("ts"): return "取得不可(削除/非公開)"
    dt = datetime.fromtimestamp(p["ts"], JST)
    if not (START <= dt <= DEADLINE): return "期間外"
    tx = p["text"]
    tags = {t.lower() for t in re.findall(r"#([^\s#]+)", tx)}
    if "vtuber楽曲ランキング" not in tags or "ミューコミvr" not in tags: return "ハッシュタグ不足"
    arts, songs = re.findall(r"\(([^()]*)\)", tx), re.findall(r"『([^『』]*)』", tx)
    if not arts or not songs: return "()/『』なし(全角カッコ等)"
    if strict and (len(set(arts)) > 1 or len(set(songs)) > 1): return "()/『』が複数"
    return arts[0].strip(), songs[0].strip()

def norm(s): return re.sub(r"[\s　・、。！!？?：:/／\-－~〜「」]", "", unicodedata.normalize("NFKC", s)).lower()

def counted_votes(cache, ids, strict):
    valid, invalid = [], collections.Counter()
    for pid in ids:
        r = parse(cache[pid], strict)
        if isinstance(r, str): invalid[r] += 1; continue
        p = cache[pid]
        valid.append({"id": pid, "user": p["user"].lower(), "dt": datetime.fromtimestamp(p["ts"], JST), "artist": r[0], "song": r[1]})
    valid.sort(key=lambda v: v["dt"])
    seen, out = set(), []
    for v in valid:
        k = (v["user"], v["dt"].date())  # 1人1日1回（JST日付）
        if k in seen: invalid["同日2回目以降"] += 1; continue
        seen.add(k); out.append(v)
    return out, invalid

def main():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    ids = load_ids()
    new = [p for p in ids if p not in cache or cache[p].get("code") == "ERR"]
    print(f"fetching {len(new)} new post(s)", file=sys.stderr)
    for n, pid in enumerate(new, 1):
        cache[pid] = fetch(pid)
        if n % 50 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False)); print(f"  {n}/{len(new)}", file=sys.stderr)
        time.sleep(0.3)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False))

    votes, invalid = counted_votes(cache, ids, MODE == "strict")
    tally = collections.Counter((v["artist"], v["song"]) for v in votes)
    lines = [f"mode={MODE} posts={len(ids)} counted={len(votes)} invalid={dict(invalid)}"]
    if votes: lines.append(f"range: {votes[0]['dt']:%m/%d %H:%M} - {votes[-1]['dt']:%m/%d %H:%M} JST")
    rank, prev = 0, None
    for i, ((a, s), n) in enumerate(tally.most_common(), 1):
        if n != prev: rank, prev = i, n
        lines.append(f"{rank}\t{n}\t({a})\t『{s}』")
    lines.append("\n## 表記ゆれ候補")
    for ((a1, s1), c1), ((a2, s2), c2) in itertools.combinations(tally.most_common(), 2):
        na1, na2, ns1, ns2 = norm(a1), norm(a2), norm(s1), norm(s2)
        if (ns1 == ns2 and (na1 in na2 or na2 in na1)) or (na1 == na2 and (ns1 in ns2 or ns2 in ns1)):
            lines.append(f"({a1})『{s1}』{c1}  <->  ({a2})『{s2}』{c2}")
    out = "\n".join(lines)
    print(out)
    d = ROOT / "data/rankings"; d.mkdir(exist_ok=True)
    (d / f"{datetime.now(JST):%Y%m%d-%H%M}_{MODE}.txt").write_text(out + "\n")

if __name__ == "__main__":
    main()
