#!/usr/bin/env python3
"""국제기구 인사센터(unrecruit.mofa.go.kr) 공고 모니터링 스크립트.

공석/인턴십/UNV 게시판을 확인해 data.js를 갱신하고,
새 공고가 있으면 macOS 알림을 띄운다.
"""
import html
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = "https://unrecruit.mofa.go.kr"
DIR = Path(__file__).resolve().parent
SEEN_FILE = DIR / "seen.json"
DATA_FILE = DIR / "data.js"

NEW_DAYS = 7  # 이 기간 안에 처음 발견된 공고는 NEW 표시

BOARDS = {
    "vacancy": {
        "label": "국제기구 공석",
        "list_url": f"{BASE}/new/vacancy/latest_vacancy.jsp",
        "view_url": f"{BASE}/new/vacancy/latest_vacancy_view.jsp?seq=",
    },
    "internship": {
        "label": "인턴십",
        "list_url": f"{BASE}/new/internship/notice.jsp",
        "view_url": f"{BASE}/new/internship/notice_view.jsp?seq=",
    },
    "unv_specialist": {
        "label": "UNV 전문봉사단",
        "list_url": f"{BASE}/new/unv/specialist.jsp",
        "view_url": f"{BASE}/new/unv/specialist_view.jsp?seq=",
    },
    "unv_youth": {
        "label": "UNV 청년봉사단",
        "list_url": f"{BASE}/new/unv/youth.jsp",
        "view_url": f"{BASE}/new/unv/youth_view.jsp?seq=",
    },
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_vacancy(page):
    """공석 게시판: 구분/분야/직책/기구/직급/마감일 7컬럼 테이블."""
    items = []
    for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        m = re.search(r"goView\('(\d+)'\)[^>]*title=\"([^\"]*)\"", tr)
        if not m:
            continue
        seq, title = m.group(1), strip_tags(m.group(2))
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 6:
            continue
        items.append({
            "seq": seq,
            "title": title,
            "status": strip_tags(tds[0]),
            "field": strip_tags(tds[1]),
            "org": strip_tags(tds[3]),
            "grade": strip_tags(tds[4]),
            "deadline": strip_tags(tds[5]),
        })
    return items


def parse_notice(page):
    """인턴십/UNV 게시판: 번호/제목/날짜/조회수 4컬럼 테이블."""
    items = []
    for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        m = re.search(r"goView\('(\d+)'\)[^>]*title=\"([^\"]*)\"", tr)
        if not m:
            continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        date = ""
        for td in tds:
            t = strip_tags(td)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
                date = t
                break
        items.append({
            "seq": m.group(1),
            "title": strip_tags(m.group(2)),
            "date": date,
        })
    return items


def notify(title, message):
    script = f'display notification "{message}" with title "{title}"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=10)
    except Exception:
        pass


def main():
    seen = {}
    first_run = not SEEN_FILE.exists()
    if not first_run:
        seen = json.loads(SEEN_FILE.read_text())

    now = datetime.now()
    now_iso = now.strftime("%Y-%m-%d %H:%M")
    # 최초 수집분은 NEW로 취급하지 않기 위해 시드 시각을 기록
    seeded_at = seen.setdefault("_seeded_at", now_iso)
    all_items = []
    new_items = []
    errors = []

    for board, cfg in BOARDS.items():
        try:
            page = fetch(cfg["list_url"])
        except Exception as e:
            errors.append(f"{cfg['label']}: {e}")
            continue
        parsed = parse_vacancy(page) if board == "vacancy" else parse_notice(page)
        for it in parsed:
            key = f"{board}:{it['seq']}"
            if key not in seen:
                seen[key] = now_iso
                if not first_run:
                    new_items.append((cfg["label"], it["title"]))
            first_seen = seen[key]
            try:
                is_new = (
                    first_seen > seeded_at
                    and now - datetime.strptime(first_seen, "%Y-%m-%d %H:%M") <= timedelta(days=NEW_DAYS)
                )
            except ValueError:
                is_new = False
            all_items.append({
                **it,
                "board": board,
                "board_label": cfg["label"],
                "url": cfg["view_url"] + it["seq"],
                "first_seen": first_seen,
                "is_new": is_new,
            })

    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=1))

    data = {
        "updated": now_iso,
        "items": all_items,
        "errors": errors,
        "new_count": len(new_items),
    }
    DATA_FILE.write_text(
        "window.JOB_DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n"
    )

    if new_items:
        first_title = new_items[0][1]
        if len(first_title) > 60:
            first_title = first_title[:60] + "…"
        msg = first_title if len(new_items) == 1 else f"{first_title} 외 {len(new_items) - 1}건"
        notify(f"국제기구 새 공고 {len(new_items)}건", msg.replace('"', "'"))

    print(f"[{now_iso}] 수집 {len(all_items)}건, 새 공고 {len(new_items)}건" + (f", 오류 {errors}" if errors else ""))


if __name__ == "__main__":
    sys.exit(main())
