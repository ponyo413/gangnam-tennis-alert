# 봇 멈춤 감지(healthchecks.io) 설정 — 최초 1회

봇이 완전히 멈추면(예: GitHub 자동실행이 60일 비활동으로 꺼짐) 스스로 알릴 수 없습니다.
무료 외부 감시 서비스가 봇의 "살아있어" 신호를 지켜보다, 끊기면 텔레그램으로 알려줍니다.

## 설정 순서

1. https://healthchecks.io 가입 (무료 — 구글 계정으로 로그인 가능)
2. **Add Check** → 이름 '테니스봇', Period(기대 주기) 5분, Grace(유예) 10분 정도로 설정
3. 그 체크의 **Ping URL** 복사 (`https://hc-ping.com/...` 형태)
4. GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
   - 이름: `HC_PING_URL`
   - 값: 복사한 Ping URL
5. healthchecks.io 체크 → **Integrations** → **Telegram** 연결
   (또는 webhook integration에 텔레그램 sendMessage 주소 등록 — 지금 쓰는 봇 토큰 재사용)
6. 끝! 봇이 10분 넘게 신호를 못 보내면 텔레그램으로 "🚨 봇 멈춤" 알림이 옵니다.

> `HC_PING_URL`을 등록하기 전까지는 핑을 건너뛰므로(워크플로의 `if` 조건), 봇 동작에 영향이 없습니다.
> 즉 코드를 먼저 배포해두고, 가입·연동은 편할 때 해도 됩니다.
