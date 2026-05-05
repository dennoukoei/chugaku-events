#!/usr/bin/env python3
import csv
import re
import shutil
import sqlite3
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "past_exams"
DATA_DIR = ROOT / "data"
ZEN_COOKIE_DB = Path.home() / "Library/Application Support/zen/Profiles/3c09d2c2.Default (release)/cookies.sqlite"
BASE = "https://www.yotsuyaotsuka.com"
UA = "Mozilla/5.0"

YOTSUYA_KAKOMON_CLASSES = {
    "B13P046": [
        ("渋谷教育学園渋谷中学校", "第1回", "24"),
        ("渋谷教育学園渋谷中学校", "第2回", "707"),
    ],
    "B13P098": [
        ("東洋英和女学院中学部", "A日程", "31"),
        ("東洋英和女学院中学部", "B日程", "679"),
    ],
    "B13N007": [],
    "B13N005": [("東京学芸大学附属世田谷中学校", "", "7")],
    "B13N001": [("お茶の水女子大学附属中学校", "", "17")],
    "B13P113": [("富士見丘中学校", "", "570")],
    "B13P056": [("実践女子学園中学校", "", "141")],
    "B13P111": [("広尾学園中学校", "", "199")],
    "B13P089": [("東京女学館中学校", "", "250")],
    "B13P115": [("普連土学園中学校", "", "55")],
    "B13P061": [("女子学院中学校", "", "8")],
}

SUBJECTS = {
    "kokugo": "国語",
    "sansu": "算数",
    "rika": "理科",
    "shakai": "社会",
    "eigo": "英語",
}

KINDS = {
    "mondai": "問題",
    "kaito": "解答",
}


def cookie_header() -> str:
    if not ZEN_COOKIE_DB.exists():
        return ""
    tmp = Path(tempfile.gettempdir()) / "zen_yotsuya_cookies.sqlite"
    shutil.copy2(ZEN_COOKIE_DB, tmp)
    con = sqlite3.connect(tmp)
    values = []
    for name, value in con.execute(
        "select name,value from moz_cookies where host like '%yotsuyaotsuka.com%'"
    ):
        values.append(f"{name}={value}")
    return "; ".join(values)


def fetch(url: str, cookie: str) -> bytes:
    headers = {"User-Agent": UA}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=60).read()


def safe_part(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", "_", value.strip())
    return value or "default"


def collect_links(class_id: str, cookie: str) -> list[str]:
    url = f"{BASE}/chugaku_kakomon/system/classes.php?id={class_id}"
    html = fetch(url, cookie).decode("utf-8", "replace")
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if f"/uploadPdfs/{class_id}/" in href and href.endswith(".pdf"):
            links.append(urllib.parse.urljoin(BASE, href))
    return sorted(set(links))


def parse_pdf_url(url: str) -> tuple[str, str, str]:
    match = re.search(r"/uploadPdfs/\d+/(\d{4})/([a-z]+)-([a-z]+)\.pdf$", url)
    if not match:
        return "", "", ""
    year, subject_key, kind_key = match.groups()
    return year, SUBJECTS.get(subject_key, subject_key), KINDS.get(kind_key, kind_key)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    cookie = cookie_header()
    rows = []
    for study1_id, classes in YOTSUYA_KAKOMON_CLASSES.items():
        if not classes:
            rows.append(
                {
                    "study1_id": study1_id,
                    "学校名": "",
                    "入試区分": "",
                    "四谷過去問ID": "",
                    "年度": "",
                    "科目": "",
                    "種別": "",
                    "ファイル": "",
                    "元URL": "",
                    "状態": "掲載なし",
                }
            )
            continue
        for school_name, exam_label, class_id in classes:
            links = collect_links(class_id, cookie)
            if not links:
                rows.append(
                    {
                        "study1_id": study1_id,
                        "学校名": school_name,
                        "入試区分": exam_label,
                        "四谷過去問ID": class_id,
                        "年度": "",
                        "科目": "",
                        "種別": "",
                        "ファイル": "",
                        "元URL": f"{BASE}/chugaku_kakomon/system/classes.php?id={class_id}",
                        "状態": "掲載なし",
                    }
                )
                continue
            for url in links:
                year, subject, kind = parse_pdf_url(url)
                filename = "_".join(
                    part
                    for part in [
                        study1_id,
                        safe_part(school_name),
                        safe_part(exam_label),
                        year,
                        safe_part(subject),
                        safe_part(kind),
                    ]
                    if part
                ) + ".pdf"
                target = OUT_DIR / filename
                if not target.exists() or target.stat().st_size == 0:
                    target.write_bytes(fetch(url, cookie))
                rows.append(
                    {
                        "study1_id": study1_id,
                        "学校名": school_name,
                        "入試区分": exam_label,
                        "四谷過去問ID": class_id,
                        "年度": year,
                        "科目": subject,
                        "種別": kind,
                        "ファイル": f"past_exams/{filename}",
                        "元URL": url,
                        "状態": "取得済み" if target.exists() and target.stat().st_size > 0 else "取得失敗",
                    }
                )
    out_csv = DATA_DIR / "past_exams.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["study1_id", "学校名", "入試区分", "四谷過去問ID", "年度", "科目", "種別", "ファイル", "元URL", "状態"],
        )
        writer.writeheader()
        writer.writerows(rows)
    downloaded = sum(1 for row in rows if row["状態"] == "取得済み")
    missing = sum(1 for row in rows if row["状態"] == "掲載なし")
    print(f"past_exams={downloaded} missing_entries={missing}")


if __name__ == "__main__":
    main()
