"""
웹소설 자동 생성 스케줄러 — Django Management Command

사용법:
  python manage.py webnovel_scheduler start    # 백그라운드 루프 시작
  python manage.py webnovel_scheduler once     # 한 번만 실행
  python manage.py webnovel_scheduler pause    # 일시정지 (다음 사이클부터 스킵)
  python manage.py webnovel_scheduler resume   # 재개
  python manage.py webnovel_scheduler status   # 현재 상태 확인

서버에서 상시 실행:
  nohup python manage.py webnovel_scheduler start >> /var/log/webnovel_scheduler.log 2>&1 &

systemd 사용 시: /etc/systemd/system/webnovel_scheduler.service 참고
"""
import time
import requests
import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand

# ── 설정 ──────────────────────────────────────────────────────────────
API_KEY = "59DQqKqImxvNkePzZE70_7-qCIaU00PYor9ubKtgeX5DYmzn3EbjdenZyo3iudC1"
BASE_URL = "https://voxliber.ink/api/v1"
HEADERS  = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
INTERVAL_HOURS = 4

# 일시정지 플래그 파일 위치 (존재하면 다음 사이클 스킵)
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PAUSE_FILE = os.path.join(BASE_DIR, "scheduler_pause.flag")

# ── 웹소설 목록 ───────────────────────────────────────────────────────
WEBNOVEL_LIST = [
    {
        "book_uuid": "bf046219-8547-418b-824d-912bb9426793",
        "writing_style": "한국 웹소설 스타일, 1인칭 주인공(이은서) 시점, 빙의+이세계, 황제와의 긴장감과 설레임, 코믹하면서도 감정 묘사 풍부, 대화 비중 높이고 내면 독백 포함",
        "provider": "gpt",
    },
    {
        "book_uuid": "a7777d75-ff6f-47d9-ac8f-68062e06bd2a",
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 황제×평민녀 로맨스, 차가운 남주가 녹아가는 과정, 긴장감 넘치는 궁정 암투, 감정선 섬세하게",
        "provider": "claude",
    },
    {
        "book_uuid": "7161fcb6-5423-4780-99fd-9e0f3ee252b0",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 신데렐라 스토리 비틀기, 재벌가 내 갈등과 비밀, 로맨스와 가족 드라마 균형",
        "provider": "gemini",
    },
    {
        "book_uuid": "7e6eda70-7a4e-4bde-af54-8e8bc9d30492",
        "writing_style": "한국 웹소설 스타일, 1인칭 남주 시점, 무능 → 두뇌파 역전, 게임 시스템 비틀기, 코믹하면서도 긴장감 있는 전개, 현실적 감각으로 판타지 극복",
        "provider": "gpt",
    },
    {
        "book_uuid": "fd136c5d-8ee1-4ea9-99ca-7dfeb90078e5",
        "writing_style": "한국 웹소설 스타일, 1인칭 황녀 시점, 회귀+복수+로맨스, 지략 대결, 황실 음모, 냉철하지만 감정이 스며드는 주인공",
        "provider": "gemini",
    },
    {
        "book_uuid": "a1ff5c7c-fd69-4d8b-99bb-6054b8e450d2",
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, SF+로맨스, AI와 인간의 감정 탐구, 철학적 질문을 부드럽게 녹인 스토리, 따뜻하고 잔잔한 문체",
        "provider": "claude",
    },
    {
        "book_uuid": "bc1988eb-78a3-4f9a-9a7a-f6f581578358",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 학원+마법+코미디, 성장 스토리, 유쾌한 사건사고, 동료들과의 우정과 로맨스 힌트",
        "provider": "grok",
    },
    {
        "book_uuid": "e7515a91-2085-4ca0-a6f5-368be73a404c",
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 저주×용×로맨스, 서툰 남주의 로맨스 시도, 긴장감 있는 세계관, 판타지 설정 풍부하게",
        "provider": "gemini",
    },
    {
        "book_uuid": "a3a40766-0480-4a7c-a5cd-548912f870b7",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 사이버펑크+스릴러+로맨스, 빠른 전개, 긴장감, 과거의 비밀이 밝혀지는 구조",
        "provider": "grok",
    },
    {
        "book_uuid": "5f8c3d82-52f6-44b7-81f4-40320b084e1c",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 공포+미스터리+로맨스, 학원 배경, 코믹한 귀신과의 일상, 반전 있는 진실 추적",
        "provider": "gpt",
    },
    {
        "book_uuid": "7bc76bd9-eea8-4e6b-9636-457046a1ab75",
        "writing_style": "한국 성인 웹소설 스타일, 1인칭 여주(강아린) 시점, 재벌 CEO와의 계약 동거, 냉혹하지만 은밀히 끌리는 남주 묘사, 긴장감 넘치는 밀당과 설레임, 선정적이고 노골적인 성인 묘사 포함, 대화 비중 높이고 내면 독백 풍부하게, 다음 화가 궁금해지는 결말",
        "provider": "grok",
    },
]


def _log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def is_paused():
    return os.path.exists(PAUSE_FILE)


def generate_episode(book_uuid, writing_style, provider="gpt"):
    try:
        r = requests.post(
            f"{BASE_URL}/webnovel/generate-episode/",
            headers=HEADERS,
            json={"book_uuid": book_uuid, "writing_style": writing_style, "provider": provider},
            timeout=180,
        )
        result = r.json()
        if r.status_code == 200 and result.get("success"):
            ep = result.get("data", {})
            _log(f"  ✅ {ep.get('episode_number')}화: {ep.get('episode_title')} ({ep.get('text_length')}자) [{provider}]")
            return True
        else:
            _log(f"  ❌ 실패: {result.get('error', r.status_code)}")
            return False
    except Exception as e:
        _log(f"  ❌ 오류: {e}")
        return False


def run_once():
    _log("웹소설 자동 생성 시작")
    ok, fail = 0, 0
    for novel in WEBNOVEL_LIST:
        provider = novel.get("provider", "gpt")
        _log(f"  📖 {novel['book_uuid'][:8]}... [{provider}]")
        if generate_episode(novel["book_uuid"], novel["writing_style"], provider):
            ok += 1
        else:
            fail += 1
    _log(f"완료 — 성공 {ok} / 실패 {fail}")


def run_loop():
    _log(f"스케줄러 시작 — {INTERVAL_HOURS}시간 간격")
    while True:
        if is_paused():
            _log("⏸  일시정지 상태 — 1시간 후 재확인")
            time.sleep(3600)
            continue
        run_once()
        _log(f"다음 실행까지 {INTERVAL_HOURS}시간 대기...")
        # 대기 중에도 pause 신호 1분마다 확인
        for _ in range(INTERVAL_HOURS * 60):
            time.sleep(60)
            if is_paused():
                _log("⏸  대기 중 일시정지 감지")
                break


class Command(BaseCommand):
    help = "웹소설 자동 생성 스케줄러"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["start", "once", "pause", "resume", "status"],
            help="start=루프시작 / once=1회실행 / pause=일시정지 / resume=재개 / status=상태확인",
        )

    def handle(self, *args, **options):
        action = options["action"]

        if action == "start":
            self.stdout.write("🚀 스케줄러 루프 시작 (Ctrl+C 또는 pause 명령으로 정지)")
            run_loop()

        elif action == "once":
            run_once()

        elif action == "pause":
            with open(PAUSE_FILE, "w") as f:
                f.write(datetime.now().isoformat())
            self.stdout.write(self.style.WARNING("⏸  스케줄러 일시정지 — 현재 사이클 완료 후 멈춤"))

        elif action == "resume":
            if os.path.exists(PAUSE_FILE):
                os.remove(PAUSE_FILE)
                self.stdout.write(self.style.SUCCESS("▶️  스케줄러 재개"))
            else:
                self.stdout.write("이미 실행 중 상태입니다.")

        elif action == "status":
            if is_paused():
                with open(PAUSE_FILE) as f:
                    since = f.read().strip()
                self.stdout.write(self.style.WARNING(f"⏸  일시정지 중 (since: {since})"))
            else:
                self.stdout.write(self.style.SUCCESS("▶️  실행 중 (pause 플래그 없음)"))
