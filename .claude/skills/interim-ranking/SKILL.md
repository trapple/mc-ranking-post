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
| `data/urls/<JST開始>_<JST終了>.txt` | Grok で集めたポストURL（12時間ごと）。区間の終わりから6時間以上たったものは確定扱いで再検索しない |
| `data/posts.json` | ポストID → 本文・投稿者・時刻のキャッシュ。取得済みは再取得しない |
| `data/rankings/<JST時刻>.txt` | 集計結果の履歴 |

## 手順

1. **URL収集**: `python3 tools/collect.py` を Bash の `run_in_background: true` で実行する（Grok を区間ごとに最大6並列、1区間最大20分）。完了通知を待つ
   - 確定区間はスキップされるので、2回目以降は直近の区間だけが走る
2. **集計**: `python3 tools/tally.py` を実行する（新しいポストだけ fxtwitter で取得。1件0.3秒）
   - 既定は厳密モード。`MODE=lenient` で「( )・『 』が複数あっても最初を採用」する寛容モード
   - 両方実行して、差（主に YouTube 共有タイトルの `(Official Music Video)` 由来）をユーザーに伝える
3. **報告**: 厳密モードの上位を表で示し、次も添える
   - 集計対象の時間範囲（JST）と件数、無効の内訳
   - 表記ゆれで票が割れている曲（出力末尾の「表記ゆれ候補」）
4. **TOP5ポスト文**: 依頼されたら作って `pbcopy` でコピーする

## ルール（`tools/tally.py` に実装済み）

- `#VTuber楽曲ランキング` と `#ミューコミVR` の両方が必要
- アーティスト名は半角 `( )`、曲名は `『 』` 内。全角（ ）は無効
- 1人1日1回（JST日付）。同日2回目以降は無効
- 表記が違えば別曲として数える（公式ルールどおり。統合はしない）

## TOP5ポスト文の注意

- 半角 `( )` と `『 』` を使わない（曲名は「 」、日付の曜日カッコも書かない）。投票として誤集計されるのを防ぐ
- `#VTuber楽曲ランキング` `#ミューコミVR` は付けない
- 「◯/◯ ◯時時点・公開ポストのみの非公式集計」「DM票は含まれない」を明記
- 末尾に投票サポートサイトとプレイリストのURL（`data/config.json` の `site_url` / `playlist_url`）

## 限界

Grok の X 検索は1回10件までで、網羅はできない。数字は下限の目安として扱う。
