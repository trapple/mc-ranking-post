---
name: vote-lookup
description: Find VTuber楽曲ランキング vote posts for a given artist/song or X account and check whether each one is counted (valid / invalid reason / not yet collected). Use when user says "◯◯の投票さがして", "◯◯の投稿さがして", "俺の投票入ってる？", "投票が入ってない", "得票数知りたい", or "vote-lookup".
---

# 投票ポストの検索・集計反映チェック

特定のアーティスト・曲、または特定アカウントの投票ポストを探し、集計にどう反映されているかを確かめる。

## 使い方

まず `git pull`（Actions が `data/votes.json` を更新しているため）。

```
python3 tools/lookup.py --artist 琶舞                # アーティスト名（部分一致・表記ゆれ込み）
python3 tools/lookup.py --song "Symbiotic"           # 曲名（部分一致）
python3 tools/lookup.py --user v_masuoji             # アカウントの投票（@ なし）
python3 tools/lookup.py --artist 琶舞 --user v_masuoji
```

- 集計データ（`data/votes.json`）にある投票を一覧し、状態を出す: `有効` / `同日2回目以降` / 無効の理由
- `--user` を付けると Yahoo!リアルタイム検索（`ID:<user>` と `ID:<user> 投票します` の2回。キーワード検索は反映が遅れるため）も引き、**まだ集計データに入っていない**ポストを fxtwitter で直接取得して、有効かどうかを判定する（`未取込` と表示。次の自動実行で取り込まれる。ストアには書き込まない）
- アカウント名はストアにハッシュでしか無いので、`--user` はハッシュを計算して照合する（鍵 `~/.config/mc-ranking/salt` が必要）

## 報告

- 件数、各ポストの日時（JST）・状態・URL（`https://x.com/i/status/<id>`）を表で示す
- 有効票数（厳密モード）と全体順位
- 見つからない／入っていない場合は原因の候補を伝える
  - 自動実行がまだ（GitHub の定時実行は遅れたり飛んだりする。`gh run list -R trapple/mc-ranking-post -w update -L 5` で確認）
  - Yahoo!への反映待ち（キーワード検索に出るまで時間がかかることがある）
  - 書式・ハッシュタグの不備（表示される無効理由を見る）
  - DM で投票した（公開ポストではないので見えない）
