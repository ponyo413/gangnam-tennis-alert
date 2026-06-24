# 강남 테니스장 취소표 알림

포이·세곡 테니스장 빈자리(취소표)를 강남구 예약 사이트에서 주기적으로 확인해
**텔레그램으로 알려주는** 개인용 시스템.

- 감시 대상: 포이·강남세곡 테니스장, 송파·잠실(유수지) 테니스장, 대치유수지 테니스장
- 대치유수지: 사이트 공지(매크로 제한)에 따라 15분 간격·한국시간 08~24시에만 조회
- 원하는 시간대: 평일 저녁(18~21시) + 주말 전체
- 알림: 텔레그램 / 24시간 / **알림만**(자동예약 안 함)
- 실행: GitHub Actions(무료 클라우드) 약 5분마다

## 문서
- 설계서: `docs/superpowers/specs/2026-06-22-gangnam-tennis-alert-design.md`
- 공정표: `docs/superpowers/plans/2026-06-22-gangnam-tennis-alert-implementation.md`
- 조회 API 분석: `docs/superpowers/notes-fetcher.md`

## 로컬 실행
```bash
pip install -r requirements.txt
# .env.example을 .env로 복사하고 텔레그램 토큰 입력
python -m src.main
```

## 테스트
```bash
pytest -v
```
