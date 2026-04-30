# 学校追加フロー

このメモは、対象校を追加するときに同じ調査と生成をすぐ再現するための手順です。

## 依頼テンプレート

次のように依頼すると進めやすいです。

```text
この学校を追加して:
- 学校名
- 公式サイトURL
- Study1の学校ページURL、または学校名だけ

既存と同じ形式で、イベント、予約開始日、住所、最寄駅、学校詳細、偏差値各ソース、月別A4印刷カレンダーまで更新して。
```

Study1の学校IDや各偏差値サイトのコードが分からなくても、こちらで調べて追加できます。

## 追加時に更新する場所

主な編集対象は [scripts/scrape_study1_events.py](/Users/akirakimura/devwork/chugaku_events/scripts/scrape_study1_events.py) です。

- `SCHOOLS`: 表示対象の学校名とStudy1 ID
- `MINKOU_URLS`: みんなの中学校情報の学校URL
- `SYUTOKEN_CODES`: 首都圏模試センターの学校コード
- `YOTSUYA_CODES`: 四谷大塚の学校コード
- `scripts/download_yotsuya_past_exams.py` の `YOTSUYA_KAKOMON_CLASSES`: 四谷大塚過去問データベースの学校・入試区分ID
- `ACCESS_OVERRIDES`: Study1のアクセス情報が薄い場合の補正
- `RESERVATION_RULES`: 公式サイトで予約開始日や開始ルールが確認できる場合の補正
- `SUPPLEMENTAL_EVENTS`: Study1に載らない公式イベントの手動追加

表示側は [scripts/build_events_html.py](/Users/akirakimura/devwork/chugaku_events/scripts/build_events_html.py) が生成します。通常、学校を増やすだけなら表示側の変更は不要です。

## 調査する情報源

イベントと学校基本情報:

- Study1学校ページ: `https://www.study1.jp/kanto/school/{Study1 ID}/`
- Study1説明会ページ: `https://www.study1.jp/kanto/school/{Study1 ID}/briefing/`
- 学校公式サイトの入試・説明会・イベントページ

予約開始日:

- 公式サイトに日付がある場合は公式を優先
- 日付ではなく「1か月前」「3週間前」などのルールしかない場合は、`予約開始精度=rule` として記載
- 予定のみの場合は `tentative`
- 根拠URLは必ず残す

偏差値:

- スタディ: `https://www.study1.jp/kanto/list/deviation.html`
- みんなの中学校情報: 学校別ページ
- 首都圏模試センター: `https://www.syutoken-mosi.co.jp/db/school/?code={code}&p=3`
- 四谷大塚: `https://www.yotsuyaotsuka.com/juken/data/?code={code}`

偏差値はソースごとに母集団や定義が違うので、単一の代表値に混ぜないこと。四谷大塚は `Aライン80偏差値` と `Cライン50偏差値` があり、入試回・男女別に値が分かれるため、CSVには要約と詳細の両方を残す。

## コードの探し方

Study1 ID:

```bash
python3 - <<'PY'
import urllib.parse
name = "学校名"
print("https://www.study1.jp/kanto/search/?keyword=" + urllib.parse.quote(name))
PY
```

四谷大塚コードは検索で見つかることが多いです。

```text
site:yotsuyaotsuka.com/juken/data 学校名 四谷大塚
```

四谷大塚の過去問データベースIDは、ZenブラウザのセッションCookieを使って過去問トップを取得し、学校名で探します。Cookie値は表示しないこと。

```bash
python3 - <<'PY'
import sqlite3, shutil, tempfile, pathlib, urllib.request
from bs4 import BeautifulSoup

db = pathlib.Path.home() / "Library/Application Support/zen/Profiles/3c09d2c2.Default (release)/cookies.sqlite"
tmp = pathlib.Path(tempfile.gettempdir()) / "zen_yotsuya_cookies.sqlite"
shutil.copy2(db, tmp)
con = sqlite3.connect(tmp)
cookie = "; ".join(f"{n}={v}" for n, v in con.execute("select name,value from moz_cookies where host like '%yotsuyaotsuka.com%'"))
req = urllib.request.Request("https://www.yotsuyaotsuka.com/chugaku_kakomon/system", headers={"User-Agent": "Mozilla/5.0", "Cookie": cookie})
soup = BeautifulSoup(urllib.request.urlopen(req).read().decode("utf-8", "replace"), "html.parser")
for a in soup.select("a[href]"):
    if "学校名" in a.get_text(strip=True):
        print(a.get_text(strip=True), a["href"])
PY
```

首都圏模試コードも学校名検索で確認します。

```text
site:syutoken-mosi.co.jp/db/school 学校名 首都圏模試
```

みんなの中学校情報は学校名検索で学校別URLを確認します。

```text
site:minkou.jp/junior/school 学校名
```

## 実行手順

1. `scripts/scrape_study1_events.py` の対象校とコード表を更新する。
2. 公式サイトを確認し、必要なら `RESERVATION_RULES` と `SUPPLEMENTAL_EVENTS` を足す。
3. データを再取得する。

```bash
python3 scripts/scrape_study1_events.py
```

4. 四谷大塚の過去問PDFを全件取得する。

```bash
python3 scripts/download_yotsuya_past_exams.py
```

5. HTMLを再生成する。

```bash
python3 scripts/build_events_html.py
```

6. ローカルで確認する。

```bash
python3 -m http.server 8000
```

確認URL:

```text
http://localhost:8000/index.html
```

## 追加後の確認ポイント

- [ ] `data/schools.csv` に新しい学校が1行追加されている
- [ ] `data/events.csv` にイベントが入っている
- [ ] `index.html` の学校一覧に表示される
- [ ] `schools/{Study1 ID}.html` が生成される
- [ ] 住所、TEL、最寄駅、公式URL、説明会URLが入っている
- [ ] 予約開始日・根拠URLが入っている
- [ ] 月別カレンダーとA4印刷表示にイベントが出る
- [ ] スタディ、みんな、首都圏模試、四谷大塚の偏差値が出る
- [ ] 偏差値が未掲載のソースは空欄ではなく「掲載なし」またはURLつきで理由が分かる
- [ ] `data/past_exams.csv` に四谷大塚過去問PDFの取得結果が入っている
- [ ] `past_exams/` にPDFが保存されている
- [ ] 学校詳細ページに過去問PDFリンクが年度・科目・問題/解答別に表示される

## 既知の注意点

- Study1に載らない公式イベントがある。渋谷教育学園渋谷のように公式サイトから `SUPPLEMENTAL_EVENTS` に足す。
- 四谷大塚は学校ページがあっても偏差値表が未掲載の学校がある。富士見丘はこのケース。
- 四谷大塚の過去問データベースに学校がない場合がある。東京大学教育学部附属中等教育学校はこのケース。
- 過去問PDFは件数と容量が大きい。既存ファイルは再ダウンロードしない実装なので、追加校だけなら2回目以降は比較的速い。
- 予約開始日はStudy1より公式サイトのほうが正確なことがある。
- 公式サイトがPDFや画像中心の場合、予約開始日は手作業で根拠確認が必要になる。
- 追加校が増えると学校カードや偏差値欄が長くなるため、表示確認は必ず行う。
