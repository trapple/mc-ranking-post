# mc-ranking-post

ミューコミVR「VTuber楽曲ランキング」の投票サポートサイトと、公開ポストの非公式な暫定集計。

- 投票サポート: https://mc-ranking-utahajimari.trapplejp.workers.dev/
- 票数の推移（非公式）: https://mc-ranking-utahajimari.trapplejp.workers.dev/trend

## 構成

| パス | 役割 |
|---|---|
| `public/` | Cloudflare Workers（静的アセット）で配信するサイト。`trend.html` / `trend-og.png` は自動生成 |
| `tools/collect_yahoo.py` | Yahoo!リアルタイム検索から投票ポストのIDを集める（差分取得） |
| `tools/collect.py` | Grok で投票ポストのURLを集める（補助。要 Grok Build） |
| `tools/tally.py` | 新しいポストを fxtwitter で取得して `data/votes.json` に追記し、公式ルールで集計 |
| `tools/trend.py` | 推移ページとシェア用画像を生成（headless Chrome） |
| `tools/playlist.py` | 投票曲を YouTube プレイリストに反映（手動・要 OAuth） |
| `data/votes.json` | 集計に必要な最小限のデータ（下記） |
| `data/songs.json` | 曲キー → プレイリスト動画の対応 |

## data/votes.json

ポストIDをキーに、集計に必要な情報だけを持つ。**ポスト本文とアカウント名は保存しない。**

```json
{"2105255699651694876": {"code": 200, "ts": 1790767047, "u": "3f9a1c…", "tags": true,
  "a": ["Palette Project"], "s": ["ギミラビ"], "yt": []}}
```

- `u`: アカウント名（小文字化）の HMAC-SHA256 先頭16桁。「1人1日1回」の判定にだけ使う。鍵は環境変数 `MC_SALT`（ローカルは `~/.config/mc-ranking/salt`、CI は Secrets）
- `tags`: `#VTuber楽曲ランキング` と `#ミューコミVR` の両方があるか
- `a` / `s`: 半角 `( )` 内と `『 』` 内の文字列すべて（厳密/寛容モードの判定用）。`@アカウント` は `@***` に伏せる
- `yt`: ポスト内の YouTube 動画ID（プレイリストの候補出し用）
- `code`: 取得結果（200 / 404）。404 は削除・非公開

## 定期実行（GitHub Actions）

`.github/workflows/update.yml` が2時間ごと（UTC 偶数時 = JST 奇数時）に実行する。

1. `collect_yahoo.py` で新着ポストを収集
2. `tally.py` で取得・集計し `data/votes.json` を更新
3. `trend.py` で推移ページとシェア画像を生成
4. 変更があればコミットして push し、`wrangler deploy` で公開

締切（`data/config.json` の `deadline_jst`）から6時間を過ぎると何もしない。

必要な設定:

| 種類 | 名前 | 内容 |
|---|---|---|
| Secret | `CLOUDFLARE_API_TOKEN` | 「Edit Cloudflare Workers」テンプレートのトークン |
| Secret | `MC_SALT` | アカウント名ハッシュの鍵（ローカルと同じ値） |
| Variable | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare のアカウントID |

プレイリスト更新と TOP5 ポスト文の作成は判断が必要なので手動（`.claude/skills/`）。
