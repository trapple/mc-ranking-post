---
name: update-playlist
description: Add newly voted songs from the VTuber楽曲ランキング public X posts to the YouTube playlist, resolving each song to its official YouTube video. Use when user says "プレイリスト更新", "最新プレイリスト", "プレイリストに追加", "update-playlist", or after running interim-ranking when new songs appear.
---

# 最新プレイリスト更新

集計済みポストから投票曲を拾い、まだプレイリストにない曲の公式動画を探して追加する。

## 前提

- 先に `git pull` で `data/votes.json` を最新にする（GitHub Actions が2時間ごとに更新している）。直近まで欲しければ `interim-ranking` の手順1〜2も実行する
- YouTube の OAuth クライアント JSON: 環境変数 `YT_CLIENT_SECRET`、なければ `~/Downloads/client_secret_*.json`
- トークン: `~/.config/mc-ranking/yt-token.json`（リポジトリ外。期限切れ時はブラウザ認証が開く → ユーザーに許可を頼む）
- Python 依存は `uv run` が自動で入れる

## データ

`data/songs.json`: 曲キー（正規化した「アーティスト|曲名」）→ 状態。
- `video_id`: 追加済み/追加する動画
- `status`: `added` / `not_found`（YouTubeにない）/ `skip`（集計崩れ・対象外）/ `alias`（表記ゆれ。`alias_of` に本来のキー）
- 一度判定した曲は次回以降スキップされる

## 手順

1. **候補出し**: `uv run tools/playlist.py plan`
   - `songs.json` 未登録の曲を列挙し、ポスト内の YouTube URL（oEmbed でタイトル一致を確認）→ なければ yt-dlp 検索上位3件、を出す
   - 自動で確定できたもの（ポスト内URLのタイトルに曲名を含む）は `auto` と表示
   - すでにプレイリストにある曲（手動追加分・表記ゆれ・集計崩れを含む）は `[matched]` と表示され、自動で `added` になる。集計崩れ（`(火)` など）や表記ゆれが混じっていたら `set` で `skip` / `alias` に直す
2. **判定**（Claude が行う）: 候補ごとに `uv run tools/playlist.py set` で登録する
   - `set KEY video VIDEO_ID` / `set KEY not_found` / `set KEY skip "理由"` / `set KEY alias OTHER_KEY`
   - `auto` はまとめて `uv run tools/playlist.py accept-auto`
   - 公式MV > 公式音源（- Topic）> リリックビデオ。歌枠切り抜き・カバー・「歌ってみた」は選ばない
   - `(火)`、`(スマホ専用)`、`(Official Music Video)` のような集計崩れは `skip`
   - 表記ゆれ（`(月白 累)`/`(月白累)` など）は `alias`
3. **追加**: `uv run tools/playlist.py sync` で `status=video` の未追加分をプレイリストへ追加し `added` にする（既存動画は重複追加しない）
   - 1日の API 上限は約200件。まず1件で動作確認してから残りを流す
4. **報告**: 追加数、見つからなかった曲、確認が必要な曲（オリジナルか怪しいものなど）を伝える

## 並べ替え

`uv run tools/playlist.py move VIDEO_ID POSITION`（0始まり）
