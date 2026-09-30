"""Yahoo!リアルタイム検索から投票ポストURLを集める（新しい順に40件ずつさかのぼる）。
usage: python3 tools/collect_yahoo.py [--full] [--max-pages N]
  既定: 既知のポストだけのページが2回続いたら停止（差分取得）
  --full: テーマ告知時刻までさかのぼる"""
import json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "data/config.json").read_text())
START = datetime.fromisoformat(CFG["theme_start_jst"]).timestamp()
OUT = ROOT / "data/urls/yahoo.txt"
QUERY = "#VTuber楽曲ランキング #ミューコミVR"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
INTERVAL = 2.0

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=20).read().decode()

def first_page():
    h = get("https://search.yahoo.co.jp/realtime/search?p=" + urllib.parse.quote(QUERY))
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    return json.loads(m.group(1))["props"]["pageProps"]["pageData"]["timeline"]

def next_page(oldest_id):
    # start を併用するとオフセットが二重にかかりページ間が飛ぶので oldestTweetId だけ渡す
    q = urllib.parse.urlencode({"p": QUERY, "results": 40, "oldestTweetId": oldest_id})
    return json.loads(get("https://search.yahoo.co.jp/realtime/api/v1/pagination?" + q))["timeline"]

def main():
    full = "--full" in sys.argv
    max_pages = int(sys.argv[sys.argv.index("--max-pages") + 1]) if "--max-pages" in sys.argv else 200
    known = set(OUT.read_text().split()) if OUT.exists() else set()
    found, known_streak = set(), 0
    tl = first_page()
    print(f"yahoo: totalResultsAvailable={tl['head'].get('totalResultsAvailable')}")
    for page in range(1, max_pages + 1):
        es = tl.get("entry") or []
        if not es: print("no more entries"); break
        urls = {f"https://x.com/{e['screenName']}/status/{e['id']}" for e in es if e.get("id") and e.get("screenName")}
        new = urls - known - found
        found |= urls
        oldest = min(es, key=lambda e: e["createdAt"])
        print(f"page {page}: {len(es)} posts, {len(new)} new, oldest {datetime.fromtimestamp(oldest['createdAt'], JST):%m/%d %H:%M} JST", flush=True)
        if oldest["createdAt"] < START: print("reached theme start"); break
        known_streak = known_streak + 1 if not new else 0
        if not full and known_streak >= 2: print("caught up with known posts"); break
        time.sleep(INTERVAL)
        try:
            tl = next_page(oldest["id"])
        except Exception as e:
            print(f"stop: {e}"); break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(sorted(known | found)) + "\n")
    print(f"yahoo.txt: +{len(found - known)} (total {len(known | found)})")

if __name__ == "__main__":
    main()
