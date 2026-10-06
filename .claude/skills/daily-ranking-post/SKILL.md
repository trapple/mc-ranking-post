---
name: daily-ranking-post
description: Build today's VTuber楽曲ランキング interim TOP5 X post from the latest public votes and copy it to the clipboard. Run daily. Use when user says "今日のランキング", "ランキングツイート", "ランキングポスト", "X用にまとめて", "毎日のポスト", or "daily-ranking-post".
---

# 今日のランキングポスト（毎日）

最新の公開ポストを集計して、X 用の暫定TOP5ポスト文を作り、クリップボードにコピーする。

## 手順

1. `git pull`（Actions が `data/votes.json` を更新している）
2. `python3 tools/collect_yahoo.py` で直近まで取り込む（差分のみ。数ページで終わる）
3. `python3 tools/post_text.py` を実行する
   - 厳密モードで集計し、ポスト文を標準出力に出す。`--copy` でクリップボードにもコピー
   - ひとこと行（2行目の段落）は上位の票差から自動で作る。より良い言い回しがあれば Claude が直してよい（接戦・独走・順位の入れ替わりなど）
   - **ひとこと行など文章中でアーティスト名を出すときは敬称略しない**（「千代浦蝶美さんが月深ツキさんを抜いて」）。順位の行（🥇〜5位）は敬称略でよい
4. `git checkout -- data/votes.json`（手元の追記を捨てる。次の自動実行で同じポストが入る。残すと `git pull` が衝突する）
5. ポスト文をそのまま回答に貼る。あわせて
   - 集計範囲（JST）と有効票数
   - 前回ポスト（`data/rankings/` の直近の履歴や会話）からの順位の動きがあれば一言

## ポスト文の決まり（`tools/post_text.py` に実装済み）

- 冒頭2行は固定: `VTuber楽曲ランキング「<テーマ>」暫定TOP5` / `<M/D HH:MM>時点・公開ポストのみの勝手に集計です`（時刻は集計範囲の最終ポスト、JST）
- 🥇🥈🥉 4位 5位 の順に `アーティスト「曲名」N票`
- 半角 `( )` と `『 』` を使わない、`#VTuber楽曲ランキング` `#ミューコミVR` を付けない（投票として誤集計されるのを防ぐ）
- 末尾に 推移ページ（`<site_url>trend`）→ 締切 → 投票サイト（`site_url`）→ プレイリスト（`playlist_url`、通常の YouTube）。URL は `data/config.json` から
