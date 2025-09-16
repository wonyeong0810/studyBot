# studyBot
공부봇

## 요구 사항
- Python 3.10+
- 패키지: `discord.py`
- Discord Application + Bot (토큰)
- Discord Developer Portal에서 Message Content Intent 활성화

## 설치
```bash
# 가상환경(선택)
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate

# 의존성 설치
pip install -U discord.py
```

## 환경 변수 설정
이 코드는 `.env` 파일을 자동으로 읽지 않습니다. 환경변수 `DISCORD_TOKEN`을 셸에서 직접 설정하세요. 노출된 토큰은 즉시 재발급(rotate) 하세요.

- macOS/Linux
```bash
export DISCORD_TOKEN="<디스코드_봇_토큰>"
python bot.py
```

- Windows (PowerShell)
```powershell
setx DISCORD_TOKEN "<디스코드_봇_토큰>"
# 새 터미널을 열고
python bot.py
```

또는 1회성 실행:
```bash
DISCORD_TOKEN="<디스코드_봇_토큰>" python bot.py
```

## 실행
```bash
python bot.py
```
- 진입점: [`main`](/home/wonyeong/project/studyBot/bot.py)
- 봇 이벤트/루프: [`on_message`](/home/wonyeong/project/studyBot/bot.py), [`daily_check`](/home/wonyeong/project/studyBot/bot.py)
- 데이터 저장: [`DataStore`](/home/wonyeong/project/studyBot/bot.py) → `data.json` 자동 생성

## 디스코드 서버에서 사용법
1. 봇을 서버에 초대하고, Developer Portal → Bot → Privileged Gateway Intents에서 “Message Content Intent” 활성화.
2. 서버에서 관리자 권한으로 인증 채널 설정:
   - `!study-channel #인증채널`
3. 참가자 등록:
   - `!study-join`
4. 인증 방법:
   - 설정한 채널에 이미지(사진) 첨부로 올리면 자동 인증됩니다.
5. 기타 명령:
   - `!study-leave` 스터디 탈퇴
   - `!study-status [@유저]` 현재 벌점 확인
   - `!study-check [@유저]` 오늘 인증 여부 확인
   - `!study-leaderboard` 벌점 랭킹
   - `!study-help` 도움말

## 동작 개요
- 매일 00:05(KST) 전날 미인증자에게 1,000원 벌점 부과 후 결과를 채널에 공지합니다. 스케줄러: [`daily_check`](/home/wonyeong/project/studyBot/bot.py)
- 타임존: Asia/Seoul
- 데이터 파일: `data.json` (동일 디렉터리)

## 보안 주의
- 토큰은 절대 외부에 공개/커밋하지 마세요. 노출 시 즉시 재발급하세요.
