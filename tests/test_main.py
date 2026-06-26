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
    monkeypatch.setattr(m, "run_summary", lambda: calls.append(1) or True)  # 발송 성공(True) 가정
    monkeypatch.setattr(m, "SUMMARY_PATH", str(tmp_path / "summary_sent.json"))
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 8, 2))   # 첫 8시대 점검 → 발송
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 8, 7))   # 같은 날 → 건너뜀
    assert calls == [1]                                       # 딱 한 번만


def test_maybe_send_daily_summary_skips_before_8(tmp_path, monkeypatch):
    """8시 전엔 보내지 않는다(도장도 안 찍힘)."""
    import src.main as m
    calls = []
    monkeypatch.setattr(m, "run_summary", lambda: calls.append(1) or True)  # 발송 성공(True) 가정
    monkeypatch.setattr(m, "SUMMARY_PATH", str(tmp_path / "summary_sent.json"))
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 7, 30))
    assert calls == []


# ─────────────────────────────────────────────────────────────
# [1번 개선] 요약 발송 '빵꾸' 방지 — 발송이 실패하면 도장을 안 찍는다.
#
# 텔레그램이 "너무 자주 보냈어"(429 등)라며 거부하면 send_telegram이 False를 돌려준다.
# 예전엔 run_summary가 그 값을 무시하고 maybe_send_daily_summary가 무조건 '오늘 보냄✓'
# 도장을 찍어버려, 발송 실패해도 그날 요약이 영영 안 왔다(편지가 우체통에 안 들어갔는데
# 달력에 '보냄✓' 표시해버린 격). 이제 성공(True)일 때만 도장을 찍어 다음 점검에서 재시도한다.
# ─────────────────────────────────────────────────────────────

def test_maybe_send_daily_summary_retries_when_send_fails(tmp_path, monkeypatch):
    """발송 실패(False)면 도장을 안 찍어, 다음 점검에서 한 번 더 시도한다(빵꾸 방지)."""
    import src.main as m
    calls = []
    # run_summary가 '발송 실패(False)'를 돌려주는 상황 — 텔레그램이 막힌 경우
    monkeypatch.setattr(m, "run_summary", lambda: calls.append(1) or False)
    monkeypatch.setattr(m, "SUMMARY_PATH", str(tmp_path / "summary_sent.json"))
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 8, 2))   # 첫 점검 → 실패(도장 안 찍힘)
    m.maybe_send_daily_summary(datetime(2026, 6, 26, 8, 7))   # 다음 점검 → 도장 없으니 재시도
    assert calls == [1, 1]                                    # 두 번 다 시도 = 빵꾸 안 남


def test_run_summary_returns_send_result(monkeypatch):
    """run_summary는 텔레그램 발송이 성공하면 True, 거부되면 False를 돌려준다.

    이 값을 보고 maybe_send_daily_summary가 '도장을 찍을지'를 정한다.
    """
    import src.main as m
    # 실제 망·파일 접근 없이 흐름만 보도록 의존 함수들을 가짜로 바꾼다(monkeypatch)
    monkeypatch.setattr(m, "load_settings", lambda: ({"강남": {}}, None))
    monkeypatch.setattr(m, "fetch_slots", lambda: [])
    monkeypatch.setattr(m, "fetch_esongpa_slots", lambda settings, previous: [])
    monkeypatch.setattr(m, "load_slots", lambda path: [])
    monkeypatch.setattr(m, "load_failures", lambda path: {})
    monkeypatch.setattr(m, "save_failures", lambda path, data: None)

    monkeypatch.setattr(m, "send_telegram", lambda text: True)
    assert m.run_summary() is True
    monkeypatch.setattr(m, "send_telegram", lambda text: False)
    assert m.run_summary() is False


def test_run_summary_keeps_failures_when_send_fails(monkeypatch):
    """발송 실패 시 '어제 조회 실패 기록'을 지우지 않는다 — 다음 성공 발송에 보고하려 보존."""
    import src.main as m
    saved = []
    monkeypatch.setattr(m, "load_settings", lambda: ({"강남": {}}, None))
    monkeypatch.setattr(m, "fetch_slots", lambda: [])
    monkeypatch.setattr(m, "fetch_esongpa_slots", lambda settings, previous: [])
    monkeypatch.setattr(m, "load_slots", lambda path: [])
    monkeypatch.setattr(m, "load_failures", lambda path: {"esongpa": 2})
    monkeypatch.setattr(m, "save_failures", lambda path, data: saved.append(data))
    monkeypatch.setattr(m, "send_telegram", lambda text: False)

    m.run_summary()
    assert saved == []   # 발송 실패 → 실패 기록 보존(리셋 안 함)


def test_run_summary_resets_failures_when_send_succeeds(monkeypatch):
    """발송 성공 시에만 '어제 조회 실패 기록'을 비운다(정상 보고를 마쳤으므로)."""
    import src.main as m
    saved = []
    monkeypatch.setattr(m, "load_settings", lambda: ({"강남": {}}, None))
    monkeypatch.setattr(m, "fetch_slots", lambda: [])
    monkeypatch.setattr(m, "fetch_esongpa_slots", lambda settings, previous: [])
    monkeypatch.setattr(m, "load_slots", lambda path: [])
    monkeypatch.setattr(m, "load_failures", lambda path: {"esongpa": 2})
    monkeypatch.setattr(m, "save_failures", lambda path, data: saved.append(data))
    monkeypatch.setattr(m, "send_telegram", lambda text: True)

    m.run_summary()
    assert saved == [{}]   # 발송 성공 → 빈 기록으로 리셋


# ─────────────────────────────────────────────────────────────
# [경미 보강] 수동 'summary' 모드도 발송 실패를 종료코드로 알린다.
#
# 봇을 켜는 방법은 둘 — ①평소 자동(watch, 5분 점검) ②사람이 손으로 'summary'(요약만 지금).
# run_summary가 이제 성공/실패(True/False)를 돌려주므로, 수동 모드에선 그 값을 종료코드로
# 넘겨 GitHub Actions가 발송 실패를 '빨간불'로 감지할 수 있게 한다(watch 모드는 늘 0 유지).
# ─────────────────────────────────────────────────────────────

def test_main_summary_mode_returns_1_when_send_fails(monkeypatch):
    """수동 'summary' 모드에서 발송 실패(False)면 종료코드 1을 돌려준다(실패 감지)."""
    import sys
    import src.main as m
    monkeypatch.setattr(sys, "argv", ["main", "summary"])
    monkeypatch.setattr(m, "run_summary", lambda: False)
    assert m.main() == 1


def test_main_summary_mode_returns_0_when_send_succeeds(monkeypatch):
    """수동 'summary' 모드에서 발송 성공(True)이면 종료코드 0(정상)."""
    import sys
    import src.main as m
    monkeypatch.setattr(sys, "argv", ["main", "summary"])
    monkeypatch.setattr(m, "run_summary", lambda: True)
    assert m.main() == 0


def test_main_watch_mode_returns_0(monkeypatch):
    """평소 'watch' 모드는 항상 종료코드 0 — 점검만 하고 워크플로는 성공 처리(기존 동작 보존)."""
    import sys
    import src.main as m
    monkeypatch.setattr(sys, "argv", ["main"])
    monkeypatch.setattr(m, "run_vacancy_alert", lambda: None)
    monkeypatch.setattr(m, "run_application_alert", lambda: None)
    monkeypatch.setattr(m, "maybe_send_daily_summary", lambda now: None)
    assert m.main() == 0
