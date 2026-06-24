"""일시적 연결 끊김을 흡수하는 '재시도' 세션 — 강남·esongpa 조회 공통.

강남 사이트가 밤에 간헐적으로 연결이 끊긴다(ConnectTimeout). 한 번에 포기하지 않고
잠깐 쉬었다 최대 2번 더 시도해, 잠깐 끊김에는 빈자리를 놓치지 않게 한다.
(진짜 장시간 다운이면 재시도해도 실패 → main의 '연속 실패 카운트'가 받아준다.)
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_session(headers=None):
    """재시도가 붙은 requests 세션을 만든다.

    연결(connect)·읽기(read) 실패와 서버 일시오류(5xx)에 대해 최대 2번 더 시도한다.
    backoff_factor=1 → 재시도 간격 0초 → 1초 → 2초(점점 길게). 첫 시도 성공 시 재시도 없음.
    """
    session = requests.Session()
    if headers:
        session.headers.update(headers)
    retry = Retry(
        total=2, connect=2, read=2,                # 최대 2번 더 재시도
        backoff_factor=1,                          # 재시도 간격: 0s → 1s → 2s
        status_forcelist=(500, 502, 503, 504),     # 서버 일시 오류도 재시도
        allowed_methods=frozenset(["GET", "POST"]),  # esongpa 로그인(POST)도 재시도
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
