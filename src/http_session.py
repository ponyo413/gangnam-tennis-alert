"""일시적 연결 끊김을 흡수하는 '재시도' 세션 — 강남·esongpa·대치 조회 공통.

강남 사이트가 밤에 간헐적으로 연결이 끊긴다(ConnectTimeout). 한 번에 포기하지 않고
잠깐 쉬었다 최대 1번 더 시도해, 잠깐 끊김에는 빈자리를 놓치지 않게 한다.
(예전엔 2번 재시도였으나, 여러 사이트가 느릴 때 대기·재시도가 누적되어 7분 안전장치에
 걸리는 문제가 있어 1번으로 줄였다. 진짜 장시간 다운은 main의 '연속 실패 카운트'가 받아준다.)
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_session(headers=None):
    """재시도가 붙은 requests 세션을 만든다.

    연결(connect)·읽기(read) 실패와 서버 일시오류(5xx)에 대해 최대 1번 더 시도한다.
    (재시도가 1회뿐이면 urllib3가 첫 재시도 전 대기를 건너뛰므로 backoff는 실제로는 적용되지 않는다.
     backoff_factor=0.5는 추후 재시도를 늘릴 때를 대비한 값.) 첫 시도 성공 시 재시도 없음.
    """
    session = requests.Session()
    if headers:
        session.headers.update(headers)
    retry = Retry(
        total=1, connect=1, read=1,                # 최대 1번만 더 재시도(빨리 포기)
        backoff_factor=0.5,                        # 재시도 간 대기(재시도 1회에선 미적용·확장 대비)
        status_forcelist=(500, 502, 503, 504),     # 서버 일시 오류도 재시도
        allowed_methods=frozenset(["GET", "POST"]),  # esongpa 로그인(POST)도 재시도
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
