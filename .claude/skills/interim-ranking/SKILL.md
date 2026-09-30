---
name: interim-ranking
description: Tally the current (interim) VTuber楽曲ランキング standings from public X posts using the official voting rules, and draft an X post of the TOP5. Use when user says "暫定ランキング", "暫定ランク", "暫定TOP5", "今の順位", "集計して", or "interim-ranking".
---

# 暫定ランキング集計

公開ポスト（#VTuber楽曲ランキング）を集め、公式ルールどおりに数えて暫定順位を出す。DM票は見えないので含まない。

## データ（`data/` にためて差分だけ処理する）

| パス | 中身 |
|---|---|
| `data/config.json` | テーマ告知時刻（JST）、締切、プレイリストID |
| `data/urls/yahoo.txt` | Yahoo!リアルタイム検索で集めたポストURL（追記のみ） |
| `data/urls/<JST開始>_<JST終了>.txt` | Grok で集めたポストURL（12時間ごと）。区間の終わりから6時間以上たったものは確定扱いで再検索しない |
| `data/posts.json` | ポストID → 本文・投稿者・時刻のキャッシュ。取得済みは再取得しない |
| `data/rankings/<JST時刻>.txt` | 集計結果の履歴 |

## 手順

1. **URL収集**（主: Yahoo!リアルタイム検索、補助: Grok）
   - `python3 tools/collect_yahoo.py` を実行する。新しい順に40件ずつさかのぼり、既知のポストだけのページが続いたら止まる（差分取得）。2秒間隔
     - 初回や取りこぼしが疑われるときは `--full` でテーマ告知時刻までさかのぼる
     - Yahoo!の公式APIではない（ページ内部の仕組み）ので、必要なときだけ実行し間隔を詰めない
   - 補助として `python3 tools/collect.py`（Grok、12時間区間ごと）を Bash の `run_in_background: true` で実行してもよい。1区間最大20分
     - 確定区間はスキップされるので、2回目以降は直近の区間だけが走る
     - `FAILED` が出た区間はファイルを作らないので、次回また検索される。`402 Payment Required` / `usage balance exhausted` は Grok Build の利用枠切れ → Yahoo!分だけで進める
2. **集計**: `python3 tools/tally.py` を実行する（新しいポストだけ fxtwitter で取得。1件0.3秒）
   - 既定は厳密モード。`MODE=lenient` で「( )・『 』が複数あっても最初を採用」する寛容モード
   - 両方実行して、差（主に YouTube 共有タイトルの `(Official Music Video)` 由来）をユーザーに伝える
3. **報告**: 厳密モードの上位を表で示し、次も添える
   - 集計対象の時間範囲（JST）と件数、無効の内訳
   - 表記ゆれで票が割れている曲（出力末尾の「表記ゆれ候補」）
4. **TOP5ポスト文**: 依頼されたら作って `pbcopy` でコピーする
5. **推移ページ**: 依頼されたら `python3 tools/trend.py` で `data/trend.html` を作り直し、Artifact ツールで `url: https://claude.ai/artifact/DUqePtQD2g9RJPfxhugQf2` を指定して同じURLに再公開する（上位8曲の累計推移＋日別票数の表。厳密モード）

## ルール（`tools/tally.py` に実装済み）

- `#VTuber楽曲ランキング` と `#ミューコミVR` の両方が必要
- アーティスト名は半角 `( )`、曲名は `『 』` 内。全角（ ）は無効
- 1人1日1回（JST日付）。同日2回目以降は無効
- 表記が違えば別曲として数える（公式ルールどおり。統合はしない）

## TOP5ポスト文

冒頭の2行はこの形で固定（絵文字は付けない。時刻は集計範囲の最終ポスト時刻、JST）:

```
VTuber楽曲ランキング「歌始まり！！」暫定TOP5
9/30 20:47時点・公開ポストのみの勝手に集計です

🥇 wouca「Romantica」248票
🥈 ...
🥉 ...
4位 ...
5位 ...

<ひとこと（接戦・差など）>
DM票は含まれないので、実際の順位は変わる可能性があります

投票は10/27 23:59まで🗳️
投票文かんたん作成👇
<site_url>

投票曲まとめプレイリスト🎧
<playlist_url>
```

- 半角 `( )` と `『 』` を使わない（曲名は「 」、日付の曜日カッコも書かない）。投票として誤集計されるのを防ぐ
- `#VTuber楽曲ランキング` `#ミューコミVR` は付けない
- `site_url` / `playlist_url` は `data/config.json` から

## 限界

Yahoo!リアルタイム検索は似たポストをまとめたり古いポストを落としたりすることがあり、Grok の X 検索も1回10件まで。網羅はできないので、数字は下限の目安として扱う。
