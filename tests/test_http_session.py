"""재시도 붙은 공통 세션 생성 테스트.

강남 사이트가 밤에 간헐적으로 연결이 끊긴다(ConnectTimeout). 한 번에 포기하지 않고
최대 2번 더 재시도하도록 세션에 재시도 설정이 붙어야 한다.
"""
from src.http_session import make_session


def test_세션에_재시도_2회가_붙는다():
    """연결/읽기 실패 시 최대 2번 더 재시도하도록 설정돼야 한다."""
    session = make_session()
    retry = session.get_adapter("https://example.com").max_retries
    assert retry.total == 2
    assert retry.connect == 2
    assert retry.read == 2


def test_http도_https도_재시도가_붙는다():
    """http/https 둘 다 재시도 어댑터가 mount돼야 한다(esongpa는 verify=False 우회 포함)."""
    session = make_session()
    assert session.get_adapter("http://x.com").max_retries.total == 2
    assert session.get_adapter("https://x.com").max_retries.total == 2


def test_헤더가_세션에_적용된다():
    """전달한 헤더(User-Agent 등)가 세션에 실려야 한다."""
    session = make_session({"User-Agent": "테스트"})
    assert session.headers["User-Agent"] == "테스트"
