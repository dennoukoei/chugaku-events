#!/usr/bin/env python3
import csv
import html as html_lib
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT = ROOT / "index.html"
SCHOOL_DIR = ROOT / "schools"
EXCLUDE_PAST_EXAMS = os.environ.get("EXCLUDE_PAST_EXAMS") == "1"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_csv_optional(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv(path)


PAST_EXAM_FALLBACKS: dict[str, list[tuple[str, str]]] = {
    "B13N007": [
        ("FAQ: 実技の出題例", "https://www.hs.p.u-tokyo.ac.jp/forentrance/qa"),
        ("入学検査問題の二次利用", "https://www.hs.p.u-tokyo.ac.jp/archives/38158"),
        ("入学検査について", "https://www.hs.p.u-tokyo.ac.jp/forentrance/guideline"),
    ]
}


def sort_key(row: dict[str, str]) -> tuple[str, str, str]:
    date = row.get("開催日", "")
    match = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", date)
    normalized = (
        f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}"
        if match
        else "99999999"
    )
    return (normalized, row.get("開催時間", ""), row.get("学校名", ""))


def school_page_name(school: dict[str, str]) -> str:
    return f"{school['study1_id']}.html"


def escape(value: str) -> str:
    return html_lib.escape(str(value or ""), quote=True)


def parse_date_key(row: dict[str, str]) -> str:
    match = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", row.get("開催日", ""))
    if not match:
        return ""
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"


def month_label(key: str) -> str:
    year, month = key.split("-")
    return f"{year}年{int(month)}月"


def precision_label(value: str) -> str:
    return {
        "exact": "開始日時あり",
        "range": "受付期間あり",
        "rule": "開始ルール",
        "tentative": "予定",
        "unknown": "",
    }.get(value, "")


def split_summary(value: str) -> list[str]:
    if not value:
        return []
    if " | " in value:
        return [part.strip() for part in value.split(" | ") if part.strip()]
    return [part.strip() for part in re.split(r"(?<=。)", value) if part.strip()]


def info_cards(items: list[tuple[str, str]]) -> str:
    cards = []
    for label, value in items:
        if not value:
            continue
        cards.append(
            f"""
            <div class="info-card">
              <span>{escape(label)}</span>
              <strong>{escape(value)}</strong>
            </div>
            """
        )
    return "".join(cards)


def deviation_cards(school: dict[str, str]) -> str:
    items = [
        ("スタディ", school.get("スタディ偏差値", ""), school.get("スタディ偏差値URL", "")),
        ("みんな 2026", school.get("みんな偏差値2026", ""), school.get("みんな偏差値URL", "")),
        ("首都圏模試", school.get("首都圏模試偏差値", ""), school.get("首都圏模試URL", "")),
        ("四谷大塚", school.get("四谷大塚偏差値", ""), school.get("四谷大塚URL", "")),
    ]
    cards = []
    for label, value, url in items:
        if not value:
            continue
        source = (
            f'<a href="{escape(url)}" target="_blank" rel="noopener">出典</a>'
            if url
            else ""
        )
        cards.append(
            f"""
            <div class="deviation-card">
              <span>{escape(label)}</span>
              <strong>{escape(value)}</strong>
              {source}
            </div>
            """
        )
    if not cards:
        return ""
    return f'<div class="deviation-grid">{"".join(cards)}</div>'


def summary_list(value: str) -> str:
    items = split_summary(value)
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def past_exam_sections(rows: list[dict[str, str]], link_prefix: str = "") -> str:
    downloaded = [row for row in rows if row.get("状態") == "取得済み" and row.get("ファイル")]
    if not downloaded:
        return '<div class="empty">四谷大塚の過去問データベースに対象校のPDF掲載が見つかりませんでした。</div>'
    by_exam: dict[str, list[dict[str, str]]] = {}
    for row in sorted(downloaded, key=lambda r: (r.get("入試区分", ""), r.get("年度", ""), r.get("科目", ""), r.get("種別", "")), reverse=True):
        by_exam.setdefault(row.get("入試区分") or "掲載分", []).append(row)
    sections = []
    for exam_label, exam_rows in by_exam.items():
        by_year: dict[str, list[dict[str, str]]] = {}
        for row in exam_rows:
            by_year.setdefault(row.get("年度", ""), []).append(row)
        years_html = []
        for year in sorted(by_year, reverse=True):
            subject_rows: dict[str, dict[str, str]] = {}
            for row in sorted(by_year[year], key=lambda r: (r.get("科目", ""), r.get("種別", ""))):
                subject_rows.setdefault(row.get("科目", ""), {})[row.get("種別", "")] = row.get("ファイル", "")
            rows_html = "".join(
                f"""
                <div class="past-row">
                  <div class="past-subject">{escape(subject)}</div>
                  <div class="past-action">
                    {f'<a href="{escape(link_prefix + pair.get("問題", ""))}" target="_blank" rel="noopener">問題</a>' if pair.get("問題") else '<span class="missing">未掲載</span>'}
                  </div>
                  <div class="past-action">
                    {f'<a href="{escape(link_prefix + pair.get("解答", ""))}" target="_blank" rel="noopener">解答</a>' if pair.get("解答") else '<span class="missing">未掲載</span>'}
                  </div>
                </div>
                """
                for subject, pair in subject_rows.items()
            )
            years_html.append(
                f"""
                <details class="past-year" open>
                  <summary>{escape(year)}年 <span>{len(by_year[year])}件</span></summary>
                  <div class="past-grid">
                    <div class="past-head">科目</div>
                    <div class="past-head">問題</div>
                    <div class="past-head">解答</div>
                    {rows_html}
                  </div>
                </details>
                """
            )
        sections.append(
            f"""
            <details class="past-exam-section">
              <summary>{escape(exam_label)} <span>{len(exam_rows)}件</span></summary>
              <div>{"".join(years_html)}</div>
            </details>
            """
        )
    if sections:
        return "".join(sections)
    return '<div class="empty">四谷大塚の過去問データベースに対象校のPDF掲載が見つかりませんでした。</div>'


def build_calendar_month(key: str, events: list[dict[str, str]], css_prefix: str = "") -> str:
    year, month = map(int, key.split("-"))
    import calendar

    by_day: dict[int, list[dict[str, str]]] = {}
    for event in events:
        match = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", event.get("開催日", ""))
        if not match:
            continue
        if f"{int(match.group(1)):04d}-{int(match.group(2)):02d}" != key:
            continue
        by_day.setdefault(int(match.group(3)), []).append(event)

    weekdays = ["日", "月", "火", "水", "木", "金", "土"]
    cells = [f'<div class="{css_prefix}weekday">{day}</div>' for day in weekdays]
    first_weekday, last_day = calendar.monthrange(year, month)
    # Python: Monday=0. Calendar UI: Sunday=0.
    sunday_first = (first_weekday + 1) % 7
    cells.extend(f'<div class="{css_prefix}day empty"></div>' for _ in range(sunday_first))
    for day in range(1, last_day + 1):
        items = by_day.get(day, [])
        event_html = "".join(
            f"""
            <div class="{css_prefix}cal-event">
              <strong>{escape(event.get('イベント名'))}</strong>
              <span>{escape(event.get('開催時間') or '時間未掲載')}</span>
              <span>{escape(event.get('予約開始日・記載'))}</span>
            </div>
            """
            for event in items
        )
        cells.append(
            f"""
            <div class="{css_prefix}day {'has-events' if items else ''}">
              <span class="{css_prefix}day-number">{day}</span>
              {event_html}
            </div>
            """
        )
    remainder = len(cells) % 7
    if remainder:
        cells.extend(f'<div class="{css_prefix}day empty"></div>' for _ in range(remainder, 7))
    return "".join(cells)


def write_school_pages(schools: list[dict[str, str]], events: list[dict[str, str]], past_exams: list[dict[str, str]]) -> None:
    SCHOOL_DIR.mkdir(exist_ok=True)
    events_by_school = {school["学校名"]: [] for school in schools}
    for event in events:
        events_by_school.setdefault(event["学校名"], []).append(event)
    past_by_school = {school["study1_id"]: [] for school in schools}
    for row in past_exams:
        past_by_school.setdefault(row.get("study1_id", ""), []).append(row)

    for school in schools:
        school_events = sorted(events_by_school.get(school["学校名"], []), key=sort_key)
        school_past_exams = past_by_school.get(school["study1_id"], [])
        past_exam_html = past_exam_sections(school_past_exams, "../")
        past_exam_count = sum(1 for row in school_past_exams if row.get("状態") == "取得済み")
        past_exam_fallbacks = PAST_EXAM_FALLBACKS.get(school["study1_id"], [])
        fallback_html = ""
        if past_exam_count == 0 and past_exam_fallbacks:
            fallback_html = """
            <div class="data-panel">
              <h2>公開過去問の代替情報</h2>
              <p>公開PDFは見つかりませんでした。公式サイトの検査案内とFAQを確認してください。</p>
              <div class="links">
                %s
              </div>
            </div>
            """ % "".join(
                f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(label)}</a>'
                for label, url in past_exam_fallbacks
            )
        if EXCLUDE_PAST_EXAMS:
            past_exam_section_html = ""
        else:
            past_exam_section_html = (
                '<section>'
                '<div class="section-title"><h2>過去問PDF</h2>'
                '<span>四谷大塚 過去問データベース掲載分</span></div>'
                f'{past_exam_html}'
                f'{fallback_html}'
                '</section>'
            )
        months = sorted({parse_date_key(event) for event in school_events if parse_date_key(event)})
        basic_items = [
            ("設置", school.get("設置", "")),
            ("学校種別", school.get("学校種別", "")),
            ("生徒総数", school.get("生徒総数", "")),
            ("制服", school.get("制服", "")),
        ]
        basic_html = info_cards(basic_items)
        deviation_html = deviation_cards(school)
        feature_html = summary_list(school.get("特徴サマリー", ""))
        tuition_html = summary_list(school.get("学費サマリー", ""))
        exam_html = summary_list(school.get("入試結果サマリー", ""))

        detail_sections = []
        for label, key in [
            ("スタディ注目ポイント", "注目ポイント"),
            ("建学の精神・教育理念", "詳細_建学の精神、教育理念"),
            ("教育の特色", "詳細_教育の特色"),
            ("施設設備", "詳細_施設設備"),
            ("学校行事", "詳細_学校行事"),
            ("部活動", "詳細_部活動"),
            ("進路指導", "詳細_進路指導"),
            ("その他", "詳細_その他"),
            ("スクール特集", "スクール特集"),
            ("学校からのお知らせ", "学校からのお知らせ"),
        ]:
            value = school.get(key, "")
            if value:
                detail_sections.append(
                    f"""
                    <details class="info-section">
                      <summary>{escape(label)}</summary>
                      <div>{summary_list(value) or f'<p>{escape(value)}</p>'}</div>
                    </details>
                    """
                )
        detail_html = "\n".join(detail_sections)
        event_rows = "".join(
            f"""
            <article class="event">
              <div class="datebox">
                <strong>{escape(event.get('開催日') or '随時')}</strong>
                <span>{escape(event.get('開催時間') or '時間未掲載')}</span>
              </div>
              <div>
                <h3>{escape(event.get('イベント名'))}</h3>
                <div class="tags">
                  {f'<span>{escape(event.get("場所"))}</span>' if event.get("場所") else ''}
                  {f'<span>{escape(event.get("対象"))}</span>' if event.get("対象") else ''}
                  {f'<span class="reserve">{escape(event.get("予約開始日・記載"))}</span>' if event.get("予約開始日・記載") else ''}
                  {f'<span>{escape(precision_label(event.get("予約開始精度", "")))}</span>' if precision_label(event.get("予約開始精度", "")) else ''}
                </div>
                {f'<p>{escape(event.get("備考"))}</p>' if event.get("備考") else ''}
              </div>
              <div class="actions">
                {f'<a href="{escape(event.get("予約URL"))}" target="_blank" rel="noopener">予約</a>' if event.get("予約URL") else ''}
                {f'<a href="{escape(event.get("詳細URL"))}" target="_blank" rel="noopener">詳細</a>' if event.get("詳細URL") else ''}
                {f'<a href="{escape(event.get("予約開始根拠URL"))}" target="_blank" rel="noopener">開始日根拠</a>' if event.get("予約開始根拠URL") else ''}
              </div>
            </article>
            """
            for event in school_events
        ) or '<div class="empty">イベント情報はありません。</div>'

        calendar_sections = "".join(
            f"""
            <section class="month">
              <div class="month-title">
                <h2>{month_label(month)}</h2>
                <span>{sum(1 for event in school_events if parse_date_key(event) == month)}件</span>
              </div>
              <div class="calendar">{build_calendar_month(month, school_events)}</div>
            </section>
            """
            for month in months
        ) or '<div class="empty">カレンダーに表示できる日付付きイベントはありません。</div>'

        print_sections = "".join(
            f"""
            <section class="print-month">
              <div class="print-title">
                <h1>{escape(school['学校名'])} {month_label(month)}</h1>
                <p>{sum(1 for event in school_events if parse_date_key(event) == month)}件 / 取得基準日 2026-04-30</p>
              </div>
              <div class="print-grid">{build_calendar_month(month, school_events, 'print-')}</div>
            </section>
            """
            for month in months
        )

        page = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(school['学校名'])} | イベント詳細</title>
  <style>
    :root {{ --bg:#f5f7f3; --surface:#fff; --surface-2:#fafbf7; --ink:#14191c; --muted:#50595d; --line:#ccd5d1; --line-soft:#e3e9e6; --accent:#1e655c; --accent2:#8a3434; --soft:#e3edea; --shadow:0 14px 32px rgba(20,30,35,.10); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic","YuGothic","Noto Sans JP",sans-serif; font-size:16px; line-height:1.7; }}
    a {{ color:var(--accent); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    header {{ background:#173b3b; color:#fff; border-bottom:5px solid #c28a35; }}
    .topbar, main, footer {{ max-width:1180px; margin:0 auto; padding:32px 24px; }}
    main {{ padding-top:32px; }}
    .back {{ color:#d7ece7; font-size:14px; font-weight:700; }}
    .back:hover {{ color:#fff; }}
    h1 {{ margin:12px 0 0; font-size:clamp(28px,4.4vw,44px); line-height:1.2; letter-spacing:0; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:22px; }}
    .pill {{ display:inline-flex; min-height:34px; align-items:center; padding:6px 14px; border:1px solid rgba(255,255,255,.28); border-radius:999px; background:rgba(255,255,255,.10); color:#f1faf7; font-size:14px; font-weight:600; }}
    .panel {{ padding:20px; border:1px solid var(--line); border-radius:10px; background:var(--surface); }}
    .panel p {{ margin:8px 0; color:var(--muted); font-size:15px; }}
    .profile-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:18px; }}
    .info-card {{ min-height:84px; padding:16px; border:1px solid var(--line); border-radius:10px; background:var(--surface-2); }}
    .info-card span {{ display:block; margin-bottom:6px; color:var(--muted); font-size:13px; font-weight:800; letter-spacing:0.02em; }}
    .info-card strong {{ display:block; font-size:16px; line-height:1.5; font-weight:700; }}
    .deviation-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:18px; }}
    .deviation-card {{ min-height:96px; padding:16px; border:1px solid #b8cdc6; border-radius:10px; background:#eff7f3; }}
    .deviation-card span {{ display:block; margin-bottom:6px; color:#3f4a4d; font-size:13px; font-weight:800; letter-spacing:0.02em; }}
    .deviation-card strong {{ display:block; font-size:24px; line-height:1.2; color:var(--accent); font-weight:800; }}
    .deviation-card a {{ display:inline-flex; margin-top:6px; font-size:13px; font-weight:800; }}
    .detail-grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px; }}
    .data-panel {{ padding:20px; border:1px solid var(--line); border-radius:10px; background:#fff; }}
    .data-panel h2 {{ margin:0 0 14px; font-size:20px; font-weight:800; }}
    .data-panel ul, .info-section ul {{ margin:0; padding-left:20px; }}
    .data-panel li, .info-section li {{ margin:8px 0; color:#2a3236; font-size:14px; line-height:1.65; }}
    .info-section {{ margin:14px 0; border:1px solid var(--line); border-radius:10px; background:#fff; overflow:hidden; }}
    .info-section summary {{ cursor:pointer; padding:16px 20px; color:var(--ink); font-size:17px; font-weight:800; background:var(--surface-2); }}
    .info-section summary:hover {{ background:#f1f4ee; }}
    .info-section[open] summary {{ border-bottom:1px solid var(--line); }}
    .info-section div {{ padding:18px 20px; }}
    .info-section p {{ margin:0; color:#2a3236; font-size:15px; line-height:1.75; }}
    .past-exam-section {{ margin:14px 0; border:1px solid var(--line); border-radius:10px; background:#fff; overflow:hidden; }}
    .past-exam-section summary {{ cursor:pointer; display:flex; justify-content:space-between; gap:12px; padding:16px 20px; color:var(--ink); font-size:17px; font-weight:800; background:var(--surface-2); }}
    .past-exam-section summary:hover {{ background:#f1f4ee; }}
    .past-exam-section[open] summary {{ border-bottom:1px solid var(--line); }}
    .past-year {{ border-bottom:1px solid var(--line-soft); background:#fff; }}
    .past-year:last-child {{ border-bottom:0; }}
    .past-year summary {{ cursor:pointer; display:flex; justify-content:space-between; gap:12px; padding:13px 20px; color:var(--ink); font-size:15px; font-weight:800; background:#fdfdfc; }}
    .past-year summary:hover {{ background:var(--surface-2); }}
    .past-year[open] summary {{ border-bottom:1px solid var(--line-soft); }}
    .past-grid {{ display:grid; grid-template-columns:minmax(0,1.8fr) minmax(100px,0.6fr) minmax(100px,0.6fr); }}
    .past-head, .past-row > div {{ padding:12px 16px; border-bottom:1px solid var(--line-soft); }}
    .past-head {{ background:#e9f0ec; color:#3f4a4d; font-size:13px; font-weight:800; letter-spacing:0.02em; }}
    .past-row {{ display:contents; }}
    .past-subject {{ font-size:14px; font-weight:700; color:var(--ink); overflow-wrap:anywhere; }}
    .past-action {{ display:flex; align-items:center; }}
    .past-action a, .past-action .missing {{ display:inline-flex; min-height:32px; align-items:center; padding:5px 12px; border-radius:6px; font-size:13px; font-weight:800; text-decoration:none; }}
    .past-action a {{ border:1px solid #b8cdc6; background:#eff7f3; color:var(--accent); }}
    .past-action a:hover {{ background:var(--soft); }}
    .past-action .missing {{ color:var(--muted); }}
    .links {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }}
    .btn, .links a, .actions a {{ display:inline-flex; align-items:center; justify-content:center; min-height:40px; padding:8px 14px; border:1px solid var(--accent); border-radius:8px; background:#fff; color:var(--accent); font-size:14px; font-weight:700; text-decoration:none; transition:background 0.15s ease; }}
    .btn:hover, .links a:hover, .actions a:hover {{ background:var(--soft); text-decoration:none; }}
    .section-title, .month-title {{ display:flex; justify-content:space-between; align-items:end; gap:16px; margin:44px 0 16px; padding-bottom:10px; border-bottom:2px solid var(--line); }}
    h2 {{ margin:0; font-size:24px; letter-spacing:0; font-weight:800; }}
    .calendar {{ display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); border-top:1px solid var(--line); border-left:1px solid var(--line); background:#fff; border-radius:10px; overflow:hidden; }}
    .weekday {{ min-height:38px; padding:10px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); background:#e9f0ec; color:#3f4a4d; font-size:13px; font-weight:800; letter-spacing:0.04em; text-align:center; }}
    .day {{ min-height:130px; padding:10px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); background:#fff; }}
    .day.empty {{ background:#f3f5f2; }}
    .day-number {{ display:inline-flex; justify-content:center; align-items:center; width:30px; min-height:30px; margin-bottom:8px; border-radius:6px; font-size:14px; font-weight:800; }}
    .day.has-events .day-number {{ background:var(--accent); color:#fff; }}
    .cal-event {{ margin:6px 0; padding:7px 9px; border-left:3px solid var(--accent2); border-radius:5px; background:#f8edec; font-size:13px; line-height:1.4; overflow-wrap:anywhere; }}
    .cal-event strong, .cal-event span {{ display:block; }}
    .cal-event strong {{ font-weight:700; color:var(--ink); }}
    .cal-event span {{ color:var(--muted); font-size:12px; margin-top:3px; }}
    .events {{ display:grid; gap:14px; }}
    .event {{ display:grid; grid-template-columns:160px minmax(0,1fr) 180px; gap:18px; padding:18px; border:1px solid var(--line); border-radius:10px; background:#fff; transition:box-shadow 0.15s ease; }}
    .event:hover {{ box-shadow:var(--shadow); }}
    .datebox {{ display:grid; align-content:start; gap:6px; min-height:80px; padding:14px; border-left:4px solid var(--accent); border-radius:8px; background:var(--soft); }}
    .datebox span, .event p {{ color:var(--muted); font-size:14px; }}
    .datebox span:first-child, .datebox .date {{ font-weight:800; font-size:17px; color:var(--ink); }}
    .event h3 {{ margin:0 0 8px; font-size:19px; letter-spacing:0; font-weight:800; line-height:1.4; }}
    .tags {{ display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; }}
    .tags span {{ display:inline-flex; min-height:28px; align-items:center; padding:4px 12px; border-radius:999px; background:#ece8de; color:#4a443a; font-size:13px; font-weight:700; }}
    .tags .reserve {{ background:#f6dada; color:var(--accent2); }}
    .actions {{ display:grid; align-content:start; gap:10px; }}
    .empty {{ padding:32px; border:1px dashed #b3bfba; border-radius:10px; background:#fff; color:var(--muted); font-size:15px; text-align:center; }}
    .print-calendar {{ display:none; }}
    footer {{ color:var(--muted); font-size:13px; }}
    @media (max-width:900px) {{ .event, .profile-grid, .detail-grid, .deviation-grid, .past-grid {{ grid-template-columns:1fr; }} .actions {{ display:flex; flex-wrap:wrap; }} }}
    @page {{ size:A4 portrait; margin:10mm; }}
    @media print {{
      header, main, footer {{ display:none; }}
      body {{ background:#fff; color:#000; }}
      .print-calendar {{ display:block; }}
      .print-month {{ page-break-after:always; break-after:page; }}
      .print-month:last-child {{ page-break-after:auto; break-after:auto; }}
      .print-title {{ display:flex; justify-content:space-between; align-items:baseline; gap:8mm; margin:0 0 4mm; border-bottom:.4mm solid #000; padding-bottom:2mm; }}
      .print-title h1 {{ margin:0; color:#000; font-size:16pt; line-height:1.2; }}
      .print-title p {{ margin:0; color:#333; font-size:8pt; }}
      .print-grid {{ display:grid; grid-template-columns:repeat(7,1fr); border-top:.25mm solid #777; border-left:.25mm solid #777; }}
      .print-weekday {{ min-height:7mm; padding:1.5mm; border-right:.25mm solid #777; border-bottom:.25mm solid #777; background:#e9ece9; font-size:8pt; font-weight:700; text-align:center; }}
      .print-day {{ min-height:34mm; padding:1.5mm; border-right:.25mm solid #777; border-bottom:.25mm solid #777; overflow:hidden; }}
      .print-day.empty {{ background:#f4f4f4; }}
      .print-day-number {{ display:block; margin-bottom:1mm; font-size:8pt; font-weight:800; }}
      .print-cal-event {{ margin:0 0 1mm; padding-left:1.2mm; border-left:.7mm solid #555; font-size:6.8pt; line-height:1.25; overflow-wrap:anywhere; }}
      .print-cal-event strong, .print-cal-event span {{ display:block; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <a class="back" href="../index.html">一覧へ戻る</a>
      <h1>{escape(school['学校名'])}</h1>
      <div class="meta">
        <span class="pill">イベント {len(school_events)}件</span>
        {f'<span class="pill">過去問PDF {past_exam_count}件</span>' if not EXCLUDE_PAST_EXAMS else ''}
        <span class="pill">月数 {len(months)}ヶ月</span>
        <span class="pill">取得基準日 2026-04-30</span>
      </div>
    </div>
  </header>
  <main>
    <section class="panel">
      <p>{escape(school['住所'])}</p>
      <p>{escape(school['TEL'])}</p>
      <p>{escape(school['最寄駅・アクセス'])}</p>
      <div class="links">
        <a href="{escape(school['公式URL'])}" target="_blank" rel="noopener">公式サイト</a>
        <a href="{escape(school['説明会URL'])}" target="_blank" rel="noopener">説明会ページ</a>
        {f'<a href="{escape(school.get("入試要項URL"))}" target="_blank" rel="noopener">入試要項</a>' if school.get("入試要項URL") else ''}
        <button class="btn" type="button" onclick="window.print()">A4月別カレンダーを印刷</button>
      </div>
      {deviation_html}
      <div class="profile-grid">{basic_html}</div>
    </section>
    <section>
      <div class="section-title"><h2>学校詳細</h2><span>出典別偏差値・特色・学費など</span></div>
      <div class="detail-grid">
        {f'<section class="data-panel"><h2>特徴</h2>{feature_html}</section>' if feature_html else ''}
        {f'<section class="data-panel"><h2>学費</h2>{tuition_html}{summary_list(school.get("学費詳細", ""))}{summary_list(school.get("学費備考", ""))}</section>' if tuition_html or school.get("学費詳細") or school.get("学費備考") else ''}
        {f'<section class="data-panel"><h2>入試結果</h2>{exam_html}</section>' if exam_html else ''}
      </div>
      {detail_html or '<div class="empty">詳細情報は取得できませんでした。</div>'}
    </section>
    {past_exam_section_html}
    <section>
      <div class="section-title"><h2>月別カレンダー</h2><span>{len(school_events)}件</span></div>
      {calendar_sections}
    </section>
    <section>
      <div class="section-title"><h2>イベント一覧</h2><span>{len(school_events)}件</span></div>
      <div class="events">{event_rows}</div>
    </section>
  </main>
  <footer>掲載情報は取得時点のものです。参加前に各校の公式サイトで最新情報を確認してください。</footer>
  <div class="print-calendar">{print_sections}</div>
</body>
</html>
"""
        (SCHOOL_DIR / school_page_name(school)).write_text(page, encoding="utf-8")


def main() -> None:
    schools = read_csv(DATA_DIR / "schools.csv")
    events = sorted(read_csv(DATA_DIR / "events.csv"), key=sort_key)
    past_exams = read_csv_optional(DATA_DIR / "past_exams.csv")
    for school in schools:
        school["詳細ページ"] = f"schools/{school_page_name(school)}"
        school["過去問PDF件数"] = str(
            sum(1 for row in past_exams if row.get("study1_id") == school["study1_id"] and row.get("状態") == "取得済み")
        )
    embedded = (
        json.dumps({"schools": schools, "events": events, "pastExams": past_exams}, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )

    document = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>中学イベント情報まとめ</title>
  <style>
    :root {{
      --bg: #f5f7f3;
      --surface: #ffffff;
      --surface-2: #fafbf7;
      --ink: #14191c;
      --muted: #50595d;
      --line: #ccd5d1;
      --line-soft: #e3e9e6;
      --accent: #1e655c;
      --accent-2: #8a3434;
      --accent-3: #a06a18;
      --soft: #e3edea;
      --shadow: 0 14px 32px rgba(20, 30, 35, 0.10);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", "YuGothic", "Noto Sans JP", sans-serif;
      font-size: 16px;
      line-height: 1.7;
    }}

    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    header {{
      background: #173b3b;
      color: #fff;
      border-bottom: 5px solid #c28a35;
    }}

    .topbar {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 28px;
    }}

    .eyebrow {{
      margin: 0 0 10px;
      color: #c5dcd7;
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(28px, 4.4vw, 44px);
      line-height: 1.2;
      letter-spacing: 0;
    }}

    .header-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 22px;
    }}

    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 6px 14px;
      border: 1px solid rgba(255,255,255,0.28);
      border-radius: 999px;
      color: #f1faf7;
      background: rgba(255,255,255,0.10);
      font-size: 14px;
      font-weight: 600;
      white-space: nowrap;
    }}

    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 24px;
    }}

    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 5;
      display: grid;
      grid-template-columns: minmax(220px, 1.2fr) minmax(180px, 0.8fr) minmax(160px, 0.7fr) minmax(130px, 0.5fr);
      gap: 14px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255,255,255,0.97);
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }}

    label {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}

    input, select {{
      width: 100%;
      min-height: 44px;
      border: 1px solid #b9c4c0;
      border-radius: 8px;
      padding: 10px 12px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      font-size: 15px;
    }}

    input:focus, select:focus {{
      outline: 2px solid var(--accent);
      outline-offset: 1px;
      border-color: var(--accent);
    }}

    .summary-row {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 28px 0;
    }}

    .metric {{
      min-height: 96px;
      padding: 20px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--surface);
    }}

    .metric strong {{
      display: block;
      font-size: 32px;
      line-height: 1.1;
      color: var(--accent);
      font-weight: 800;
    }}

    .metric span {{
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 600;
    }}

    .section-title {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin: 44px 0 16px;
      padding-bottom: 10px;
      border-bottom: 2px solid var(--line);
    }}

    h2 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
      font-weight: 800;
    }}

    .section-title .muted, .section-title span.muted {{
      font-size: 14px;
    }}

    .muted {{ color: var(--muted); }}

    .calendar-panel {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--surface);
      overflow: hidden;
    }}

    .calendar-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-2);
    }}

    .calendar-head h3 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
      font-weight: 800;
    }}

    .calendar-head select {{
      max-width: 220px;
    }}

    .calendar-grid {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
    }}

    .weekday {{
      min-height: 38px;
      padding: 10px;
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: #e9f0ec;
      color: #3f4a4d;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-align: center;
    }}

    .weekday:nth-child(7n) {{ border-right: 0; }}

    .day {{
      min-height: 140px;
      padding: 10px;
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}

    .day:nth-child(7n) {{ border-right: 0; }}

    .day.is-empty {{
      background: #f3f5f2;
    }}

    .day-number {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      min-height: 30px;
      margin-bottom: 8px;
      border-radius: 6px;
      color: var(--ink);
      font-size: 14px;
      font-weight: 800;
    }}

    .day.has-events .day-number {{
      background: var(--accent);
      color: #fff;
    }}

    .cal-event {{
      display: block;
      margin: 6px 0;
      padding: 7px 9px;
      border-left: 3px solid var(--accent-2);
      border-radius: 5px;
      background: #f8edec;
      color: var(--ink);
      font-size: 13px;
      font-weight: 700;
      line-height: 1.4;
    }}

    .cal-event small {{
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-weight: 600;
      font-size: 12px;
    }}

    .print-actions {{
      display: flex;
      justify-content: flex-end;
      margin: 14px 0 0;
    }}

    .print-calendar {{
      display: none;
    }}

    .school-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-top: 16px;
    }}

    .school-table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      background: var(--surface);
      font-size: 14px;
    }}

    .school-table th,
    .school-table td {{
      padding: 13px 14px;
      border-bottom: 1px solid var(--line-soft);
      vertical-align: top;
      text-align: left;
    }}

    .school-table th {{
      background: #e9f0ec;
      color: #3f4a4d;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }}

    .school-table tr:last-child td {{
      border-bottom: 0;
    }}

    .school-table tbody tr:hover {{
      background: var(--surface-2);
    }}

    .dev {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 42px;
      min-height: 30px;
      padding: 0 8px;
      border-radius: 6px;
      background: #173b3b;
      color: #fff;
      font-size: 13px;
      font-weight: 800;
    }}

    .dev-list {{
      display: grid;
      gap: 6px;
      min-width: 140px;
    }}

    .dev-line {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
      min-height: 28px;
      padding: 5px 10px;
      border: 1px solid #cdded8;
      border-radius: 6px;
      background: #f4f9f6;
      color: var(--ink);
      font-size: 13px;
      font-weight: 800;
    }}

    .dev-line span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}

    .dev-line strong {{
      text-align: right;
      overflow-wrap: anywhere;
    }}

    .dev-line a {{
      color: inherit;
      text-decoration: none;
    }}

    .school {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      padding: 20px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--surface);
      transition: box-shadow 0.15s ease;
    }}

    .school:hover {{
      box-shadow: var(--shadow);
    }}

    .school h3 {{
      margin: 0 0 8px;
      font-size: 19px;
      letter-spacing: 0;
      font-weight: 800;
    }}

    .school-title {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }}

    .school-title h3 {{
      margin: 0;
    }}

    .school .dev-list {{
      margin: 10px 0;
      max-width: 340px;
    }}

    .school p {{
      margin: 6px 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .school-actions {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      align-items: stretch;
      min-width: 96px;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 8px 14px;
      border: 1px solid var(--accent);
      border-radius: 8px;
      color: var(--accent);
      background: #fff;
      font-size: 14px;
      font-weight: 700;
      text-decoration: none;
      transition: background 0.15s ease;
    }}

    .btn:hover {{
      background: var(--soft);
      text-decoration: none;
    }}

    .events {{
      display: grid;
      gap: 14px;
    }}

    .event {{
      display: grid;
      grid-template-columns: 160px minmax(0, 1fr) 170px;
      gap: 18px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--surface);
      transition: box-shadow 0.15s ease;
    }}

    .event:hover {{
      box-shadow: var(--shadow);
    }}

    .datebox {{
      display: grid;
      align-content: start;
      gap: 6px;
      min-height: 80px;
      padding: 14px;
      border-left: 4px solid var(--accent);
      background: var(--soft);
      border-radius: 8px;
    }}

    .datebox .date {{
      font-weight: 800;
      font-size: 17px;
      color: var(--ink);
    }}

    .datebox .time {{
      color: var(--muted);
      font-size: 14px;
      font-weight: 600;
    }}

    .event h3 {{
      margin: 0 0 8px;
      font-size: 19px;
      letter-spacing: 0;
      font-weight: 800;
      line-height: 1.4;
    }}

    .event-school {{
      margin: 0 0 6px;
      color: var(--accent-2);
      font-size: 14px;
      font-weight: 800;
    }}

    .event-school .dev {{
      min-width: 32px;
      min-height: 24px;
      margin-right: 8px;
      font-size: 12px;
      vertical-align: middle;
    }}

    .event-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0;
    }}

    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 12px;
      border-radius: 999px;
      background: #ece8de;
      color: #4a443a;
      font-size: 13px;
      font-weight: 700;
    }}

    .tag.reserve {{ background: #ffeacb; color: #84541a; }}
    .tag.start {{ background: #f6dada; color: var(--accent-2); }}
    .tag.precision {{ background: #e1e7ee; color: #3b4956; }}

    .note {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .event-actions {{
      display: grid;
      align-content: start;
      gap: 10px;
    }}

    .empty {{
      padding: 32px;
      border: 1px dashed #b3bfba;
      border-radius: 10px;
      background: #fff;
      color: var(--muted);
      font-size: 15px;
      text-align: center;
    }}

    footer {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 16px 24px 40px;
      color: var(--muted);
      font-size: 13px;
    }}

    @media (max-width: 900px) {{
      .toolbar, .summary-row, .school-grid, .event {{
        grid-template-columns: 1fr;
      }}
      .toolbar {{ position: static; }}
      .school {{ grid-template-columns: 1fr; }}
      .school-actions, .event-actions {{ display: flex; flex-wrap: wrap; }}
      .school-table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}

    @page {{
      size: A4 portrait;
      margin: 10mm;
    }}

    @media print {{
      body {{
        background: #fff;
        color: #000;
      }}

      header, main, footer {{
        display: none;
      }}

      .print-calendar {{
        display: block;
      }}

      .print-month {{
        page-break-after: always;
        break-after: page;
        width: 100%;
      }}

      .print-month:last-child {{
        page-break-after: auto;
        break-after: auto;
      }}

      .print-title {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 8mm;
        margin: 0 0 4mm;
        border-bottom: 0.4mm solid #000;
        padding-bottom: 2mm;
      }}

      .print-title h1 {{
        margin: 0;
        color: #000;
        font-size: 16pt;
        line-height: 1.2;
      }}

      .print-title p {{
        margin: 0;
        color: #333;
        font-size: 8pt;
      }}

      .print-grid {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        border-top: 0.25mm solid #777;
        border-left: 0.25mm solid #777;
      }}

      .print-weekday {{
        min-height: 7mm;
        padding: 1.5mm;
        border-right: 0.25mm solid #777;
        border-bottom: 0.25mm solid #777;
        background: #e9ece9;
        font-size: 8pt;
        font-weight: 700;
        text-align: center;
      }}

      .print-day {{
        min-height: 34mm;
        padding: 1.5mm;
        border-right: 0.25mm solid #777;
        border-bottom: 0.25mm solid #777;
        overflow: hidden;
      }}

      .print-day.empty {{
        background: #f4f4f4;
      }}

      .print-day-number {{
        display: block;
        margin-bottom: 1mm;
        font-size: 8pt;
        font-weight: 800;
      }}

      .print-event {{
        margin: 0 0 1mm;
        padding-left: 1.2mm;
        border-left: 0.7mm solid #555;
        font-size: 6.8pt;
        line-height: 1.25;
        overflow-wrap: anywhere;
      }}

      .print-event strong {{
        display: block;
        font-size: 6.8pt;
      }}

      .print-event span {{
        display: block;
        color: #333;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <p class="eyebrow">2026年度 学校説明会・イベント</p>
      <h1>中学イベント情報まとめ</h1>
      <div class="header-meta">
        <span class="pill">対象校 {len(schools)}校</span>
        <span class="pill">イベント {len(events)}件</span>
        <span class="pill">取得基準日 2026-04-30</span>
        <span class="pill">出典 中学受験スタディ</span>
      </div>
    </div>
  </header>

  <main>
    <section class="toolbar" aria-label="絞り込み">
      <label>検索
        <input id="q" type="search" placeholder="学校名・イベント名・備考で検索">
      </label>
      <label>学校
        <select id="schoolFilter"></select>
      </label>
      <label>場所
        <select id="placeFilter">
          <option value="">すべて</option>
          <option value="本校">本校</option>
          <option value="オンライン">オンライン</option>
        </select>
      </label>
      <label>表示
        <select id="limitFilter">
          <option value="all">全件</option>
          <option value="30">直近30件</option>
          <option value="60">直近60件</option>
        </select>
      </label>
    </section>

    <section class="summary-row" aria-label="集計">
      <div class="metric"><strong id="visibleCount">0</strong><span>表示中のイベント</span></div>
      <div class="metric"><strong id="schoolCount">{len(schools)}</strong><span>対象校</span></div>
      <div class="metric"><strong id="reserveCount">0</strong><span>予約URLあり</span></div>
      <div class="metric"><strong id="startCount">0</strong><span>予約開始情報あり</span></div>
    </section>

    <section>
      <div class="section-title">
        <h2>学校情報</h2>
        <span class="muted">出典別偏差値・種別・イベント数</span>
      </div>
      <div id="schools" class="school-grid"></div>
    </section>

    <section>
      <div class="section-title">
        <h2>月別カレンダー</h2>
        <span id="calendarSummary" class="muted"></span>
      </div>
      <div class="calendar-panel">
        <div class="calendar-head">
          <h3 id="calendarTitle">-</h3>
          <select id="monthFilter" aria-label="表示月"></select>
        </div>
        <div id="calendar" class="calendar-grid"></div>
      </div>
      <div class="print-actions">
        <button class="btn" type="button" onclick="window.print()">A4月別カレンダーを印刷</button>
      </div>
    </section>

    <section>
      <div class="section-title">
        <h2>イベント一覧</h2>
        <span id="eventSummary" class="muted"></span>
      </div>
      <div id="events" class="events"></div>
    </section>
  </main>

  <footer>
    掲載情報は取得時点のものです。参加前に各校の公式サイトで最新情報を確認してください。
  </footer>

  <div id="printCalendar" class="print-calendar" aria-hidden="true"></div>

  <script id="embedded-data" type="application/json">{embedded}</script>
  <script>
    const data = JSON.parse(document.getElementById('embedded-data').textContent);
    const schools = data.schools;
    const events = data.events;
    const pastExams = data.pastExams || [];

    const q = document.getElementById('q');
    const schoolFilter = document.getElementById('schoolFilter');
    const placeFilter = document.getElementById('placeFilter');
    const limitFilter = document.getElementById('limitFilter');
    const monthFilter = document.getElementById('monthFilter');
    const schoolRoot = document.getElementById('schools');
    const eventRoot = document.getElementById('events');
    const calendarRoot = document.getElementById('calendar');
    const printCalendarRoot = document.getElementById('printCalendar');
    const calendarTitle = document.getElementById('calendarTitle');
    const calendarSummary = document.getElementById('calendarSummary');
    const visibleCount = document.getElementById('visibleCount');
    const reserveCount = document.getElementById('reserveCount');
    const startCount = document.getElementById('startCount');
    const eventSummary = document.getElementById('eventSummary');

    function escapeHtml(value) {{
      return String(value || '').replace(/[&<>"']/g, char => ({{
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }}[char]));
    }}

    function link(url, label) {{
      if (!url) return '';
      return `<a class="btn" href="${{escapeHtml(url)}}" target="_blank" rel="noopener">${{label}}</a>`;
    }}

    function sourceLink(url, label) {{
      return url
        ? `<a href="${{escapeHtml(url)}}" target="_blank" rel="noopener">${{escapeHtml(label)}}</a>`
        : escapeHtml(label);
    }}

    function deviationRows(school) {{
      const rows = [
        ['スタディ', school['スタディ偏差値'], school['スタディ偏差値URL']],
        ['みんな', school['みんな偏差値2026'], school['みんな偏差値URL']],
        ['首都圏模試', school['首都圏模試偏差値'], school['首都圏模試URL']],
        ['四谷大塚', school['四谷大塚偏差値'], school['四谷大塚URL']]
      ].filter(row => row[1]);
      if (!rows.length) return '<span class="muted">未取得</span>';
      return `<div class="dev-list">${{rows.map(([label, value, url]) => `
        <div class="dev-line"><span>${{sourceLink(url, label)}}</span><strong>${{escapeHtml(value)}}</strong></div>
      `).join('')}}</div>`;
    }}

    function primaryDeviation(school) {{
      const yotsuya = school['四谷大塚A80偏差値'] || '';
      const nums = yotsuya.match(/\\d+/g);
      if (nums && nums.length) {{
        const values = nums.map(Number);
        const min = Math.min(...values);
        const max = Math.max(...values);
        return min === max ? `Y${{min}}` : `Y${{min}}-${{max}}`;
      }}
      return school['首都圏模試偏差値'] || school['みんな偏差値2026'] || school['スタディ偏差値'] || '';
    }}

    function schoolByName(name) {{
      return schools.find(school => school['学校名'] === name) || {{}};
    }}

    function eventCountForSchool(name) {{
      return events.filter(event => event['学校名'] === name).length;
    }}

    function pastExamCountForSchool(school) {{
      return Number(school['過去問PDF件数'] || 0);
    }}

    function normalize(value) {{
      return String(value || '').toLowerCase();
    }}

    function eventText(event) {{
      return [
        event['学校名'], event['開催日'], event['開催時間'], event['イベント名'],
        event['場所'], event['対象'], event['予約開始日・記載'], event['備考']
      ].join(' ');
    }}

    function parseEventDate(event) {{
      const match = String(event['開催日'] || '').match(/(\\d{{4}})\\/(\\d{{1,2}})\\/(\\d{{1,2}})/);
      if (!match) return null;
      return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    }}

    function monthKey(date) {{
      return `${{date.getFullYear()}}-${{String(date.getMonth() + 1).padStart(2, '0')}}`;
    }}

    function monthLabel(key) {{
      const [year, month] = key.split('-');
      return `${{year}}年${{Number(month)}}月`;
    }}

    function getFilteredEvents(applyLimit = false) {{
      const query = normalize(q.value);
      let filtered = events.filter(event => {{
        const schoolMatch = !schoolFilter.value || event['学校名'] === schoolFilter.value;
        const placeMatch = !placeFilter.value || event['場所'] === placeFilter.value;
        const textMatch = !query || normalize(eventText(event)).includes(query);
        return schoolMatch && placeMatch && textMatch;
      }});
      if (applyLimit && limitFilter.value !== 'all') filtered = filtered.slice(0, Number(limitFilter.value));
      return filtered;
    }}

    function renderSchools() {{
      schoolRoot.innerHTML = schools.map(school => `
        <article class="school">
          <div>
            <div class="school-title">
              <h3>${{escapeHtml(school['学校名'])}}</h3>
            </div>
            ${{deviationRows(school)}}
            <p>${{escapeHtml(school['住所'])}}</p>
            <p>${{escapeHtml([school['設置'], school['学校種別']].filter(Boolean).join(' / '))}} / イベント ${{eventCountForSchool(school['学校名'])}}件{'' if EXCLUDE_PAST_EXAMS else " / 過去問PDF ${{pastExamCountForSchool(school)}}件"}</p>
            <p>${{escapeHtml(school['TEL'])}}</p>
            <p>${{escapeHtml(school['最寄駅・アクセス'])}}</p>
          </div>
          <div class="school-actions">
            ${{link(school['詳細ページ'], '詳細')}}
            ${{link(school['公式URL'], '公式')}}
            ${{link(school['説明会URL'], '説明会')}}
          </div>
        </article>
      `).join('');
    }}

    function populateFilters() {{
      schoolFilter.innerHTML = '<option value="">すべて</option>' + schools
        .map(school => `<option value="${{escapeHtml(school['学校名'])}}">${{escapeHtml(school['学校名'])}}</option>`)
        .join('');

      const monthKeys = [...new Set(events.map(parseEventDate).filter(Boolean).map(monthKey))].sort();
      monthFilter.innerHTML = monthKeys
        .map(key => `<option value="${{key}}">${{monthLabel(key)}}</option>`)
        .join('');
    }}

    function renderEvents() {{
      const filtered = getFilteredEvents(true);

      visibleCount.textContent = filtered.length;
      reserveCount.textContent = filtered.filter(event => event['予約URL']).length;
      startCount.textContent = filtered.filter(event => event['予約開始日・記載']).length;
      eventSummary.textContent = `${{filtered.length}}件を表示`;

      if (!filtered.length) {{
        eventRoot.innerHTML = '<div class="empty">条件に一致するイベントはありません。</div>';
        return;
      }}

      eventRoot.innerHTML = filtered.map(event => {{
        const reserveStart = event['予約開始日・記載'];
        const precision = event['予約開始精度'];
        const note = event['備考'];
        const precisionLabel = {{
          exact: '開始日時あり',
          range: '受付期間あり',
          rule: '開始ルール',
          tentative: '予定',
          unknown: ''
        }}[precision] || '';
        return `
          <article class="event">
            <div class="datebox">
              <span class="date">${{escapeHtml(event['開催日'] || '随時')}}</span>
              <span class="time">${{escapeHtml(event['開催時間'] || '時間未掲載')}}</span>
            </div>
            <div>
              <p class="event-school"><span class="dev">${{escapeHtml(primaryDeviation(schoolByName(event['学校名'])) || '-')}}</span>${{escapeHtml(event['学校名'])}}</p>
              <h3>${{escapeHtml(event['イベント名'])}}</h3>
              <div class="event-meta">
                ${{event['場所'] ? `<span class="tag">${{escapeHtml(event['場所'])}}</span>` : ''}}
                ${{event['対象'] ? `<span class="tag">${{escapeHtml(event['対象'])}}</span>` : ''}}
                ${{event['予約'] ? `<span class="tag reserve">${{escapeHtml(event['予約'].replace(' 予約する', ''))}}</span>` : ''}}
                ${{reserveStart ? `<span class="tag start">${{escapeHtml(reserveStart)}}</span>` : ''}}
                ${{precisionLabel ? `<span class="tag precision">${{escapeHtml(precisionLabel)}}</span>` : ''}}
              </div>
              ${{note ? `<p class="note">${{escapeHtml(note)}}</p>` : ''}}
            </div>
            <div class="event-actions">
              ${{link(event['予約URL'], '予約ページ')}}
              ${{link(event['詳細URL'], '詳細')}}
              ${{link(event['予約開始根拠URL'], '開始日根拠')}}
            </div>
          </article>
        `;
      }}).join('');
    }}

    function renderCalendar() {{
      const key = monthFilter.value;
      if (!key) {{
        calendarRoot.innerHTML = '<div class="empty">表示できる月がありません。</div>';
        calendarTitle.textContent = '-';
        calendarSummary.textContent = '';
        return;
      }}

      const [year, month] = key.split('-').map(Number);
      const monthEvents = getFilteredEvents(false).filter(event => {{
        const date = parseEventDate(event);
        return date && monthKey(date) === key;
      }});
      const byDay = new Map();
      for (const event of monthEvents) {{
        const date = parseEventDate(event);
        const day = date.getDate();
        if (!byDay.has(day)) byDay.set(day, []);
        byDay.get(day).push(event);
      }}

      const first = new Date(year, month - 1, 1);
      const last = new Date(year, month, 0);
      const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
      const cells = weekdays.map(day => `<div class="weekday">${{day}}</div>`);
      for (let i = 0; i < first.getDay(); i++) cells.push('<div class="day is-empty"></div>');
      for (let day = 1; day <= last.getDate(); day++) {{
        const items = byDay.get(day) || [];
        cells.push(`
          <div class="day ${{items.length ? 'has-events' : ''}}">
            <span class="day-number">${{day}}</span>
            ${{items.map(event => `
              <a class="cal-event" href="${{escapeHtml(event['詳細URL'] || event['予約URL'] || '#')}}" target="_blank" rel="noopener">
                ${{escapeHtml(event['イベント名'])}}
                <small>${{escapeHtml(event['学校名'])}}${{event['開催時間'] ? ' / ' + escapeHtml(event['開催時間']) : ''}}</small>
              </a>
            `).join('')}}
          </div>
        `);
      }}
      const remainder = cells.length % 7;
      if (remainder) {{
        for (let i = remainder; i < 7; i++) cells.push('<div class="day is-empty"></div>');
      }}

      calendarTitle.textContent = monthLabel(key);
      calendarSummary.textContent = `${{monthEvents.length}}件`;
      calendarRoot.innerHTML = cells.join('');
    }}

    function renderPrintCalendar() {{
      const monthKeys = [...new Set(events.map(parseEventDate).filter(Boolean).map(monthKey))].sort();
      const weekdays = ['日', '月', '火', '水', '木', '金', '土'];

      printCalendarRoot.innerHTML = monthKeys.map(key => {{
        const [year, month] = key.split('-').map(Number);
        const monthEvents = events.filter(event => {{
          const date = parseEventDate(event);
          return date && monthKey(date) === key;
        }});
        const byDay = new Map();
        for (const event of monthEvents) {{
          const date = parseEventDate(event);
          const day = date.getDate();
          if (!byDay.has(day)) byDay.set(day, []);
          byDay.get(day).push(event);
        }}

        const first = new Date(year, month - 1, 1);
        const last = new Date(year, month, 0);
        const cells = weekdays.map(day => `<div class="print-weekday">${{day}}</div>`);
        for (let i = 0; i < first.getDay(); i++) cells.push('<div class="print-day empty"></div>');
        for (let day = 1; day <= last.getDate(); day++) {{
          const items = byDay.get(day) || [];
          cells.push(`
            <div class="print-day">
              <span class="print-day-number">${{day}}</span>
              ${{items.map(event => `
                <div class="print-event">
                  <strong>${{escapeHtml(event['イベント名'])}}</strong>
                  <span>${{escapeHtml(event['学校名'])}}${{event['開催時間'] ? ' / ' + escapeHtml(event['開催時間']) : ''}}</span>
                  ${{event['予約開始日・記載'] ? `<span>${{escapeHtml(event['予約開始日・記載'])}}</span>` : ''}}
                </div>
              `).join('')}}
            </div>
          `);
        }}
        const remainder = cells.length % 7;
        if (remainder) {{
          for (let i = remainder; i < 7; i++) cells.push('<div class="print-day empty"></div>');
        }}

        return `
          <section class="print-month">
            <div class="print-title">
              <h1>${{monthLabel(key)}} 中学イベントカレンダー</h1>
              <p>${{monthEvents.length}}件 / 取得基準日 2026-04-30</p>
            </div>
            <div class="print-grid">${{cells.join('')}}</div>
          </section>
        `;
      }}).join('');
    }}

    [q, schoolFilter, placeFilter, limitFilter].forEach(control => {{
      control.addEventListener('input', renderEvents);
      control.addEventListener('change', renderEvents);
    }});

    [q, schoolFilter, placeFilter].forEach(control => {{
      control.addEventListener('input', renderCalendar);
      control.addEventListener('change', renderCalendar);
    }});
    monthFilter.addEventListener('change', renderCalendar);

    renderSchools();
    populateFilters();
    renderCalendar();
    renderPrintCalendar();
    renderEvents();
  </script>
</body>
</html>
"""
    OUTPUT.write_text(document, encoding="utf-8")
    write_school_pages(schools, events, past_exams)
    print(OUTPUT)


if __name__ == "__main__":
    main()
