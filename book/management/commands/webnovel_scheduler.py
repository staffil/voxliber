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
INTERVAL_HOURS = 12

# 일시정지 플래그 파일 위치 (존재하면 다음 사이클 스킵)
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PAUSE_FILE = os.path.join(BASE_DIR, "scheduler_pause.flag")

# ── 웹소설 목록 ───────────────────────────────────────────────────────
WEBNOVEL_LIST = [
    {
        "book_uuid": "bf046219-8547-418b-824d-912bb9426793",
        "writing_style": "한국 웹소설 스타일, 1인칭 주인공(이은서) 시점, 빙의+이세계, 황제와의 긴장감과 설레임, 코믹하면서도 감정 묘사 풍부, 대화 비중 높이고 내면 독백 포함",
        "provider": "gpt",
        "max_episodes": 30,
    },
    {
        "book_uuid": "a7777d75-ff6f-47d9-ac8f-68062e06bd2a",
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 황제×평민녀 로맨스, 차가운 남주가 녹아가는 과정, 긴장감 넘치는 궁정 암투, 감정선 섬세하게",
        "provider": "claude",
        "max_episodes": 30,
    },
    {
        "book_uuid": "7161fcb6-5423-4780-99fd-9e0f3ee252b0",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 신데렐라 스토리 비틀기, 재벌가 내 갈등과 비밀, 로맨스와 가족 드라마 균형",
        "provider": "gemini",
        "max_episodes": 25,
    },
    {
        "book_uuid": "7e6eda70-7a4e-4bde-af54-8e8bc9d30492",
        "writing_style": "한국 웹소설 스타일, 1인칭 남주 시점, 무능 → 두뇌파 역전, 게임 시스템 비틀기, 코믹하면서도 긴장감 있는 전개, 현실적 감각으로 판타지 극복",
        "provider": "gpt",
        "max_episodes": 40,
    },
    {
        "book_uuid": "fd136c5d-8ee1-4ea9-99ca-7dfeb90078e5",
        "writing_style": "한국 웹소설 스타일, 1인칭 황녀 시점, 회귀+복수+로맨스, 지략 대결, 황실 음모, 냉철하지만 감정이 스며드는 주인공",
        "provider": "gemini",
        "max_episodes": 35,
    },
    {
        "book_uuid": "a1ff5c7c-fd69-4d8b-99bb-6054b8e450d2",
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, SF+로맨스, AI와 인간의 감정 탐구, 철학적 질문을 부드럽게 녹인 스토리, 따뜻하고 잔잔한 문체",
        "provider": "claude",
        "max_episodes": 25,
    },
    {
        "book_uuid": "bc1988eb-78a3-4f9a-9a7a-f6f581578358",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 학원+마법+코미디, 성장 스토리, 유쾌한 사건사고, 동료들과의 우정과 로맨스 힌트",
        "provider": "grok",
        "max_episodes": 30,
    },
    {
        "book_uuid": "e7515a91-2085-4ca0-a6f5-368be73a404c",
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 저주×용×로맨스, 서툰 남주의 로맨스 시도, 긴장감 있는 세계관, 판타지 설정 풍부하게",
        "provider": "gemini",
        "max_episodes": 30,
    },
    {
        "book_uuid": "a3a40766-0480-4a7c-a5cd-548912f870b7",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 사이버펑크+스릴러+로맨스, 빠른 전개, 긴장감, 과거의 비밀이 밝혀지는 구조",
        "provider": "grok",
        "max_episodes": 25,
    },
    {
        "book_uuid": "5f8c3d82-52f6-44b7-81f4-40320b084e1c",
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 공포+미스터리+로맨스, 학원 배경, 코믹한 귀신과의 일상, 반전 있는 진실 추적",
        "provider": "gpt",
        "max_episodes": 20,
    },
    {
        "book_uuid": "7bc76bd9-eea8-4e6b-9636-457046a1ab75",
        "writing_style": "한국 성인 웹소설 스타일, 1인칭 여주(강아린) 시점, 재벌 CEO와의 계약 동거, 냉혹하지만 은밀히 끌리는 남주 묘사, 긴장감 넘치는 밀당과 설레임, 선정적이고 노골적인 성인 묘사 포함, 대화 비중 높이고 내면 독백 풍부하게, 다음 화가 궁금해지는 결말",
        "provider": "grok",
        "adult": True,
        "max_episodes": 30,
    },
    # ── 신규 5권 (생성 후 UUID 업데이트 필요) ──
    # {
    #     "book_uuid": "REPLACE_AFTER_CREATE",
    #     "writing_style": "...",
    #     "provider": "gpt",
    #     "completed": False,  # True로 바꾸면 생성 중단
    # },
]


def _log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def is_paused():
    return os.path.exists(PAUSE_FILE)


def get_episode_count(book_uuid):
    """현재 에피소드 수 조회"""
    try:
        r = requests.get(
            f"{BASE_URL}/webnovels/{book_uuid}/",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            eps = data.get("episodes", data.get("contents", []))
            return len(eps) if isinstance(eps, list) else data.get("episode_count", 0)
    except Exception:
        pass
    return 0


def get_story_phase_instruction(current_count, max_episodes):
    """현재 화수/총화수 기반으로 스토리 단계 지시문 반환"""
    if max_episodes is None or current_count is None:
        return ""

    next_ep = current_count + 1
    ratio = next_ep / max_episodes  # 0.0 ~ 1.0

    # 총화수 기준 단계 경계 계산
    foreshadow_start = max(1, int(max_episodes * 0.75))  # 75%부터 암시
    climax_start     = max(1, int(max_episodes * 0.88))  # 88%부터 클라이맥스

    if next_ep >= max_episodes:
        # 최종화
        return f"""
【스토리 단계: 최종화 ({next_ep}/{max_episodes}화)】
- 이번 화가 마지막입니다. 모든 갈등과 감정선을 완전히 해소하고 독자가 만족할 수 있는 진짜 결말을 써주세요.
- 주인공의 최종 목표 달성, 핵심 관계 정리, 여운 있는 마무리 장면 포함.
- 열린 결말 금지 — 반드시 완결되는 엔딩."""

    elif next_ep >= climax_start:
        remaining = max_episodes - next_ep
        return f"""
【스토리 단계: 클라이맥스 ({next_ep}/{max_episodes}화, 남은 화수 {remaining}화)】
- 지금까지 쌓아온 갈등이 폭발하는 시점입니다.
- 결말을 내지는 말되, 최종 대결/고백/선택의 직전까지 긴장감을 최고조로 끌어올리세요.
- 이 화가 끝나면 독자가 "이제 어떻게 되는 거야?!"라고 느껴야 합니다.
- 아직 해소하지 말고, 결정적 순간 바로 전에서 끊으세요."""

    elif next_ep >= foreshadow_start:
        remaining = max_episodes - next_ep
        return f"""
【스토리 단계: 결말 암시 구간 ({next_ep}/{max_episodes}화, 남은 화수 {remaining}화)】
- 이야기가 서서히 결말을 향해 수렴하기 시작하는 시점입니다.
- 지금까지의 복선을 하나씩 회수하고, 주인공의 내면 변화를 깊이 묘사하세요.
- 갈등의 핵심이 드러나거나, 최종 결전/고백의 전조가 보이기 시작해야 합니다.
- 결말을 미리 내지 말고, "이 이야기가 어디로 가는지" 독자가 어렴풋이 느끼게 하세요.
- 이 구간에서는 반드시 한 가지 이상의 반전이나 충격적 폭로가 있어야 합니다."""

    else:
        # 3화에 한 번은 반전/서프라이즈 요소 삽입
        twist_note = ""
        if next_ep % 3 == 0:
            twist_note = "\n- 【이번 화 필수】 독자 예상을 뒤엎는 반전 요소를 하나 포함하세요: 믿었던 인물의 배신, 숨겨진 비밀 폭로, 완전히 예상 밖의 사건 전개 중 하나."

        return f"""
【스토리 단계: 전개/심화 ({next_ep}/{max_episodes}화)】
- 이야기는 아직 중반부입니다. 인물 관계와 세계관을 더 깊이 발전시키세요.
- 새로운 사건이나 등장인물로 긴장감을 유지하고, 결말은 아직 멀리 있습니다.
- 이번 화의 갈등을 해결하더라도, 더 큰 문제가 남아있거나 새로운 복선이 등장해야 합니다.
- 매화마다 작은 반전이나 예상치 못한 전개로 독자가 지루하지 않게 하세요.{twist_note}"""


def generate_episode(book_uuid, writing_style, provider="gpt", max_episodes=None, current_count=None):
    # 스토리 단계 지시문 추가
    phase_instruction = get_story_phase_instruction(current_count, max_episodes)
    is_final = max_episodes and current_count is not None and (current_count + 1) >= max_episodes

    effective_style = writing_style + phase_instruction

    try:
        r = requests.post(
            f"{BASE_URL}/webnovel/generate-episode/",
            headers=HEADERS,
            json={"book_uuid": book_uuid, "writing_style": effective_style, "provider": provider},
            timeout=180,
        )
        result = r.json()
        if r.status_code == 200 and result.get("success"):
            ep = result.get("data", {})
            suffix = " 🔚 [완결]" if is_final else ""
            _log(f"  ✅ {ep.get('episode_number')}화: {ep.get('episode_title')} ({ep.get('text_length')}자) [{provider}]{suffix}")
            return True
        else:
            _log(f"  ❌ 실패: {result.get('error', r.status_code)}")
            return False
    except Exception as e:
        _log(f"  ❌ 오류: {e}")
        return False


def run_once():
    _log("웹소설 자동 생성 시작")
    ok, fail, skip = 0, 0, 0
    for novel in WEBNOVEL_LIST:
        uuid = novel["book_uuid"]

        # 수동 완결 플래그
        if novel.get("completed", False):
            _log(f"  ⏭  {uuid[:8]}... [완결 — 스킵]")
            skip += 1
            continue

        max_ep = novel.get("max_episodes")

        # max_episodes 설정된 경우 현재 화수 확인
        if max_ep:
            current = get_episode_count(uuid)
            if current >= max_ep:
                _log(f"  ⏭  {uuid[:8]}... [{current}/{max_ep}화 — 목표 달성, 스킵]")
                skip += 1
                continue
        else:
            current = None

        # 19금 책은 무조건 grok 사용
        provider = "grok" if novel.get("adult", False) else novel.get("provider", "gpt")

        ep_info = f"{current+1}/{max_ep}화" if max_ep and current is not None else "다음화"
        _log(f"  📖 {uuid[:8]}... [{provider}] {ep_info}")

        if generate_episode(uuid, novel["writing_style"], provider, max_ep, current):
            ok += 1
        else:
            fail += 1

    _log(f"완료 — 성공 {ok} / 실패 {fail} / 스킵 {skip}")


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
