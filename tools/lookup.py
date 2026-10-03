"""特定アーティスト／曲／アカウントの投票ポストを探し、集計への反映状況を出す。
usage: python3 tools/lookup.py [--artist NAME] [--song NAME] [--user SCREEN_NAME]"""
import argparse, collections, json, re, sys, time, urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tally  # noqa: E402
import collect_yahoo  # noqa: E402


def matches(r, artist, song):
    if artist and not any(tally.norm(artist) in tally.norm(x) for x in r.get("a", [])): return False
    if song and not any(tally.norm(song) in tally.norm(x) for x in r.get("s", [])): return False
    return True


def status(pid, r, counted):
    if pid in counted: return "有効"
    x = tally.parse(r, True)
    return x if isinstance(x, str) else "同日2回目以降"


def yahoo_ids(user):
    """Yahoo!リアルタイム検索でそのアカウントのポストIDを引く。
    キーワード付き検索は反映が遅れることがあるので、直近の投稿（ID指定のみ）も合わせて見る（2リクエスト）"""
    ids = []
    for i, q in enumerate([f"ID:{user}", f"ID:{user} 投票します"]):
        if i: time.sleep(collect_yahoo.INTERVAL)
        h = collect_yahoo.get("https://search.yahoo.co.jp/realtime/search?p=" + urllib.parse.quote(q))
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
        tl = json.loads(m.group(1))["props"]["pageProps"]["pageData"]["timeline"]
        ids += [e["id"] for e in tl.get("entry") or [] if e.get("id") and "投票" in e.get("displayText", "")]
    return list(dict.fromkeys(ids))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artist"); ap.add_argument("--song"); ap.add_argument("--user")
    args = ap.parse_args()
    if not (args.artist or args.song or args.user): ap.error("--artist / --song / --user のどれかを指定")

    store = tally.load_store()
    votes, _ = tally.counted_votes(store, strict=True)
    counted = {v["id"] for v in votes}
    uh = tally.user_hash(args.user.lstrip("@")) if args.user else None

    rows = [(pid, r, "") for pid, r in store.items()
            if r.get("code") == 200 and (not uh or r.get("u") == uh) and matches(r, args.artist, args.song)]
    if args.user:  # まだ集計データに無いポストを直接確認
        for pid in yahoo_ids(args.user.lstrip("@")):
            if pid in store: continue
            r = tally.fetch(pid)
            if r.get("code") == 200 and matches(r, args.artist, args.song):
                x = tally.parse(r, True)
                rows.append((pid, r, "未取込（" + ("有効な書式" if isinstance(x, tuple) else x) + "）"))

    rows.sort(key=lambda t: t[1]["ts"])
    for pid, r, note in rows:
        dt = datetime.fromtimestamp(r["ts"], tally.JST)
        print(f"{dt:%m/%d %H:%M}\t{note or status(pid, r, counted)}\t({'/'.join(r['a'])})『{'/'.join(r['s'])}』\thttps://x.com/i/status/{pid}")
    print(f"{len(rows)} post(s)")

    # 対象曲の有効票数と順位（厳密モード）
    total = collections.Counter((v["artist"], v["song"]) for v in votes)
    ranked = total.most_common()
    for (a, s), n in ranked:
        if (args.artist or args.song) and matches({"a": [a], "s": [s]}, args.artist, args.song):
            rank = 1 + sum(1 for _, m in ranked if m > n)
            print(f"有効票 {n}票・{rank}位 / {len(ranked)}曲\t({a})『{s}』")


if __name__ == "__main__":
    main()
