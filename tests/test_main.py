"""강남 조회 '연속 실패 알림' 판정 테스트.

강남 사이트는 밤에 간헐적으로 연결이 끊긴다(산발 timeout). 매번 경고하면 시끄러우니,
연속 임계(기본 3회=15분)에 도달했을 때만 '다운' 1통, 복구되면 '복구' 1통을 보낸다.
판정만 떼어낸 순수함수 read_fail_decision을 박제한다.
"""
from datetime import datetime

from src.main import read_fail_decision, should_send_summary


def test_first_two_fails_no_alert():
    """1·2회 실패는 조용 — 산발 끊김은 무시한다."""
    assert read_fail_decision(0, success=False, threshold=3) == (1, None)
    assert read_fail_decision(1, success=False, threshold=3) == (2, None)


def test_third_consecutive_fail_alerts_down():
    """연속 3회째(15분)에 '다운' 알림 1통."""
    assert read_fail_decision(2, success=False, threshold=3) == (3, "down")


def test_beyond_threshold_stays_quiet():
    """이미 다운 알림을 보낸 뒤(4회 이상)엔 더 보내지 않는다."""
    assert read_fail_decision(3, success=False, threshold=3) == (4, None)


def test_recover_after_down_alerts():
    """다운(임계 이상) 상태에서 성공하면 '복구' 알림 + 카운트 0으로 리셋."""
    assert read_fail_decision(3, success=True, threshold=3) == (0, "recover")
    assert read_fail_decision(5, success=True, threshold=3) == (0, "recover")


def test_sporadic_fail_then_success_is_quiet():
    """다운 알림 전(2회 이하) 실패 후 성공은 조용히 리셋 — 복구 알림도 없음."""
    assert read_fail_decision(2, success=True, threshold=3) == (0, None)


def test_normal_success_is_quiet():
    """평소 성공은 조용."""
    assert read_fail_decision(0, success=True, threshold=3) == (0, None)


# ─────────────────────────────────────────────────────────────
# 매일 아침 요약 발송 판정 — should_send_summary
#
# 옛날엔 GitHub 무료 예약타이머가 아침 8시에 요약을 보내야 했는데 1시간씩 늦잠을 잤다.
# 이제는 제시간에 도는 '5분 점검'이 아침 8시대 첫 바퀴에서 요약을 같이 보낸다.
# "지금 8시대인가 + 오늘 아직 안 보냈는가"만 떼어낸 순수함수를 박제한다.
# ─────────────────────────────────────────────────────────────

def test_summary_sends_at_8am_when_not_sent_today():
    """아침 8시이고 오늘 아직 안 보냈으면 → 보낸다(첫 실행/어제 보낸 기록 모두 포함)."""
    now = datetime(2026, 6, 26, 8, 3)
    assert should_send_summary(now, None) is True          # 보낸 기록 자체가 없음
    assert should_send_summary(now, "2026-06-25") is True   # 어제 보냈을 뿐, 오늘은 아직


def test_summary_not_resent_same_day():
    """오늘 이미 보냈으면 8시든 오후든 다시 안 보낸다 — 하루 딱 한 번(도장이 막음)."""
    assert should_send_summary(datetime(2026, 6, 26, 8, 30), "2026-06-26") is False
    assert should_send_summary(datetime(2026, 6, 26, 14, 0), "2026-06-26") is False


def test_summary_not_before_8am():
    """8시 전(7시대 이하)이면 보내지 않는다 — 아침이 되기 전엔 조용."""
    assert should_send_summary(datetime(2026, 6, 26, 7, 59), None) is False
    assert should_send_summary(datetime(2026, 6, 26, 0, 0), None) is False


def test_summary_catches_up_after_8am_if_missed():
    """8시대를 통째로 놓쳐도(장애 등) 9시·정오 등 그날 첫 점검에서 반드시 한 번 보낸다.
    옛 방식의 '늦어도 결국 옴' 장점을 지킨다."""
    assert should_send_summary(datetime(2026, 6, 26, 9, 0), "2026-06-25") is True
    assert should_send_summary(datetime(2026, 6, 26, 12, 30), "2026-06-25") is True


def test_summary_sends_on_first_tick_at_8am():
    """8시 정각 첫 점검에서 곧바로 보낸다(어제 기록만 있는 상태)."""
    assert should_send_summary(datetime(2026, 6, 26, 8, 0), "2026-06-25") is True


# ── 연결 코드(글루) 검증 — load→판정→발송→도장→다음엔 건너뜀.
#    run_summary는 실제 텔레그램 발송이라 가짜로 바꿔(monkeypatch) 망 없이 흐름만 본다.
def test_maybe_send_daily_summary_sends_once_per_day(tmp_path, monkeypatch):
    """8시대 첫 점검에 1번 보내고 도장 → 같은 날 다음 점검은 건너뛴다."""
    import src.main as m
    calls = []
    monkeypatch.setattr(m, "run_summary", lambda: calls.append(1))
    monkeypatch.setattr(m, "SUMMARY_PATH", str(tmp_path / "summary_sent.json"))
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 8, 2))   # 첫 8시대 점검 → 발송
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 8, 7))   # 같은 날 → 건너뜀
    assert calls == [1]                                       # 딱 한 번만


def test_maybe_send_daily_summary_skips_before_8(tmp_path, monkeypatch):
    """8시 전엔 보내지 않는다(도장도 안 찍힘)."""
    import src.main as m
    calls = []
    monkeypatch.setattr(m, "run_summary", lambda: calls.append(1))
    monkeypatch.setattr(m, "SUMMARY_PATH", str(tmp_path / "summary_sent.json"))
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 7, 30))
    assert calls == []
