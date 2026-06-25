"""재시도 붙은 공통 세션 생성 테스트.

느린 사이트에 오래 매달려 7분 안전장치(timeout-minutes)에 걸리는 문제를 막기 위해,
재시도는 '최대 1번만'(빨리 포기)으로 줄였다. 이 테스트가 그 설정을 지킨다.
"""
from src.http_session import make_session


def test_세션에_재시도_1회가_붙는다():
    """연결/읽기 실패 시 최대 1번만 더 재시도하도록 설정돼야 한다(빨리 포기)."""
    session = make_session()
    retry = session.get_adapter("https://example.com").max_retries
    assert retry.total == 1
    assert retry.connect == 1
    assert retry.read == 1
    assert retry.backoff_factor == 0.5


def test_http도_https도_재시도가_붙는다():
    """http/https 둘 다 재시도 어댑터가 mount돼야 한다(esongpa는 verify=False 우회 포함)."""
    session = make_session()
    assert session.get_adapter("http://x.com").max_retries.total == 1
    assert session.get_adapter("https://x.com").max_retries.total == 1


def test_헤더가_세션에_적용된다():
    """전달한 헤더(User-Agent 등)가 세션에 실려야 한다."""
    session = make_session({"User-Agent": "테스트"})
    assert session.headers["User-Agent"] == "테스트"
