#!/usr/bin/env python3
import csv
from datetime import date
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup


SCHOOLS = {
    "渋谷教育学園渋谷中学校": "B13P046",
    "東洋英和女学院中学部": "B13P098",
    "東京大学教育学部附属中等教育学校": "B13N007",
    "東京学芸大学附属世田谷中学校": "B13N005",
    "お茶の水女子大学附属中学校": "B13N001",
    "富士見丘中学校": "B13P113",
    "実践女子学園中学校": "B13P056",
    "広尾学園中学校": "B13P111",
    "東京女学館中学校": "B13P089",
    "普連土学園中学校": "B13P115",
}

MINKOU_URLS = {
    "B13P046": "https://www.minkou.jp/junior/school/7736/",
    "B13P098": "https://www.minkou.jp/junior/school/7506/",
    "B13N007": "https://www.minkou.jp/junior/school/7758/",
    "B13N005": "https://www.minkou.jp/junior/school/7698/",
    "B13N001": "https://www.minkou.jp/junior/school/7548/",
    "B13P113": "https://www.minkou.jp/junior/school/7731/",
    "B13P056": "https://www.minkou.jp/junior/school/7738/",
    "B13P111": "https://www.minkou.jp/junior/school/7497/",
    "B13P089": "https://www.minkou.jp/junior/school/7740/",
    "B13P115": "https://www.minkou.jp/junior/school/7504/",
}

SYUTOKEN_CODES = {
    "B13P046": "1159",
    "B13P098": "1222",
    "B13N007": "1808",
    "B13N005": "1806",
    "B13N001": "1801",
    "B13P113": "1241",
    "B13P056": "1155",
    "B13P111": "1239",
    "B13P089": "1209",
    "B13P115": "1244",
}

YOTSUYA_CODES = {
    "B13P046": "292",
    "B13P098": "512",
    "B13N007": "494",
    "B13N005": "484",
    "B13N001": "100",
    "B13P113": "647",
    "B13P056": "285",
    "B13P111": "313",
    "B13P089": "490",
    "B13P115": "653",
}

ACCESS_OVERRIDES = {
    "渋谷教育学園渋谷中学校": "各線「渋谷駅」より徒歩7分、千代田線「明治神宮前駅」より徒歩8分",
    "東洋英和女学院中学部": "都営大江戸線「麻布十番駅」7番出口より徒歩5分、東京メトロ南北線「麻布十番駅」5a番出口より徒歩7分、東京メトロ日比谷線「六本木駅」3番出口より徒歩7分、東京メトロ千代田線「乃木坂駅」3番出口より徒歩15分",
    "東京大学教育学部附属中等教育学校": "京王線「幡ヶ谷駅」北口より徒歩15分、丸ノ内線「中野新橋駅」より徒歩10分、都営大江戸線「西新宿五丁目駅」より徒歩15分、バス「東大付属」下車徒歩1分ほか",
    "東京学芸大学附属世田谷中学校": "東急田園都市線「駒沢大学駅」より徒歩25分、渋谷駅・自由が丘駅・等々力駅・用賀駅からバス「深沢不動前」「学芸附属中学校」「付属世田谷中学校前」下車徒歩4〜10分",
    "お茶の水女子大学附属中学校": "東京メトロ丸ノ内線「茗荷谷駅」より徒歩7分、東京メトロ有楽町線「護国寺駅」より徒歩13分、バス「大塚2丁目」下車徒歩1分",
    "富士見丘中学校": "京王線「笹塚駅」より徒歩5分、バス「笹塚中学校」下車徒歩3分",
    "実践女子学園中学校": "各線「渋谷駅」より徒歩10分、各線「表参道駅」B1より徒歩12分",
    "広尾学園中学校": "東京メトロ日比谷線「広尾駅」4番出口すぐ、バス「日赤医療センター下・広尾学園前」下車すぐ",
    "東京女学館中学校": "日比谷線「広尾駅」4番より徒歩12分、各線「渋谷駅」よりバス10分、各線「恵比寿駅」よりバス8分、バス「東京女学館前」下車",
    "普連土学園中学校": "都営浅草線「三田駅」より徒歩7分、JR「田町駅」より徒歩8分",
}

UA = {"User-Agent": "Mozilla/5.0"}
AS_OF = date(2026, 4, 30)
DEVIATION_CACHE: Optional[dict[str, dict[str, str]]] = None
SUPPLEMENTAL_EVENTS = [
    {
        "学校名": "渋谷教育学園渋谷中学校",
        "開催日": "2026/9/11(金)",
        "開催時間": "12:45～15:30",
        "イベント名": "飛龍祭",
        "場所": "本校",
        "対象": "小学校6年生または5年生・保護者",
        "予約": "要予約",
        "予約開始日・記載": "Web申込開始日時など詳細は2026年7月中旬を目途に公式ページで案内予定",
        "備考": "Webによる事前予約制。1組2名まで。上履き不要。",
        "予約URL": "https://mirai-compass.net/usr/shibusbj/event/evtIndex.jsf",
        "詳細URL": "https://www.shibushibu.jp/admission/event_schedule.html",
    },
    {
        "学校名": "渋谷教育学園渋谷中学校",
        "開催日": "2026/9/12(土)",
        "開催時間": "9:00～12:00",
        "イベント名": "飛龍祭 第1部",
        "場所": "本校",
        "対象": "小学校6年生または5年生・保護者",
        "予約": "要予約",
        "予約開始日・記載": "Web申込開始日時など詳細は2026年7月中旬を目途に公式ページで案内予定",
        "備考": "完全入れ替え制。Webによる事前予約制。1組2名まで。上履き不要。",
        "予約URL": "https://mirai-compass.net/usr/shibusbj/event/evtIndex.jsf",
        "詳細URL": "https://www.shibushibu.jp/admission/event_schedule.html",
    },
    {
        "学校名": "渋谷教育学園渋谷中学校",
        "開催日": "2026/9/12(土)",
        "開催時間": "12:45～15:30",
        "イベント名": "飛龍祭 第2部",
        "場所": "本校",
        "対象": "小学校6年生または5年生・保護者",
        "予約": "要予約",
        "予約開始日・記載": "Web申込開始日時など詳細は2026年7月中旬を目途に公式ページで案内予定",
        "備考": "完全入れ替え制。Webによる事前予約制。1組2名まで。上履き不要。",
        "予約URL": "https://mirai-compass.net/usr/shibusbj/event/evtIndex.jsf",
        "詳細URL": "https://www.shibushibu.jp/admission/event_schedule.html",
    },
    {
        "学校名": "渋谷教育学園渋谷中学校",
        "開催日": "2026/10/17(土)",
        "開催時間": "14:15～15:30",
        "イベント名": "第1回 学校説明会",
        "場所": "本校",
        "対象": "小学校6年生・保護者",
        "予約": "要予約",
        "予約開始日・記載": "詳細は2026年9月中旬を目途に公式ページで案内予定",
        "備考": "開場13:45。入試問題の傾向と対策、帰国生入試に関する説明を予定。Webによる事前予約制。1組2名まで。上履き不要。",
        "予約URL": "https://mirai-compass.net/usr/shibusbj/event/evtIndex.jsf",
        "詳細URL": "https://www.shibushibu.jp/admission/event_schedule.html",
    },
    {
        "学校名": "渋谷教育学園渋谷中学校",
        "開催日": "2026/11/21(土)",
        "開催時間": "14:15～15:30",
        "イベント名": "第2回 学校説明会",
        "場所": "本校",
        "対象": "小学校4年生以上・保護者",
        "予約": "要予約",
        "予約開始日・記載": "詳細は2026年9月中旬を目途に公式ページで案内予定",
        "備考": "開場13:45。入試問題の傾向と対策、帰国生入試に関する説明を予定。Webによる事前予約制。1組2名まで。上履き不要。",
        "予約URL": "https://mirai-compass.net/usr/shibusbj/event/evtIndex.jsf",
        "詳細URL": "https://www.shibushibu.jp/admission/event_schedule.html",
    },
    {
        "学校名": "東京大学教育学部附属中等教育学校",
        "開催日": "2026/6/13(土)",
        "開催時間": "10:00～11:30",
        "イベント名": "学校説明会 第1回 第1部",
        "場所": "本校",
        "対象": "2027年度に入学を希望される小学校5・6年生の家庭",
        "予約": "要予約",
        "予約開始日・記載": "申し込み開始：2026年 5月13日（水）17:00 〜 6月10日（水）17:00",
        "備考": "対面開催。定員各600名。第1部と第2部は同内容。体育館での全体会後、各教室・案内ツアーに分かれて学校生活を案内。",
        "予約URL": "https://mirai-compass.net/usr/tkuvkgfj/event/evtIndex.jsf",
        "詳細URL": "https://www.hs.p.u-tokyo.ac.jp/forentrance/guidance",
    },
    {
        "学校名": "東京大学教育学部附属中等教育学校",
        "開催日": "2026/6/13(土)",
        "開催時間": "13:30～15:00",
        "イベント名": "学校説明会 第1回 第2部",
        "場所": "本校",
        "対象": "2027年度に入学を希望される小学校5・6年生の家庭",
        "予約": "要予約",
        "予約開始日・記載": "申し込み開始：2026年 5月13日（水）17:00 〜 6月10日（水）17:00",
        "備考": "対面開催。定員各600名。第1部と第2部は同内容。体育館での全体会後、各教室・案内ツアーに分かれて学校生活を案内。",
        "予約URL": "https://mirai-compass.net/usr/tkuvkgfj/event/evtIndex.jsf",
        "詳細URL": "https://www.hs.p.u-tokyo.ac.jp/forentrance/guidance",
    },
    {
        "学校名": "東京大学教育学部附属中等教育学校",
        "開催日": "2026/10/3(土)",
        "開催時間": "10:00～11:30",
        "イベント名": "学校説明会 第2回 第1部",
        "場所": "本校",
        "対象": "2027年度に入学を希望される小学校5・6年生の家庭",
        "予約": "要予約",
        "予約開始日・記載": "申し込み開始：2026年 9月初旬（予定）",
        "備考": "対面開催。定員各600名予定。第1部と第2部は同内容。体育館での全体会後、各教室・案内ツアーに分かれて学校生活を案内。",
        "予約URL": "https://mirai-compass.net/usr/tkuvkgfj/event/evtIndex.jsf",
        "詳細URL": "https://www.hs.p.u-tokyo.ac.jp/forentrance/guidance",
    },
    {
        "学校名": "東京大学教育学部附属中等教育学校",
        "開催日": "2026/10/3(土)",
        "開催時間": "13:30～15:00",
        "イベント名": "学校説明会 第2回 第2部",
        "場所": "本校",
        "対象": "2027年度に入学を希望される小学校5・6年生の家庭",
        "予約": "要予約",
        "予約開始日・記載": "申し込み開始：2026年 9月初旬（予定）",
        "備考": "対面開催。定員各600名予定。第1部と第2部は同内容。体育館での全体会後、各教室・案内ツアーに分かれて学校生活を案内。",
        "予約URL": "https://mirai-compass.net/usr/tkuvkgfj/event/evtIndex.jsf",
        "詳細URL": "https://www.hs.p.u-tokyo.ac.jp/forentrance/guidance",
    },
]

RESERVATION_RULES = [
    # 渋谷教育学園渋谷中学校
    ("渋谷教育学園渋谷中学校", "2026/9/11", "飛龍祭", "Web申込開始日時など詳細は2026年7月中旬を目途に公式ページで案内予定", "tentative", "https://www.shibushibu.jp/admission/event_schedule.html"),
    ("渋谷教育学園渋谷中学校", "2026/9/12", "飛龍祭", "Web申込開始日時など詳細は2026年7月中旬を目途に公式ページで案内予定", "tentative", "https://www.shibushibu.jp/admission/event_schedule.html"),
    ("渋谷教育学園渋谷中学校", "2026/10/17", "学校説明会", "詳細は2026年9月中旬を目途に公式ページで案内予定", "tentative", "https://www.shibushibu.jp/admission/event_schedule.html"),
    ("渋谷教育学園渋谷中学校", "2026/11/21", "学校説明会", "詳細は2026年9月中旬を目途に公式ページで案内予定", "tentative", "https://www.shibushibu.jp/admission/event_schedule.html"),
    # 東京大学教育学部附属中等教育学校
    ("東京大学教育学部附属中等教育学校", "2026/6/13", "", "申し込み開始：2026年5月13日（水）17:00 〜 6月10日（水）17:00", "range", "https://www.hs.p.u-tokyo.ac.jp/forentrance/guidance"),
    ("東京大学教育学部附属中等教育学校", "2026/10/3", "", "申し込み開始：2026年9月初旬（予定）", "tentative", "https://www.hs.p.u-tokyo.ac.jp/forentrance/guidance"),
    # 東洋英和女学院中学部
    ("東洋英和女学院中学部", "2026/5/23", "学校説明会", "予約開始：2026年4月25日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2026/6/27", "オープンスクール", "予約開始：2026年5月30日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2026/9/5", "学校説明会", "予約開始：2026年8月8日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2026/10/23", "楓祭", "予約開始：2026年10月3日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2026/10/24", "楓祭", "予約開始：2026年10月3日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2026/11/14", "入試説明会", "予約開始：2026年10月17日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2026/12/12", "クリスマス音楽会", "予約開始：2026年11月14日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2026/12/26", "ミニ学校説明会", "予約開始：2026年11月28日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    ("東洋英和女学院中学部", "2027/2/20", "キックオフ説明会", "予約開始：2027年1月23日（土）", "exact", "https://www.toyoeiwa.ac.jp/chu-ko/event/schedule/"),
    # 富士見丘中学校
    ("富士見丘中学校", "2026/6/6", "", "予約受付：2026年5月6日（水）〜6月3日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/7/12", "", "予約受付：2026年6月12日（金）〜7月9日（木）", "range", "https://www.fujimigaoka.ac.jp/exam/returnees/briefing"),
    ("富士見丘中学校", "2026/7/19", "", "予約受付：2026年6月19日（金）〜7月15日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/8/20", "", "予約受付：2026年7月20日（月）〜8月17日（月）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/8/21", "", "予約受付：2026年7月20日（月）〜8月17日（月）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/9/26", "", "予約受付：2026年8月26日（水）〜9月23日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/9/27", "", "予約受付：2026年8月26日（水）〜9月23日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/10/3", "", "予約受付：2026年9月3日（木）〜9月30日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/returnees/briefing"),
    ("富士見丘中学校", "2026/10/17", "", "予約受付：2026年9月17日（木）〜10月14日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/11/23", "", "予約受付：2026年10月23日（金）〜11月18日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/12/5", "", "予約受付：2026年11月5日（木）〜12月2日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2026/12/26", "", "予約受付：2026年11月26日（木）〜12月23日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    ("富士見丘中学校", "2027/1/11", "", "予約受付：2026年12月11日（金）〜2027年1月6日（水）", "range", "https://www.fujimigaoka.ac.jp/exam/junior/briefing"),
    # 実践女子学園中学校
    ("実践女子学園中学校", "", "", "申込み開始は、原則1ヶ月前の平日20:00〜、土日祝は10:00〜", "rule", "https://hs.jissen.ac.jp/admission/open_school/index.html"),
    # 広尾学園中学校
    ("広尾学園中学校", "2026/5/30", "", "申込開始予定日：2026年5月8日（金）10:00〜", "exact", "https://www.hiroogakuen.ed.jp/junior/j_setumeikai.html"),
    ("広尾学園中学校", "2026/6/13", "", "申込開始予定日：2026年5月22日（金）10:00〜", "exact", "https://www.hiroogakuen.ed.jp/junior/j_setumeikai.html"),
    ("広尾学園中学校", "2026/9/5", "", "申込開始予定日：2026年8月7日（金）10:00〜", "exact", "https://www.hiroogakuen.ed.jp/junior/j_setumeikai.html"),
    ("広尾学園中学校", "2026/10/17", "", "申込開始予定日：2026年9月25日（金）10:00〜", "exact", "https://www.hiroogakuen.ed.jp/junior/j_setumeikai.html"),
    ("広尾学園中学校", "2026/11/8", "", "申込開始予定日：2026年10月16日（金）10:00〜", "exact", "https://www.hiroogakuen.ed.jp/junior/j_setumeikai.html"),
    ("広尾学園中学校", "2026/12/12", "", "申込開始予定日：2026年11月20日（金）10:00〜", "exact", "https://www.hiroogakuen.ed.jp/junior/j_setumeikai.html"),
    # 東京女学館中学校
    ("東京女学館中学校", "2026/5/9", "", "予約受付開始：2026年4月9日（木）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/6/13", "", "予約受付開始：2026年5月13日（水）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/7/11", "", "予約受付開始：2026年6月11日（木）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/7/18", "", "予約受付開始：2026年6月18日（木）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/8/29", "", "申し込み開始：2026年8月5日（水）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/10/3", "", "予約受付開始：2026年9月3日（木）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/10/24", "", "予約受付開始：2026年9月24日（木）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/11/7", "", "予約受付開始：2026年10月7日（水）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/11/8", "", "予約受付開始：2026年10月7日（水）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/11/14", "", "予約受付開始：2026年10月14日（水）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2026/12/12", "", "予約受付開始：2026年11月12日（木）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2027/1/9", "", "予約受付開始：2026年12月9日（水）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    ("東京女学館中学校", "2027/3/13", "", "申し込み開始：2027年2月13日（土）10:00〜", "exact", "https://tjk.jp/mh/examinee/briefing/"),
    # 普連土学園中学校
    ("普連土学園中学校", "2026/5/", "生徒による校舎案内ツアー", "予約受付開始：2026年4月25日（土）13:00〜", "exact", "https://www.friends.ac.jp/admission-events/22372/"),
    ("普連土学園中学校", "", "", "要予約イベントの予約受付開始日時は3週間前を目安にトップページへ掲示", "rule", "https://www.friends.ac.jp/examination/event.html"),
]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def clean_text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def parse_kv_table(table) -> dict[str, str]:
    if not table:
        return {}
    cells = table.select("th,td")
    values = {}
    for i in range(0, len(cells) - 1, 2):
        key = clean_text(cells[i]).strip("：:")
        value = clean_text(cells[i + 1])
        if key:
            values[key] = value
    return values


def compact(value: str) -> str:
    return " ".join((value or "").split())


def table_to_text(table) -> str:
    if not table:
        return ""
    rows = []
    for tr in table.select("tr"):
        cells = [compact(clean_text(cell)) for cell in tr.select("th,td")]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(" / ".join(cells))
    return " | ".join(rows)


def deviation_map() -> dict[str, dict[str, str]]:
    global DEVIATION_CACHE
    if DEVIATION_CACHE is not None:
        return DEVIATION_CACHE
    soup = BeautifulSoup(fetch("https://www.study1.jp/kanto/list/deviation.html"), "html.parser")
    result = {}
    for outer in soup.select("tr"):
        dev_cell = outer.select_one("td.dev")
        nested = outer.find("table")
        if not dev_cell or not nested:
            continue
        deviation = compact(clean_text(dev_cell))
        for tr in nested.select("tr"):
            anchor = tr.select_one("td.name a[href]")
            if not anchor:
                continue
            match = re.search(r"/school/([^/]+)/", anchor["href"])
            if not match:
                continue
            icons = [img.get("alt", "") for img in tr.select("td.type img[alt]")]
            result[match.group(1)] = {
                "偏差値": deviation,
                "設置": " / ".join([icon for icon in icons if "中学" in icon or "一貫" in icon]),
                "学校種別": " / ".join([icon for icon in icons if "校" in icon and "中学" not in icon]),
                "偏差値一覧地域": compact(clean_text(tr.select_one("td.ad"))),
            }
    DEVIATION_CACHE = result
    return result


def extract_top_profile(soup: BeautifulSoup, sid: str) -> dict[str, str]:
    info = deviation_map().get(sid, {})
    if "偏差値" in info:
        info["スタディ偏差値"] = info.pop("偏差値")
        info["スタディ偏差値URL"] = "https://www.study1.jp/kanto/list/deviation.html"
    headline = compact(clean_text(soup.select_one("#main h2")))
    point = ""
    point_heading = soup.find(string=re.compile("スタディが注目する"))
    if point_heading:
        parent = point_heading.find_parent()
        box = parent.find_parent() if parent else None
        point = compact(clean_text(box.find_next("p"))) if box and box.find_next("p") else ""

    student_total = ""
    capa = soup.select_one("#capa")
    if capa:
        values = [compact(clean_text(li)) for li in capa.select("#capa-st li")]
        student_total = " / ".join(values)

    tuition_summary = table_to_text(soup.select_one("#tuition table"))
    feature_summary = table_to_text(soup.select_one("#feature table"))
    uniform = ""
    uniform_heading = soup.find("h3", string=re.compile("制服"))
    if uniform_heading:
        uniform = compact(clean_text(uniform_heading.find_next("p")))

    news = []
    for item in soup.select("#schooltopix-box li")[:5]:
        news.append(compact(clean_text(item)))

    special = []
    for item in soup.select(".sp-others_box")[:5]:
        special.append(compact(clean_text(item)))

    return {
        **info,
        "キャッチコピー": headline,
        "注目ポイント": point,
        "生徒総数": student_total,
        "学費サマリー": tuition_summary,
        "特徴サマリー": feature_summary,
        "制服": uniform,
        "学校からのお知らせ": " | ".join(news),
        "スクール特集": " | ".join(special),
    }


def extract_minkou_deviation(sid: str) -> dict[str, str]:
    url = MINKOU_URLS.get(sid, "")
    if not url:
        return {}
    soup = BeautifulSoup(fetch(url), "html.parser")
    text_value = soup.get_text("\n", strip=True)
    match = re.search(r"2026年度\s*偏差値\s*\n\s*(\d+\s*-\s*\d+|\d+)", text_value)
    if not match:
        match = re.search(r"偏差値[：:\s]+(\d+\s*-\s*\d+|\d+)", text_value)
    return {
        "みんな偏差値2026": compact(match.group(1)) if match else "",
        "みんな偏差値URL": url,
    }


def extract_syutoken_deviation(sid: str) -> dict[str, str]:
    code = SYUTOKEN_CODES.get(sid, "")
    if not code:
        return {}
    url = f"https://www.syutoken-mosi.co.jp/db/school/?code={code}&p=3"
    text_value = BeautifulSoup(fetch(url), "html.parser").get_text("\n", strip=True)
    values = {"男": [], "女": []}
    for gender, score in re.findall(r"([男女])：\s*(\d+)", text_value):
        values[gender].append(int(score))
    parts = []
    for gender in ["男", "女"]:
        scores = values[gender]
        if not scores:
            continue
        parts.append(f"{gender}{min(scores)}" if min(scores) == max(scores) else f"{gender}{min(scores)}-{max(scores)}")
    if not parts:
        top_url = f"https://www.syutoken-mosi.co.jp/db/school/?code={code}"
        text_value = BeautifulSoup(fetch(top_url), "html.parser").get_text("\n", strip=True)
        match = re.search(r"偏差値\s*\n\s*([^\n]+)", text_value)
        parts = [compact(match.group(1))] if match else []
        url = top_url
    return {
        "首都圏模試偏差値": " / ".join(parts),
        "首都圏模試URL": url,
    }


def range_label(values: list[int]) -> str:
    if not values:
        return ""
    low = min(values)
    high = max(values)
    return str(low) if low == high else f"{low}-{high}"


def gender_range(rows: list[dict[str, str]], key: str) -> str:
    parts = []
    for gender in ("男子", "女子", "共通"):
        values = [int(row[key]) for row in rows if row["性別"] == gender and row.get(key, "").isdigit()]
        label = range_label(values)
        if label:
            parts.append(f"{gender[0]}{label}" if gender != "共通" else f"共通{label}")
    return " / ".join(parts)


def extract_yotsuya_deviation(sid: str) -> dict[str, str]:
    code = YOTSUYA_CODES.get(sid, "")
    url = f"https://www.yotsuyaotsuka.com/juken/data/?code={code}" if code else ""
    if not url:
        return {}
    text_value = BeautifulSoup(fetch(url), "html.parser").get_text("\n", strip=True)
    pattern = re.compile(
        r"性別\s*(男子|女子|共通)\s*"
        r"学校名\s*(.*?)\s*"
        r"入試日\s*([0-9/]+)\s*"
        r"Aライン80偏差値\s*(\d+)\s*"
        r"Cライン50偏差値\s*(\d+)",
        re.S,
    )
    rows = []
    for gender, exam_name, exam_date, a80, c50 in pattern.findall(text_value):
        rows.append(
            {
                "性別": gender,
                "学校名": compact(exam_name),
                "入試日": exam_date,
                "A80": a80,
                "C50": c50,
            }
        )
    a80_label = gender_range(rows, "A80")
    c50_label = gender_range(rows, "C50")
    combined = ""
    if a80_label and c50_label:
        combined = f"A80 {a80_label} / C50 {c50_label}"
    elif a80_label:
        combined = f"A80 {a80_label}"
    elif not rows:
        combined = "掲載なし"
    detail = " | ".join(
        f"{row['性別'][0]} {row['入試日']} {row['学校名']} A80:{row['A80']} C50:{row['C50']}"
        for row in rows
    )
    return {
        "四谷大塚偏差値": combined,
        "四谷大塚A80偏差値": a80_label,
        "四谷大塚C50偏差値": c50_label,
        "四谷大塚偏差値詳細": detail,
        "四谷大塚URL": url,
    }


def extract_detail_profile(sid: str) -> dict[str, str]:
    url = f"https://www.study1.jp/kanto/school/{sid}/detail/"
    soup = BeautifulSoup(fetch(url), "html.parser")
    values = {}
    for heading in soup.select("h3.db-tit"):
        title = compact(clean_text(heading))
        lead = heading.find_next("h4", class_="db-lead")
        body = heading.find_next("p", class_="db-txt")
        parts = []
        if lead:
            parts.append(compact(clean_text(lead)))
        if body:
            parts.append(compact(clean_text(body)))
        if title and parts:
            values[f"詳細_{title}"] = " ".join(parts)
    return values


def extract_exam_profile(sid: str) -> dict[str, str]:
    url = f"https://www.study1.jp/kanto/school/{sid}/exam/"
    soup = BeautifulSoup(fetch(url), "html.parser")
    values = {}
    hp_link = soup.find("a", string=re.compile("学校HPの入試要項URL"))
    values["入試要項URL"] = hp_link.get("href", "") if hp_link else ""

    result_heading = soup.find("h3", string=re.compile("入試結果"))
    if result_heading:
        table = result_heading.find_next("table")
        rows = []
        for tr in table.select("tr")[1:7] if table else []:
            cells = [compact(clean_text(cell)) for cell in tr.select("th,td")]
            if any(cells):
                rows.append(" / ".join([cell for cell in cells if cell]))
        values["入試結果サマリー"] = " | ".join(rows)

    tuition_heading = soup.find("h3", string=re.compile("学費"))
    if tuition_heading:
        table = tuition_heading.find_next("table")
        values["学費詳細"] = table_to_text(table)
        caution = tuition_heading.find_next("p", class_="caution")
        values["学費備考"] = compact(clean_text(caution))
    return values


def school_profile(name: str, sid: str) -> dict[str, str]:
    base = f"https://www.study1.jp/kanto/school/{sid}/"
    soup = BeautifulSoup(fetch(base), "html.parser")
    page_text = soup.get_text("\n", strip=True)

    address = ""
    tel = ""
    match = re.search(r"所在地：\s*\|?\s*(〒[^\n]+\n[^\n]+(?:\nTEL[^\n]+)?)", page_text)
    if match:
        lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
        address = " ".join(line for line in lines if not line.startswith("TEL"))
        tel = " ".join(line for line in lines if line.startswith("TEL"))

    match = re.search(r"URL：\s*\|?\s*(https?://\S+)", page_text)
    official_url = match.group(1) if match else ""

    profile = {
        "学校名": name,
        "study1_id": sid,
        "住所": address,
        "TEL": tel,
        "最寄駅・アクセス": ACCESS_OVERRIDES[name],
        "公式URL": official_url,
        "スタディURL": base,
        "説明会URL": urllib.parse.urljoin(base, "briefing/"),
    }
    profile.update(extract_top_profile(soup, sid))
    try:
        profile.update(extract_detail_profile(sid))
    except Exception:
        pass
    try:
        profile.update(extract_exam_profile(sid))
    except Exception:
        pass
    try:
        profile.update(extract_minkou_deviation(sid))
    except Exception:
        profile.update({"みんな偏差値2026": "", "みんな偏差値URL": MINKOU_URLS.get(sid, "")})
    try:
        profile.update(extract_syutoken_deviation(sid))
    except Exception:
        profile.update({"首都圏模試偏差値": "", "首都圏模試URL": f"https://www.syutoken-mosi.co.jp/db/school/?code={SYUTOKEN_CODES.get(sid, '')}"})
    try:
        profile.update(extract_yotsuya_deviation(sid))
    except Exception:
        code = YOTSUYA_CODES.get(sid, "")
        profile.update(
            {
                "四谷大塚偏差値": "",
                "四谷大塚A80偏差値": "",
                "四谷大塚C50偏差値": "",
                "四谷大塚偏差値詳細": "",
                "四谷大塚URL": f"https://www.yotsuyaotsuka.com/juken/data/?code={code}" if code else "",
            }
        )
    return profile


def reservation_start(detail: str, school_note: str, all_text: str) -> str:
    for source in (detail, school_note, all_text):
        for pattern in (
            r"(?:申込|申込み|予約)(?:開始|受付開始)[^。\n]*",
            r"原則1ヶ月前[^。\n]*",
        ):
            match = re.search(pattern, source)
            if match:
                return match.group(0)
    return ""


def is_current_or_future(japanese_date: str) -> bool:
    if not japanese_date:
        return True
    match = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", japanese_date)
    if not match:
        return True
    year, month, day = map(int, match.groups())
    return date(year, month, day) >= AS_OF


def reservation_rule_for(event: dict[str, str]) -> tuple[str, str, str]:
    fallback = ("", "", "")
    for school, date_part, title_part, text_value, precision, source in RESERVATION_RULES:
        if event.get("学校名") != school:
            continue
        if date_part and date_part not in event.get("開催日", ""):
            continue
        if title_part and title_part not in event.get("イベント名", ""):
            continue
        if date_part or title_part:
            return text_value, precision, source
        fallback = (text_value, precision, source)
    return fallback


def enrich_reservation_fields(event: dict[str, str]) -> dict[str, str]:
    text_value, precision, source = reservation_rule_for(event)
    if text_value:
        event["予約開始日・記載"] = text_value
        event["予約開始精度"] = precision
        event["予約開始根拠URL"] = source
    else:
        event.setdefault("予約開始日・記載", "")
        event["予約開始精度"] = "unknown"
        event["予約開始根拠URL"] = event.get("詳細URL", "")
    return event


def school_events(name: str, sid: str) -> list[dict[str, str]]:
    briefing_url = f"https://www.study1.jp/kanto/school/{sid}/briefing/"
    soup = BeautifulSoup(fetch(briefing_url), "html.parser")
    all_text = soup.get_text("\n", strip=True)
    note = ""
    for line in all_text.splitlines():
        if "申込み開始" in line or ("申込" in line and "開始" in line):
            note = line.strip()

    links = []
    seen = set()
    for anchor in soup.select('a[href*="/briefing/detail/"]'):
        url = urllib.parse.urljoin(briefing_url, anchor["href"])
        if url not in seen:
            seen.add(url)
            links.append(url)

    rows = []
    for detail_url in links:
        dsoup = BeautifulSoup(fetch(detail_url), "html.parser")
        title = clean_text(dsoup.select_one("#pop-tit")) or clean_text(dsoup.find(["h2", "h3"]))
        table = dsoup.select_one("table.pop") or dsoup.find("table")
        values = parse_kv_table(table)
        if not is_current_or_future(values.get("日付", "")):
            continue
        reserve_url = ""
        if table:
            anchor = table.select_one("a[href]")
            if anchor:
                reserve_url = urllib.parse.urljoin(detail_url, anchor["href"])
        remark = values.get("備考", "")
        rows.append(
            {
                "学校名": name,
                "開催日": values.get("日付", ""),
                "開催時間": values.get("開催時間", ""),
                "イベント名": title,
                "場所": values.get("場所", ""),
                "対象": values.get("対象", ""),
                "予約": values.get("予約", ""),
                "予約開始日・記載": reservation_start(remark, note, all_text),
                "備考": remark,
                "予約URL": reserve_url,
                "詳細URL": detail_url,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, schools: list[dict[str, str]], events: list[dict[str, str]]) -> None:
    by_school = {school["学校名"]: [] for school in schools}
    for event in events:
        by_school[event["学校名"]].append(event)

    lines = [
        "# 中学イベント情報まとめ",
        "",
        "取得元: 中学受験スタディ（2026年4月30日時点で取得）",
        "",
        "## 学校情報",
        "",
        "| 学校名 | 住所 | 最寄駅・アクセス | 公式URL | 説明会URL |",
        "|---|---|---|---|---|",
    ]
    for school in schools:
        lines.append(
            f"| {school['学校名']} | {school['住所']} | {school['最寄駅・アクセス']} | {school['公式URL']} | {school['説明会URL']} |"
        )

    lines += ["", "## イベント情報", ""]
    for school in schools:
        name = school["学校名"]
        lines += [f"### {name}", ""]
        if not by_school[name]:
            lines += ["スタディ上では今後の説明会・イベント掲載なし。", ""]
            continue
        lines += [
            "| 開催日 | 時間 | イベント名 | 場所 | 対象 | 予約開始日・記載 | 予約URL |",
            "|---|---|---|---|---|---|---|",
        ]
        for event in by_school[name]:
            lines.append(
                f"| {event['開催日']} | {event['開催時間']} | {event['イベント名']} | {event['場所']} | {event['対象']} | {event['予約開始日・記載']} | {event['予約URL']} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    schools = [school_profile(name, sid) for name, sid in SCHOOLS.items()]
    events = []
    for name, sid in SCHOOLS.items():
        events.extend(school_events(name, sid))
    events.extend(SUPPLEMENTAL_EVENTS)
    events = [enrich_reservation_fields(event) for event in events]

    write_csv(out_dir / "schools.csv", schools)
    write_csv(out_dir / "events.csv", events)
    write_markdown(out_dir / "events_summary.md", schools, events)
    print(f"schools={len(schools)} events={len(events)}")


if __name__ == "__main__":
    main()
