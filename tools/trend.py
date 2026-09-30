"""暫定票数の推移ページ（HTML）を生成する。tally.py と同じルール（厳密モード）で数える。
usage: python3 tools/trend.py [--top N]  -> data/trend.html"""
import collections, json, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tally  # noqa: E402

ROOT = tally.ROOT
TOP = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 8
TABLE_ROWS = 20


def main():
    cache = json.loads(tally.CACHE.read_text())
    ids = [i for i in tally.load_ids() if i in cache]
    votes, _ = tally.counted_votes(cache, ids, strict=True)
    if not votes: sys.exit("no votes")
    total = collections.Counter((v["artist"], v["song"]) for v in votes)
    ranked = [k for k, _ in total.most_common()]
    top = ranked[:TOP]

    # 1時間ごとの累計（JST）
    start = tally.START.replace(minute=0, second=0, microsecond=0)
    last = votes[-1]["dt"]
    hours = []
    h = start
    while h <= last:
        hours.append(h); h += timedelta(hours=1)
    per_hour = {k: [0] * len(hours) for k in top}
    for v in votes:
        k = (v["artist"], v["song"])
        if k in per_hour:
            per_hour[k][int((v["dt"] - start).total_seconds() // 3600)] += 1
    series = []
    for k in top:
        acc, cum = 0, []
        for n in per_hour[k]:
            acc += n; cum.append(acc)
        series.append({"artist": k[0], "song": k[1], "cum": cum})

    # 日別（JST）
    days = sorted({v["dt"].date() for v in votes})
    daily = collections.defaultdict(collections.Counter)
    for v in votes: daily[(v["artist"], v["song"])][v["dt"].date()] += 1
    table = [{"rank": i + 1, "artist": a, "song": s, "total": total[(a, s)],
              "days": [daily[(a, s)][d] for d in days]} for i, (a, s) in enumerate(ranked[:TABLE_ROWS])]

    data = {
        "hours": [x.strftime("%Y-%m-%dT%H:00") for x in hours],
        "series": series,
        "days": [f"{d.month}/{d.day}" for d in days],
        "table": table,
        "asOf": last.strftime("%-m/%-d %H:%M"),
        "counted": len(votes),
        "songs": len(total),
        "theme": tally.CFG["theme"],
        "deadline": datetime.fromisoformat(tally.CFG["deadline_jst"]).strftime("%-m/%-d %H:%M"),
    }
    tpl = (Path(__file__).parent / "trend_template.html").read_text()
    page = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    out = ROOT / "data/trend.html"  # Artifact 用（スケルトンは公開時に付く）
    out.write_text(page)
    site = tally.CFG["site_url"].rstrip("/")
    head = ('<!doctype html>\n<html lang="ja">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'<meta name="description" content="VTuber楽曲ランキング「{data['theme']}」の公開ポスト票を公式ルールで数えた非公式集計。上位曲の票数推移と日別票数。">\n'
            f'<meta property="og:title" content="「{data['theme']}」票数の推移（非公式）">\n'
            f'<meta property="og:image" content="{site}/rules.jpg">\n<meta name="twitter:card" content="summary_large_image">\n'
            '<style>body{margin:0}</style>\n')
    back = f'<p style="text-align:center;font-size:13px;padding-bottom:32px"><a href="{site}/" style="color:var(--accent)">投票文をかんたん作成 →</a></p>\n'
    (ROOT / "public/trend.html").write_text(head + page + back + "</html>\n")
    print(f"wrote {out} and public/trend.html (as of {data['asOf']} JST, {len(votes)} votes, top {len(top)})")


if __name__ == "__main__":
    main()
