"""강남 조회 '연속 실패 알림' 판정 테스트.

강남 사이트는 밤에 간헐적으로 연결이 끊긴다(산발 timeout). 매번 경고하면 시끄러우니,
연속 임계(기본 3회=15분)에 도달했을 때만 '다운' 1통, 복구되면 '복구' 1통을 보낸다.
판정만 떼어낸 순수함수 read_fail_decision을 박제한다.
"""
from src.main import read_fail_decision


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
