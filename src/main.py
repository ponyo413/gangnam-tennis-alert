"""전체 흐름 조율: ① 빈자리 현황 변동 알림 ② 신청기간(준비중→접수중) 알림.

시설별 켜고끄기·시간대는 settings.yaml(설정표)에서 읽어 적용한다.
조회 실패는 failures.json에 누적해 매일 아침 요약에 한 줄로 보고한다.
빈자리 현황이 직전과 달라지면(추가·삭제 무관) 현재 전체 현황을 알린다.
"""
import sys
from datetime import datetime
from pathlib import Path

from src.fetcher import fetch_slots, fetch_facility_status
from src.esongpa import fetch_esongpa_slots
from src.daechi import fetch_daechi_slots, is_daechi_due, KST
from src.filters import is_wanted_for
from src.settings_loader import load_settings
from src.differ import has_changed, find_opened
from src.notifier import send_telegram, format_application_message, format_summary
from src.state import (load_slots, save_slots, load_status, save_status,
                       load_failures, save_failures, load_fail_count, save_fail_count,
                       load_daechi_fetch_time, save_daechi_fetch_time)
from src.config import STATUS_PATH

STATE_PATH = "state.json"      # 직전 빈자리 기록
FAIL_PATH = "failures.json"    # 시설별 조회 실패 횟수(요약 때 보고 후 리셋)
READ_FAIL_PATH = "read_fail.json"   # 강남 조회 '연속' 실패 횟수(산발 끊김 무시용)
READ_FAIL_THRESHOLD = 3             # 연속 3회(=약 15분)부터 '사이트 다운'으로 보고 알림
DAECHI_SLOTS_PATH = "daechi_slots.json"   # 대치유수지 직전 빈자리(박제)
DAECHI_TIME_PATH = "daechi_fetch.json"    # 대치유수지 마지막 조회 시각


def read_fail_decision(prev_count, success, threshold=READ_FAIL_THRESHOLD):
    """강남 조회 결과로 (새 연속실패 카운트, 보낼 알림종류)를 정한다 — 순수함수.

    강남 사이트는 밤에 간헐적으로 연결이 끊긴다(산발 timeout). 매번 알리면 시끄러우니
    연속 임계에 도달했을 때만 'down', 다운에서 풀리면 'recover'만 보낸다.
    - success=True(조회 성공): 직전이 다운(임계 이상)이었으면 'recover', 카운트는 0으로.
    - success=False(조회 실패): 카운트 +1, 그 값이 '정확히 임계'면 'down'(그 위는 조용).
    반환: (new_count, alert) — alert는 None / 'down' / 'recover'.
    """
    if success:
        return 0, ("recover" if prev_count >= threshold else None)
    new_count = prev_count + 1
    return new_count, ("down" if new_count == threshold else None)


def run_vacancy_alert():
    """① 빈자리 현황 변동 알림 — 현재 빈자리가 직전과 달라지면 전체 현황을 1통으로."""
    settings, err = load_settings()
    if err:
        send_telegram(f"⚠️ {err}")  # 설정표 형식 오류 시 알림(폴백으로 계속 작동)
    # 강남 조회 '연속' 실패 추적 — 조회 전에 직전 카운트를 읽어둔다(산발 timeout 무시용)
    prev_fail = load_fail_count(READ_FAIL_PATH)
    try:
        current_all = fetch_slots()
    except Exception as e:
        # 강남 사이트 일시 끊김은 흔하다 → 연속 임계(약 15분)에 도달했을 때만 1통 알림
        count, alert = read_fail_decision(prev_fail, success=False)
        save_fail_count(READ_FAIL_PATH, count)
        if alert == "down":
            send_telegram(f"⚠️ 강남 사이트 응답 없음 (연속 {count}회·약 15분): {e}")
        print(f"[읽기 실패 {count}회 연속] {e}")
        return
    # 조회 성공 → 직전이 '다운'이었으면 복구 알림 1통 + 연속 카운트 리셋(함수가 0을 돌려줌)
    new_count, recovered = read_fail_decision(prev_fail, success=True)
    if recovered == "recover":
        send_telegram("✅ 강남 사이트 복구됨 — 빈자리 알림을 다시 받습니다.")
    save_fail_count(READ_FAIL_PATH, new_count)

    gangnam_cfg = settings.get("강남", {})
    wanted = [s for s in current_all if is_wanted_for(s, gangnam_cfg)]
    # 직전 빈자리 — '접수 닫힘'(저녁)인 esongpa 시설은 새 0건 대신 이걸 그대로 유지한다
    previous = load_slots(STATE_PATH)
    # esongpa(송파·잠실, 로그인 필요) — 실패해도 강남 알림은 계속 진행 + 실패 누적
    failures = load_failures(FAIL_PATH)
    try:
        wanted += fetch_esongpa_slots(settings, previous)  # 닫힘 시설은 직전 유지(내부 판정)
    except Exception as e:
        failures["esongpa"] = failures.get("esongpa", 0) + 1
        print(f"[esongpa 조회 실패] {e}")
    # 대치유수지 — 15분 간격 + 08~24시에만 실제 접속(매크로 빈번접속 공지 존중).
    # 그 외 실행에선 직전에 박제한 빈자리를 그대로 유지(가짜 변동 알림 방지).
    now = datetime.now(KST)
    last_str = load_daechi_fetch_time(DAECHI_TIME_PATH)
    last_dt = datetime.fromisoformat(last_str) if last_str else None
    if is_daechi_due(now, last_dt):
        try:
            daechi_slots = fetch_daechi_slots(settings)
            save_slots(DAECHI_SLOTS_PATH, daechi_slots)            # 결과 박제
            save_daechi_fetch_time(DAECHI_TIME_PATH, now.isoformat())
            wanted += daechi_slots
        except Exception as e:
            failures["대치유수지"] = failures.get("대치유수지", 0) + 1
            wanted += load_slots(DAECHI_SLOTS_PATH)                # 실패 시 직전 유지
            print(f"[대치유수지 조회 실패] {e}")
    else:
        wanted += load_slots(DAECHI_SLOTS_PATH)                    # 시간창 밖/15분 미경과 → 직전 유지
    save_failures(FAIL_PATH, failures)

    is_first = not Path(STATE_PATH).exists()
    if is_first:
        print(f"[빈자리 첫 실행] {len(wanted)}건 기준 저장(알림 생략)")
    elif has_changed(wanted, previous):
        # 빈자리 목록이 직전과 달라짐(추가·삭제 무관) → 현재 전체 현황을 1통으로
        send_telegram(format_summary(wanted, title="🔔 빈자리 현황이 바뀌었어요"))
        print(f"[현황 변동 알림] {len(wanted)}건")
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
    previous = load_slots(STATE_PATH)  # 접수 닫힘 시설은 직전(낮에 본) 빈자리를 요약에 유지
    try:
        wanted += fetch_esongpa_slots(settings, previous)  # 송파·잠실(설정 기반, 닫힘 시 직전 유지)
    except Exception as e:
        print(f"[요약-esongpa 조회 실패] {e}")
    wanted += load_slots(DAECHI_SLOTS_PATH)   # 대치유수지: 직전 박제 빈자리(요약은 접속 안 함)
    failures = load_failures(FAIL_PATH)
    send_telegram(format_summary(wanted, failures=failures))
    save_failures(FAIL_PATH, {})  # 보고 후 실패 카운트 리셋
    print(f"[요약 발송] {len(wanted)}건, 실패 {sum(failures.values())}건")


def main() -> int:
    # 인자 'summary' → 일일 요약, 그 외 → 빈자리 변동/신청 감시
    mode = sys.argv[1] if len(sys.argv) > 1 else "watch"
    if mode == "summary":
        run_summary()
    else:
        run_vacancy_alert()
        run_application_alert()
    return 0


if __name__ == "__main__":
    sys.exit(main())
