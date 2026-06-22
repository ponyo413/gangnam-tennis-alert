"""전체 흐름 조율: 조회 → 시간대 필터 → 새 빈자리 비교 → 알림 → 상태 저장."""
import sys
from pathlib import Path

from src.fetcher import fetch_slots
from src.filters import is_wanted_time
from src.differ import find_new_slots
from src.notifier import format_message, send_telegram
from src.state import load_slots, save_slots

STATE_PATH = "state.json"  # 직전 빈자리 기록 위치


def main() -> int:
    # 1) 사이트에서 현재 빈자리 전부 읽기
    try:
        current_all = fetch_slots()
    except Exception as e:
        # 사이트 자체를 못 읽으면 '읽기 실패'를 알려서 조용히 죽지 않게
        send_telegram(f"⚠️ 빈자리 읽기 실패: {e}")
        print(f"[읽기 실패] {e}")
        return 1

    # 2) 원하는 시간대(평일 저녁+주말)만 거르기
    wanted = [s for s in current_all if is_wanted_time(s)]

    # 3) 첫 실행(직전 기록 파일 없음)인지 확인 — 알림 폭탄 방지
    is_first_run = not Path(STATE_PATH).exists()
    previous = load_slots(STATE_PATH)
    new_slots = find_new_slots(wanted, previous)

    if is_first_run:
        # 처음엔 현재 빈자리가 수백 건일 수 있으므로 알리지 않고 기준만 저장
        print(f"[첫 실행] 현재 빈자리 {len(wanted)}건을 기준으로 저장 (알림 생략)")
    else:
        # 4) 직전과 비교해 새로 생긴 빈자리만 텔레그램 알림
        message = format_message(new_slots)
        if message:
            send_telegram(message)
            print(f"[알림] 새 빈자리 {len(new_slots)}건 발송")
        else:
            print("[변화 없음]")

    # 5) 이번 결과를 직전 기록으로 저장 (다음 비교용)
    save_slots(STATE_PATH, wanted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
