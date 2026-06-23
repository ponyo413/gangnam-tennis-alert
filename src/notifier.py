"""텔레그램으로 빈자리 알림을 보낸다. (1) 메시지 만들기 (2) 실제 발송."""
import requests
from src.models import Slot
from src.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, RESERVE_URL

# 한 메시지에 빈자리를 너무 많이 담지 않도록 제한
MAX_LINES = 10


def format_message(slots: list[Slot]) -> str:
    """새 빈자리 목록을 사람이 읽기 좋은 텔레그램 메시지로 만든다.

    빈 목록이면 빈 문자열(보내지 않음).
    """
    if not slots:
        return ""

    lines = ["🎾 빈자리 발견!"]
    for s in slots[:MAX_LINES]:
        lines.append(f"🏟 {s.court}테니스장 {s.place}  📅 {s.date} {s.time}")
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


def format_summary(slots: list[Slot]) -> str:
    """매일 1회 '현재 빈자리 전체' 요약 메시지. 빈 목록이면 '없음' 한 줄."""
    if not slots:
        return "🎾 [오늘의 빈자리 현황]\n현재 빈자리 없음"
    lines = ["🎾 [오늘의 빈자리 현황]"]
    for s in sorted(slots, key=lambda x: (x.court, x.date, x.time)):
        lines.append(f"🏟 {s.court} {s.place}  📅 {s.date} {s.time}")
    lines.append(f"👉 예약: {RESERVE_URL}")
    return "\n".join(lines)
