"""전체 흐름 조율: ① 빈자리/취소표 알림 ② 신청기간(준비중→접수중) 알림."""
import sys
from pathlib import Path

from src.fetcher import fetch_slots, fetch_facility_status
from src.esongpa import fetch_esongpa_slots
from src.filters import is_wanted_time
from src.differ import find_new_slots, find_opened
from src.notifier import format_message, send_telegram, format_application_message, format_summary
from src.state import load_slots, save_slots, load_status, save_status
from src.config import STATUS_PATH

STATE_PATH = "state.json"  # 직전 빈자리 기록


def run_vacancy_alert():
    """① 빈자리/취소표 알림."""
    try:
        current_all = fetch_slots()
    except Exception as e:
        send_telegram(f"⚠️ 빈자리 읽기 실패: {e}")
        print(f"[읽기 실패] {e}")
        return

    wanted = [s for s in current_all if is_wanted_time(s)]
    # esongpa(송파·잠실, 로그인 필요) — 실패해도 강남 알림은 계속 진행
    try:
        wanted += fetch_esongpa_slots()  # 시설별 시간필터는 내부에서 적용
    except Exception as e:
        print(f"[esongpa 조회 실패] {e}")

    is_first = not Path(STATE_PATH).exists()
    new_slots = find_new_slots(wanted, load_slots(STATE_PATH))

    if is_first:
        print(f"[빈자리 첫 실행] {len(wanted)}건 기준 저장(알림 생략)")
    else:
        msg = format_message(new_slots)
        if msg:
            send_telegram(msg)
            print(f"[빈자리 알림] {len(new_slots)}건")
        else:
            print("[빈자리 변화 없음]")
    save_slots(STATE_PATH, wanted)


def run_application_alert():
    """② 신청기간(준비중→접수중) 알림."""
    status = fetch_facility_status()
    if not status:
        print("[신청상태 조회 0건]")
        return

    is_first = not Path(STATUS_PATH).exists()
    opened = find_opened(status, load_status(STATUS_PATH))

    if is_first:
        print(f"[신청상태 첫 실행] {len(status)}곳 기준 저장(알림 생략)")
    else:
        for name in opened:
            send_telegram(format_application_message(name, status[name]))
            print(f"[신청 시작 알림] {name}")
        if not opened:
            print("[신청상태 변화 없음]")
    save_status(STATUS_PATH, status)


def run_summary():
    """매일 1회: 현재 '원하는 시간대' 빈자리 전체를 요약 발송(직전기록 불필요)."""
    wanted = []
    try:
        wanted += [s for s in fetch_slots() if is_wanted_time(s)]
    except Exception as e:
        print(f"[요약-강남 조회 실패] {e}")
    try:
        wanted += fetch_esongpa_slots()  # 송파·잠실(시설별 필터 적용)
    except Exception as e:
        print(f"[요약-esongpa 조회 실패] {e}")
    send_telegram(format_summary(wanted))
    print(f"[요약 발송] {len(wanted)}건")


def main() -> int:
    # 인자 'summary' → 일일 요약, 그 외 → 기존 취소표/신청 감시
    mode = sys.argv[1] if len(sys.argv) > 1 else "watch"
    if mode == "summary":
        run_summary()
    else:
        run_vacancy_alert()
        run_application_alert()
    return 0


if __name__ == "__main__":
    sys.exit(main())
