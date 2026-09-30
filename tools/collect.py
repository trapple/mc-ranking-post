"""Grok で投票ポストURLを12時間区間ごとに集める。確定済み区間はスキップ。
usage: python3 tools/collect.py [--force] [--dry-run]"""
import subprocess, sys, re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tally import DEADLINE, JST, ROOT, START  # noqa: E402

URLS = ROOT / "data/urls"
URLS.mkdir(parents=True, exist_ok=True)
SPAN, SETTLE, TIMEOUT = timedelta(hours=12), timedelta(hours=6), 1200

def windows(now):
    s = START.astimezone(JST).replace(hour=0, minute=0)
    end = min(now, DEADLINE.astimezone(JST) + timedelta(minutes=1))
    while s < end:
        yield s, s + SPAN
        s += SPAN

def path_for(a, b):
    return URLS / f"{a:%Y%m%d-%H%M}_{b:%Y%m%d-%H%M}.txt"

def run(w):
    a, b = w
    path = path_for(a, b)
    prompt = (f"X検索で、ハッシュタグ #VTuber楽曲ランキング を含み「投票します」を含むポストを、日本時間 {a:%Y-%m-%d %H:%M} から "
              f"{b:%Y-%m-%d %H:%M} までの間に投稿されたものに限って、可能な限りすべて見つけて。検索は1回10件上限なので、1時間ごとなど細かく"
              "時間を区切って繰り返し検索し、取りこぼしを最小にして。リポスト（RT）は除外、引用ポストは含める。出力は見つけたポストの URL"
              "（https://x.com/ユーザー名/status/ID 形式）を1行に1つずつ、それだけを列挙。表や説明文は不要。組み込みの X 検索 (x_search) を"
              "直接使って X (Twitter) を検索して。前置きは不要")
    try:
        r = subprocess.run(["grok", "-p", prompt, "--tools", "", "--always-approve", "--max-turns", "40"],
                           capture_output=True, text=True, timeout=TIMEOUT)
        out, err, ok = r.stdout, r.stderr, r.returncode == 0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err, ok = "timeout", False
    found = set(re.findall(r"https://(?:x|twitter)\.com/\w+/status/\d+", out))
    if not ok and not found:
        # 失敗した区間はファイルを作らない（確定扱いにして再検索されなくなるのを防ぐ）
        m = re.search(r'"message":\s*"([^"\\]*)', err or out)
        return f"{path.name}: FAILED {m.group(1) if m else (err or out).strip()[-200:]}"
    old = set(path.read_text().split()) if path.exists() else set()
    path.write_text("\n".join(sorted(old | found)) + "\n")
    return f"{path.name}: +{len(found - old)} (total {len(old | found)})"

now = datetime.now(JST)
todo = [w for w in windows(now)
        if "--force" in sys.argv or w[1] + SETTLE > now
        or not path_for(*w).exists()]
print(f"{len(todo)} window(s) to search", flush=True)
if "--dry-run" in sys.argv:
    for a, b in todo: print(f"  {a:%m/%d %H:%M} - {b:%m/%d %H:%M} JST")
    sys.exit()
with ThreadPoolExecutor(6) as ex:
    for r in ex.map(run, todo): print(r, flush=True)
