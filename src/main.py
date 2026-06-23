"""전체 흐름 조율: ① 빈자리/취소표 알림 ② 신청기간(준비중→접수중) 알림.

시설별 켜고끄기·시간대는 settings.yaml(설정표)에서 읽어 적용한다.
조회 실패는 failures.json에 누적해 매일 아침 요약에 한 줄로 보고한다.
"""
import sys
from pathlib import Path

from src.fetcher import fetch_slots, fetch_facility_status
from src.esongpa import fetch_esongpa_slots
from src.filters import is_wanted_for
from src.settings_loader import load_settings
from src.differ import find_new_slots, find_opened
from src.notifier import format_message, send_telegram, format_application_message, format_summary
from src.state import load_slots, save_slots, load_status, save_status, load_failures, save_failures
from src.config import STATUS_PATH

STATE_PATH = "state.json"      # 직전 빈자리 기록
FAIL_PATH = "failures.json"    # 시설별 조회 실패 횟수(요약 때 보고 후 리셋)


def run_vacancy_alert():
    """① 빈자리/취소표 알림."""
    settings, err = load_settings()
    if err:
        send_telegram(f"⚠️ {err}")  # 설정표 형식 오류 시 알림(폴백으로 계속 작동)
    try:
        current_all = fetch_slots()
    except Exception as e:
        send_telegram(f"⚠️ 빈자리 읽기 실패: {e}")
        print(f"[읽기 실패] {e}")
        return

    gangnam_cfg = settings.get("강남", {})
    wanted = [s for s in current_all if is_wanted_for(s, gangnam_cfg)]
    # esongpa(송파·잠실, 로그인 필요) — 실패해도 강남 알림은 계속 진행 + 실패 누적
    failures = load_failures(FAIL_PATH)
    try:
        wanted += fetch_esongpa_slots(settings)  # 시설별 켜고끄기+시간필터는 내부에서
    except Exception as e:
        failures["esongpa"] = failures.get("esongpa", 0) + 1
        print(f"[esongpa 조회 실패] {e}")
    save_failures(FAIL_PATH, failures)

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
    """매일 1회: 현재 '원하는 시간대' 빈자리 전체 + 어제 실패를 요약 발송(직전기록 불필요)."""
    settings, err = load_settings()
    if err:
        send_telegram(f"⚠️ {err}")
    gangnam_cfg = settings.get("강남", {})
    wanted = []
    try:
        wanted += [s for s in fetch_slots() if is_wanted_for(s, gangnam_cfg)]
    except Exception as e:
        print(f"[요약-강남 조회 실패] {e}")
    try:
        wanted += fetch_esongpa_slots(settings)  # 송파·잠실(설정 기반)
    except Exception as e:
        print(f"[요약-esongpa 조회 실패] {e}")
    failures = load_failures(FAIL_PATH)
    send_telegram(format_summary(wanted, failures=failures))
    save_failures(FAIL_PATH, {})  # 보고 후 실패 카운트 리셋
    print(f"[요약 발송] {len(wanted)}건, 실패 {sum(failures.values())}건")


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
