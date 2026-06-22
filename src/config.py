"""시스템 설정값. 대상 코트·원하는 시간대·텔레그램 토큰을 한곳에 모음."""
import os
from dotenv import load_dotenv

load_dotenv()  # 로컬에서 .env 파일을 읽어 환경변수로 올림

# ─────────────────────────────────────────────────────────────
# 감시할 코트 (docs/superpowers/notes-fetcher.md 실측 코드)
#   - 포이: company_code GNCC06, 코트A(15)·코트B(16)
#   - 세곡: company_code GNCC33, part 04(테니스장), 1~4번 코트(13~16)
#     ※ 세곡 part 03은 축구장이라 제외
# 나중에 봉은(GNCC05)을 추가하려면 여기에 한 칸 더.
# ─────────────────────────────────────────────────────────────
COURTS = [
    {
        "center": "포이",
        "comcd": "GNCC06",
        "part": "04",
        "places": {"15": "코트A", "16": "코트B"},
    },
    {
        "center": "세곡",
        "comcd": "GNCC33",
        "part": "04",
        "places": {"13": "1번코트", "14": "2번코트", "15": "3번코트", "16": "4번코트"},
    },
]

# 평일 저녁 시간 범위 (시작시각 기준: 18·19·20·21시 시작 = 18시~22시 직전)
WEEKDAY_EVENING_START = 18
WEEKDAY_EVENING_END = 22

# 텔레그램 토큰 (코드에 직접 안 적고 환경변수/금고에서 가져옴)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# 강남구 예약 사이트 (알림 메시지에 넣을 링크)
RESERVE_URL = "https://life.gangnam.go.kr/fmcs/1"
