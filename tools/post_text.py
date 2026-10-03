"""今日の暫定TOP5ポスト文（X用）を作る。tally.py と同じルール（厳密モード）で数える。
usage: python3 tools/post_text.py [--copy]"""
import collections, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tally  # noqa: E402

MEDALS = ["🥇", "🥈", "🥉", "4位", "5位"]


def comment(top):
    """上位の票差からひとことを作る"""
    (a1, s1), n1 = top[0]
    lead = n1 - top[1][1]
    gaps = [(top[i][1] - top[i + 1][1], i) for i in range(1, len(top) - 1)]
    gap, i = min(gaps)
    head = f"{s1}が{lead}票差で首位をキープ" if lead >= 30 else f"首位{s1}と2位は{lead}票差"
    tail = f"{i + 1}位と{i + 2}位は{gap}票差の接戦🔥" if gap <= 15 else "上位の差がじわじわ開いています"
    return f"{head}、{tail}"


def build():
    votes, _ = tally.counted_votes(tally.load_store(), strict=True)
    top = collections.Counter((v["artist"], v["song"]) for v in votes).most_common(5)
    cfg, last = tally.CFG, votes[-1]["dt"]
    site = cfg["site_url"].rstrip("/") + "/"
    lines = [f"VTuber楽曲ランキング「{cfg['theme']}」暫定TOP5",
             f"{last:%-m/%-d %H:%M}時点・公開ポストのみの勝手に集計です", ""]
    safe = lambda x: x.translate(str.maketrans("()", "（）"))  # 曲名内の半角カッコは全角に
    lines += [f"{m} {safe(a)}「{safe(s)}」{n}票" for m, ((a, s), n) in zip(MEDALS, top)]
    lines += ["", comment(top), "DM票は含まれないので、実際の順位は変わる可能性があります", "",
              "📈 票数の推移はこちら", f"{site}trend", "",
              f"投票は{tally.DEADLINE:%-m/%-d %H:%M}まで🗳️", "投票文かんたん作成👇", site, "",
              "投票曲まとめプレイリスト🎧", cfg["playlist_url"]]
    text = "\n".join(lines)
    # 投票として誤集計されないよう、半角カッコと二重カギカッコを含めない
    assert not any(c in text for c in "()『』"), "ポスト文に ( ) 『 』 が含まれています"
    return text, len(votes)


def main():
    text, n = build()
    print(text)
    print(f"\n(有効票 {n})", file=sys.stderr)
    if "--copy" in sys.argv:
        subprocess.run(["pbcopy"], input=text, text=True, timeout=10, check=True)
        print("(クリップボードにコピーしました)", file=sys.stderr)


if __name__ == "__main__":
    main()
