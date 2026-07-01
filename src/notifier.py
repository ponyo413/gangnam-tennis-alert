"""텔레그램으로 빈자리 알림을 보낸다. (1) 메시지 만들기 (2) 실제 발송."""
from datetime import date

import requests
from src.models import Slot
from src.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, RESERVE_URL, OLYMPIC_URL

# 한 메시지에 빈자리를 너무 많이 담지 않도록 제한
MAX_LINES = 10

# 요일 한글 — date.weekday()는 0(월)~6(일) 순서
_WEEKDAYS_KR = "월화수목금토일"


def _with_weekday(iso_date):
    """ "2026-07-05" → "2026-07-05(일)". 날짜 형식이 이상하면 원본을 그대로 돌려준다(안전)."""
    try:
        y, m, d = (int(x) for x in iso_date.split("-"))
        return f"{iso_date}({_WEEKDAYS_KR[date(y, m, d).weekday()]})"
    except (ValueError, TypeError):
        return iso_date


def format_message(slots: list[Slot]) -> str:
    """새 빈자리 목록을 사람이 읽기 좋은 텔레그램 메시지로 만든다.

    빈 목록이면 빈 문자열(보내지 않음).
    """
    if not slots:
        return ""

    lines = ["🎾 빈자리 발견!"]
    for s in slots[:MAX_LINES]:
        lines.append(f"🏟 {s.court}테니스장 {s.place}  📅 {_with_weekday(s.date)} {s.time}")
    if len(slots) > MAX_LINES:
        lines.append(f"…외 {len(slots) - MAX_LINES}건")
    lines.append(f"👉 지금 예약: {RESERVE_URL}")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """텔레그램으로 메시지 발송. 성공하면 True.

    text가 비어 있으면(보낼 게 없으면) 아무것도 안 하고 True.
    """
    if not text:
        return True
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10
    )
    return resp.ok


def format_application_message(name: str, info: dict) -> str:
    """신청 시작(준비중→접수중) 알림 메시지를 만든다."""
    return (
        f"🎾 {name} 신청 시작!\n"
        f"📋 접수기간: {info.get('receipt', '')}\n"
        f"📅 이용: {info.get('period', '')}\n"
        f"👉 지금 신청: {RESERVE_URL}"
    )


def format_summary(slots: list[Slot], failures: dict | None = None,
                   title: str = "🎾 [오늘의 빈자리 현황]") -> str:
    """'현재 빈자리 전체' 요약. 빈 목록이면 '없음'. 어제 실패 있으면 한 줄 덧붙임.

    title로 머리말을 바꿀 수 있다(변동 알림은 '🔔 빈자리 현황이 바뀌었어요').
    """
    if not slots:
        lines = [title, "현재 빈자리 없음"]
    else:
        lines = [title]
        for s in sorted(slots, key=lambda x: (x.court, x.date, x.time)):
            lines.append(f"🏟 {s.court} {s.place}  📅 {_with_weekday(s.date)} {s.time}")
        lines.append(f"👉 예약: {RESERVE_URL}")
    if failures:  # 어제 조회 실패가 있었으면 한 줄 보고
        detail = ", ".join(f"{k} {v}번" for k, v in failures.items())
        lines.append(f"⚠️ 어제 조회 실패: {detail}")
    return "\n".join(lines)


def format_olympic_alert(label: str, kind: str, cur: str = "", prev: str = "") -> str:
    """올림픽공원 레슨 대기 알림 문구를 만든다.

    label 예: '주중 실외 19시'. kind = '열림'/'변동'/'닫힘'.
    cur/prev = 그 칸의 현재/직전 표시값(숫자 문자열 등).

    kind별 동작:
      '열림' — 마감/X → 숫자: 이제 대기 신청이 열렸다. OLYMPIC_URL 링크를 붙인다.
      '변동' — 숫자 → 숫자: 대기 인원/자리 수가 달라졌다. 직전값 → 현재값 표시.
      '닫힘' — 숫자 → 마감/X: 대기 줄이 다시 닫혔다. 링크 불필요(어차피 신청 못 함).
    """
    if kind == "열림":   # 마감/X → 숫자: 이제 대기 신청 가능
        return (
            f"🎾 올림픽공원 테니스 레슨 대기 열림!\n"
            f"📋 {label} — 지금 {cur}\n"
            f"👉 지금 대기 신청: {OLYMPIC_URL}"
        )
    if kind == "변동":   # 숫자 → 숫자: 대기 인원/자리 수가 바뀜
        return (
            f"🔔 올림픽공원 레슨 대기 변동\n"
            f"📋 {label} — {prev} → {cur}\n"
            f"👉 {OLYMPIC_URL}"
        )
    # 닫힘: 숫자 → 마감/X (대기 줄이 다시 닫힘)
    return (
        f"🔒 올림픽공원 레슨 대기 마감\n"
        f"📋 {label} (직전 {prev})"
    )
