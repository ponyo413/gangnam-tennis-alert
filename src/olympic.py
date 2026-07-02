# src/olympic.py
"""올림픽공원 테니스 레슨 '대기 현황표' 감시 — 로그인 없는 HTML 파싱(전용 부품).

강남·esongpa·대치유수지가 '코트 빈자리(취소표)'를 다루는 것과 달리, 여기서는
'레슨 대기 칸의 값 변화'를 본다. 칸 값 3종: 숫자(대기 가능·그 수)·'마감'(대기 마감)·'X'(레슨 없음).
값이 바뀌면(마감→숫자·숫자→숫자·숫자→마감) 알림, 마감↔X만 조용.
날짜 축이 없는 고정 주간표(주중/주말)라 '칸별 현재값 dict'만 다룬다.
"""

import re

from src.config import OLYMPIC_URL
from src.http_session import make_session
from src.notifier import format_olympic_alert

DAY_KEYS = ("주중", "주말", "수요일")   # 표 첫 칸(요일)에 나올 수 있는 값
COURT_KEYS = ("실외", "실내")            # 표 둘째 칸(코트)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
REQUEST_TIMEOUT = 8   # 한 요청 최대 기다림(초)

# 표 파싱용 정규식(스크립트 제거 → <tr> → <th|td> 순)
_SCRIPT_RE = re.compile(r"<script.*?</script>", re.DOTALL | re.IGNORECASE)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_RE = re.compile(r"<(t[hd])[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
_HOUR_RE = re.compile(r"(\d+)\s*시")     # "19시" → 19


def _clean(fragment):
    """HTML 조각에서 태그 제거 + 공백 정리 → 순수 텍스트."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", text).strip()


def _is_number(value):
    """값이 숫자(대기 가능)인지. None·'마감'·'X'는 False (None-안전)."""
    return str(value).strip().isdigit()


def classify_change(prev, cur):
    """칸 하나의 직전값(prev)→현재값(cur)으로 알림 종류를 정한다(순수함수).

    반환: '열림' / '변동' / '닫힘' / None(조용).
    - 값이 같으면 None.
    - 현재가 숫자면: 직전이 숫자 아님(마감/X/None) → '열림', 직전도 숫자(값 다름) → '변동'.
    - 현재가 숫자 아니면(마감/X): 직전이 숫자 → '닫힘', 아니면 None(마감↔X는 조용).
    """
    if prev == cur:
        return None
    if _is_number(cur):
        return "변동" if _is_number(prev) else "열림"
    return "닫힘" if _is_number(prev) else None


def build_targets(cfg):
    """설정(cfg) → 감시할 (요일, 코트, 시) 튜플 목록(순수함수).

    cfg 예: {"받기": True, "코트": ["실외","실내"], "주중": [19]}.
    받기=False·설정 없음 → []. 요일키(주중/주말/수요일) × 코트 × 시각을 모두 편다.
    """
    if not cfg or not cfg.get("받기"):
        return []
    courts = [c for c in cfg.get("코트", []) if c in COURT_KEYS]
    targets = []
    for day in DAY_KEYS:
        for hour in cfg.get(day, []):
            for court in courts:
                targets.append((day, court, hour))
    return targets


def _rows(html):
    """HTML → 표의 각 줄을 '칸 텍스트 목록'으로. (스크립트 제거 후 <tr>·<th/td> 파싱)"""
    body = _SCRIPT_RE.sub("", html)
    rows = []
    for tr in _TR_RE.findall(body):
        cells = [_clean(m.group(2)) for m in _CELL_RE.finditer(tr)]
        if cells:
            rows.append(cells)
    return rows


def _hour_columns(rows):
    """머리줄('시간/코트'가 든 줄)에서 {시각(int): 열번호} 지도를 만든다."""
    for cells in rows:
        if any("시간/코트" in c for c in cells):
            cols = {}
            for idx, c in enumerate(cells):
                m = _HOUR_RE.fullmatch(c.replace(" ", ""))
                if m:
                    cols[int(m.group(1))] = idx
            return cols
    return {}


def parse_olympic(html, targets):
    """감시 대상 칸의 현재 값만 dict로 뽑는다(순수 파싱).

    targets: (요일, 코트, 시) 튜플 목록.
    반환: {"주중 실외 19시": "마감", "주중 실내 19시": "3", ...} — 칸 실제 텍스트 그대로.
    표에서 못 찾은 칸은 그냥 빠진다(예외 안 냄).
    """
    rows = _rows(html)
    hour_cols = _hour_columns(rows)
    result = {}
    for day, court, hour in targets:
        col = hour_cols.get(hour)
        if col is None:
            continue
        for cells in rows:
            if len(cells) > col and cells[0] == day and cells[1] == court:
                result[f"{day} {court} {hour}시"] = cells[col]
                break
    return result


def build_olympic_messages(current, previous):
    """직전(previous)·현재(current) 값 dict를 비교해 보낼 알림 문구 목록을 만든다.

    current의 각 칸을 classify_change로 판정하고, 종류가 있으면 문구 1개씩.
    """
    messages = []
    for label, cur in current.items():
        prev = previous.get(label)
        kind = classify_change(prev, cur)
        if kind:
            messages.append(format_olympic_alert(label, kind, cur, prev or ""))
    return messages


def fetch_olympic_states(settings):
    """설정 기반으로 대기 현황표를 조회해 감시 칸의 현재 값 dict를 돌려준다.

    반환: dict(정상) / {}(받기 off·대상 0개) / None(조회·파싱 실패 → main이 직전 유지).
    조회 예외는 밖으로 던지지 않는다(다른 시설 알림 보호).
    """
    cfg = settings.get("올림픽공원레슨")
    targets = build_targets(cfg)
    if not targets:
        return {}                       # 감시 끔 → 조회 안 함
    try:
        session = make_session(HEADERS)
        r = session.get(OLYMPIC_URL, timeout=REQUEST_TIMEOUT)
        r.encoding = "utf-8"            # 표 한글 깨짐 방지
        return parse_olympic(r.text, targets)
    except Exception as e:
        print(f"[올림픽공원 조회 실패] {e}")
        return None
