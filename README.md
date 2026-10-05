# 英語カルテ SNS 全自動投稿

毎日、医学部受験・共通テスト英語のテーマを1つ選び、AI（Claude）が文章を書き、
サムネイル・カルーセル画像・BGM・縦型動画まで自動で作って各SNSに投稿します。
人の操作は最初の設定だけです。

## 1日の流れ（GitHub Actions が自動実行）

| 時刻(JST) | X | Threads | Instagram | note |
|---|---|---|---|---|
| 07:00 朝 | 投稿1 | 投稿1（画像付き） | – | – |
| 12:30 昼 | 投稿2 | 投稿2 | カルーセル（7枚前後） | – |
| 20:00 夜 | 投稿3（URL付き） | 投稿3 | リール動画（約30秒・BGM付き） | 記事1本（無料） |

- テーマは `config/topics.yaml` から重複なしで選ばれます（一巡したら最初から）。
- 日付や配点などの数字は `config/facts.yaml` に書いたものだけ使うよう AI に指示しています。
- BGM はプログラムで毎日自動作曲します（著作権フリー）。`assets/bgm/` に音源を置けばそちらを使います。
- 同じ投稿が二重に出ないよう `public/日付/posted.json` に記録します。

## 必要なもの（ユーザー側の作業）

1. **GitHub リポジトリ（公開）** にこのフォルダを置く
   - 画像・動画を Instagram/Threads に渡すため GitHub Pages を使います。無料プランでは公開リポジトリが必要です。
   - Settings → Pages → Branch を `gh-pages` / `(root)` に設定（初回実行後）
   - 公開URLは `https://<ユーザー名>.github.io/<リポジトリ名>` が自動で使われます（変える場合は Variables の `MEDIA_BASE_URL`）
2. **Claude API キー** → Secret `ANTHROPIC_API_KEY`
3. **X 開発者アカウント**（従量課金。リンクなし $0.015/件、リンクあり $0.20/件）
   - アプリの権限を Read and Write にし、Secrets に `X_API_KEY` `X_API_SECRET` `X_ACCESS_TOKEN` `X_ACCESS_TOKEN_SECRET`
4. **Meta 開発者アプリ**（Threads API と Instagram API、どちらも無料）
   - Instagram はプロアカウント（ビジネス/クリエイター）に切替
   - Secrets に `THREADS_USER_ID` `THREADS_ACCESS_TOKEN` `IG_USER_ID` `IG_ACCESS_TOKEN`（長期トークン）
   - トークン自動延長用に、Secrets を書き換えられる fine-grained PAT を `GH_SECRETS_PAT` に
5. **note**: 公式APIがないため、ブラウザ自動操作で投稿します
   - Secrets に `NOTE_EMAIL` `NOTE_PASSWORD`
   - Variables の `NOTE_MODE` で `publish`（完全自動公開）/ `draft`（下書きまで・既定）/ `off`

## 動作確認

```bash
pip install -r requirements.txt
# APIを使わずサンプルで画像・動画を作る
RUN_DATE=2026-10-06 python -m src.run prepare --content-json samples/sample_content.json
# 投稿せずに中身だけ確認
DRY_RUN=1 RUN_DATE=2026-10-06 python -m src.run post --slot evening
```

GitHub 上では Actions → 「SNS自動投稿」→ Run workflow で `dry_run=1` を指定すると、投稿せずに試せます。

## 費用の目安（月）

- Claude API: 1日1回の生成で数ドル程度
- X: リンクなし2件+リンクあり1件/日 ≈ $7
- Threads / Instagram / GitHub Actions（公開リポジトリ）: 無料

## 注意

- note の自動投稿は公式に認められた方法ではありません。画面変更で止まる・規約上のリスクがある点をご理解のうえ `NOTE_MODE` を選んでください。失敗時は Actions の成果物にスクリーンショットが残ります。
- AI の文章は事実確認を自動で完全には保証できません。`facts.yaml` を最新の公式情報で更新し、定期的に投稿内容を見直してください。
