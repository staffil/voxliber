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
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand

# ── 설정 ──────────────────────────────────────────────────────────────
API_KEY = "59DQqKqImxvNkePzZE70_7-qCIaU00PYor9ubKtgeX5DYmzn3EbjdenZyo3iudC1"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = "https://voxliber.ink/api/v1"
HEADERS  = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
INTERVAL_HOURS = 12
WEEKLY_CREATION_DAYS = 7   # 7일마다 신규 책 5권 생성
WEEKLY_CREATION_COUNT = 5  # 한 번에 생성할 책 수

# 파일 위치
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
PAUSE_FILE        = os.path.join(BASE_DIR, "scheduler_pause.flag")
WEEKLY_STATE_FILE = os.path.join(BASE_DIR, "weekly_creation_state.json")
AUTO_BOOKS_FILE   = os.path.join(BASE_DIR, "auto_created_books.json")
BOOK_CONTEXT_FILE = os.path.join(BASE_DIR, "book_context_cache.json")  # 캐릭터/플롯 캐시

# ── 기존 웹소설 스타일 설정 (UUID → 설정) ────────────────────────────
# 새로 추가된 책은 자동으로 DB에서 읽어오므로 여기에 추가 불필요
STYLE_CONFIG = {
    "bf046219-8547-418b-824d-912bb9426793": {
        "writing_style": "한국 웹소설 스타일, 1인칭 주인공(이은서) 시점, 빙의+이세계, 황제와의 긴장감과 설레임, 코믹하면서도 감정 묘사 풍부, 대화 비중 높이고 내면 독백 포함",
        "provider": "gpt", "max_episodes": 30,
    },
    "a7777d75-ff6f-47d9-ac8f-68062e06bd2a": {
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 황제×평민녀 로맨스, 차가운 남주가 녹아가는 과정, 긴장감 넘치는 궁정 암투, 감정선 섬세하게",
        "provider": "claude", "max_episodes": 30,
    },
    "7161fcb6-5423-4780-99fd-9e0f3ee252b0": {
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 신데렐라 스토리 비틀기, 재벌가 내 갈등과 비밀, 로맨스와 가족 드라마 균형",
        "provider": "gemini", "max_episodes": 25,
    },
    "7e6eda70-7a4e-4bde-af54-8e8bc9d30492": {
        "writing_style": "한국 웹소설 스타일, 1인칭 남주 시점, 무능 → 두뇌파 역전, 게임 시스템 비틀기, 코믹하면서도 긴장감 있는 전개, 현실적 감각으로 판타지 극복",
        "provider": "gpt", "max_episodes": 40,
    },
    "fd136c5d-8ee1-4ea9-99ca-7dfeb90078e5": {
        "writing_style": "한국 웹소설 스타일, 1인칭 황녀 시점, 회귀+복수+로맨스, 지략 대결, 황실 음모, 냉철하지만 감정이 스며드는 주인공",
        "provider": "gemini", "max_episodes": 35,
    },
    "a1ff5c7c-fd69-4d8b-99bb-6054b8e450d2": {
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, SF+로맨스, AI와 인간의 감정 탐구, 철학적 질문을 부드럽게 녹인 스토리, 따뜻하고 잔잔한 문체",
        "provider": "claude", "max_episodes": 25,
    },
    "bc1988eb-78a3-4f9a-9a7a-f6f581578358": {
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 학원+마법+코미디, 성장 스토리, 유쾌한 사건사고, 동료들과의 우정과 로맨스 힌트",
        "provider": "grok", "max_episodes": 30,
    },
    "e7515a91-2085-4ca0-a6f5-368be73a404c": {
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 저주×용×로맨스, 서툰 남주의 로맨스 시도, 긴장감 있는 세계관, 판타지 설정 풍부하게",
        "provider": "gemini", "max_episodes": 30,
    },
    "a3a40766-0480-4a7c-a5cd-548912f870b7": {
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 사이버펑크+스릴러+로맨스, 빠른 전개, 긴장감, 과거의 비밀이 밝혀지는 구조",
        "provider": "grok", "max_episodes": 25,
    },
    "5f8c3d82-52f6-44b7-81f4-40320b084e1c": {
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 공포+미스터리+로맨스, 학원 배경, 코믹한 귀신과의 일상, 반전 있는 진실 추적",
        "provider": "gpt", "max_episodes": 20,
    },
    "7bc76bd9-eea8-4e6b-9636-457046a1ab75": {
        "writing_style": "한국 성인 웹소설 스타일, 1인칭 여주(강아린) 시점, 재벌 CEO와의 계약 동거, 냉혹하지만 은밀히 끌리는 남주 묘사, 긴장감 넘치는 밀당과 설레임, 선정적이고 노골적인 성인 묘사 포함, 대화 비중 높이고 내면 독백 풍부하게, 다음 화가 궁금해지는 결말",
        "provider": "grok", "adult": True, "max_episodes": 30,
    },
    "43b84eec-ceff-41d2-9239-57ce99cfef4e": {
        "writing_style": "한국 웹소설 스타일, 1인칭 주인공 시점, 직장인 개그+이세계 판타지, 현실 직장 경험을 판타지에 접목한 코미디, 주인공의 냉소적 내면 독백 풍부, 대화 비중 높이고 예상 밖의 전개로 웃음 유발",
        "provider": "gpt", "max_episodes": 30,
    },
    "3ec8eae1-45c8-4193-90c0-146959f90121": {
        "writing_style": "한국 웹소설 스타일, 3인칭 전지적 시점, 다크 판타지+미스터리, 신비롭고 음울한 분위기, 복선과 반전을 촘촘히 배치, 인물들의 숨겨진 의도가 조금씩 드러나는 구조, 세계관 묘사 풍부",
        "provider": "grok", "max_episodes": 30,
    },
    "7906392a-ef67-4589-8ad1-e7bad6a5cfc5": {
        "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 강한 여주가 모든 걸 뒤집는 복수극, 액션과 정치 암투 균형, 차갑고 계산적인 여주와 예상 밖의 남주 케미, 긴장감 넘치는 전개",
        "provider": "gemini", "max_episodes": 35,
    },
    "1fce1aa2-58a4-487c-89d0-4e0c86ddb20a": {
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 포스트아포칼립스+서바이벌 스릴러, 다양한 인간 군상의 욕망과 갈등, 현실적인 생존 묘사, 긴장감과 극적 반전, 유머와 공포가 교차하는 전개",
        "provider": "gpt", "max_episodes": 30,
    },
    "3d89aeff-9112-45bd-9250-3441607b9c98": {
        "writing_style": "한국 웹소설 스타일, 3인칭 시점, 현대 배경 다크 판타지+미스터리+로맨스, 예술적 감수성과 공포 분위기 균형, 저주의 비밀이 서서히 밝혀지는 구조, 히로인의 등장과 감정선 섬세하게",
        "provider": "grok", "max_episodes": 25,
    },
}

# auto_created_books.json 로드 후 STYLE_CONFIG에 병합
def _merge_auto_books_to_config():
    """자동 생성된 책 정보를 STYLE_CONFIG에 병합"""
    auto = load_auto_books()
    merged = dict(STYLE_CONFIG)
    for b in auto:
        uid = b.get("book_uuid", "")
        if uid and uid not in merged:
            merged[uid] = {
                "writing_style": b.get("writing_style", "한국 웹소설 스타일, 감성적이고 몰입감 있는 전개"),
                "provider": b.get("provider", "gpt"),
                "max_episodes": b.get("max_episodes", 30),
                "adult": b.get("adult", False),
                "completed": b.get("completed", False),
                "name": b.get("name", ""),
            }
    return merged


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


def load_book_context_cache():
    try:
        with open(BOOK_CONTEXT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_book_context_cache(cache):
    with open(BOOK_CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def generate_book_context(book_uuid, book_name, description, writing_style):
    """GPT-4o-mini로 캐릭터 시트 + 플롯 아웃라인 자동 생성 후 캐시"""
    cache = load_book_context_cache()
    if book_uuid in cache:
        return cache[book_uuid]

    if not OPENAI_API_KEY:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=[
                {
                    "role": "system",
                    "content": "한국 웹소설 편집자입니다. 소설의 핵심 정보를 간결하게 정리합니다."
                },
                {
                    "role": "user",
                    "content": f"""다음 웹소설의 캐릭터 시트와 플롯 아웃라인을 작성하세요.

제목: {book_name}
설명: {description}
문체/장르: {writing_style[:200]}

아래 형식으로 출력하세요 (다른 설명 없이):

【주요 등장인물】
- 주인공: (이름, 나이, 외모 특징 1줄, 성격 1줄, 특이사항)
- 남/여주2: (이름, 외모 특징 1줄, 성격 1줄)
- 조연1~2: (이름, 역할 1줄)

【세계관 핵심 설정】
(3줄 이내. 마법 시스템, 시대적 배경, 고유 용어 등)

【전체 플롯 아웃라인】
- 도입부(1~25%):
- 갈등 심화(26~50%):
- 클라이맥스 준비(51~75%):
- 결말(76~100%): """
                }
            ]
        )
        context_text = resp.choices[0].message.content.strip()
        cache[book_uuid] = context_text
        save_book_context_cache(cache)
        _log(f"  📋 '{book_name}' 캐릭터/플롯 생성 완료 (캐시 저장)")
        return context_text
    except Exception as e:
        _log(f"  ⚠️  캐릭터/플롯 생성 실패: {e}")
        return None


def generate_cover_dalle3(book_uuid, book_name, description, writing_style):
    """DALL-E 3 HD로 웹소설 표지 생성 후 업로드"""
    if not OPENAI_API_KEY:
        return False
    try:
        import requests as _req
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 장르/분위기 추출 (writing_style 앞 100자)
        genre_hint = writing_style[:100]

        # GPT-4o-mini로 커버 프롬프트 생성
        pr = client.chat.completions.create(
            model='gpt-4o-mini', max_tokens=200,
            messages=[
                {'role': 'system', 'content': 'Expert book cover prompt writer for DALL-E 3. Output ONLY the English prompt, no explanations.'},
                {'role': 'user', 'content': f'Create a DALL-E 3 HD prompt for a Korean webtoon/Japanese anime style novel cover (portrait 2:3 ratio). Title: "{book_name}". Description: {description[:200]}. Genre: {genre_hint}. REQUIRED style: Korean webtoon art style combined with Japanese anime illustration — large expressive eyes, soft cel-shading, clean linework, pastel and saturated color palette, detailed hair, beautiful Korean anime characters. Dramatic cinematic composition, atmospheric lighting, professional book cover layout. Absolutely NO text, letters, or watermarks in the image.'}
            ]
        )
        img_prompt = pr.choices[0].message.content.strip()

        # DALL-E 3 HD 생성
        ir = client.images.generate(
            model='dall-e-3',
            prompt=img_prompt,
            size='1024x1792',
            quality='hd',
            n=1,
        )
        img_url = ir.data[0].url
        img_data = _req.get(img_url, timeout=60).content

        # 서버 업로드
        up = _req.post(
            f"{BASE_URL}/upload-book-cover/",
            headers={"X-API-Key": API_KEY},
            data={"book_uuid": book_uuid},
            files={"cover_image": ("cover.jpg", img_data, "image/jpeg")},
            timeout=30,
        )
        if up.json().get("success"):
            _log(f"  🖼️  표지 생성 완료: {book_name}")
            return True
        else:
            _log(f"  ⚠️  표지 업로드 실패: {up.json()}")
            return False
    except Exception as e:
        _log(f"  ⚠️  표지 생성 실패: {e}")
        return False


def mark_book_completed(book_uuid):
    """책 완결 상태로 업데이트"""
    try:
        r = requests.post(
            f"{BASE_URL}/update-book-metadata/",
            headers=HEADERS,
            json={"book_uuid": book_uuid, "status": "completed"},
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("success"):
            return True
    except Exception:
        pass
    return False


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


def generate_episode(book_uuid, writing_style, provider="gpt", max_episodes=None, current_count=None, book_context=None):
    # 캐릭터/플롯 컨텍스트 삽입
    context_note = ""
    if book_context:
        context_note = f"\n\n【작품 설정 — 반드시 일관되게 유지】\n{book_context}\n"

    # 스토리 단계 지시문 추가
    phase_instruction = get_story_phase_instruction(current_count, max_episodes)
    is_final = max_episodes and current_count is not None and (current_count + 1) >= max_episodes

    effective_style = writing_style + context_note + phase_instruction

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


def _generate_writing_style_for_book(book_name, description, genres):
    """STYLE_CONFIG에 없는 새 책의 writing_style을 GPT로 자동 생성"""
    if not OPENAI_API_KEY:
        return f"한국 웹소설 스타일, {book_name} 장르에 맞는 몰입감 있는 전개, 대화 비중 높이고 감정 묘사 풍부"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=300,
            messages=[
                {"role": "system", "content": "한국 웹소설 편집자. 소설 문체 지시문을 1~2문장으로 작성합니다."},
                {"role": "user", "content": f"제목: {book_name}\n설명: {description}\n장르: {', '.join(genres)}\n\n이 소설의 writing_style 지시문을 한국 웹소설 스타일로 작성하세요. 시점, 분위기, 대화 비중, 감정 묘사 방향 포함. 한 문단으로."}
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return f"한국 웹소설 스타일, {book_name} 장르의 몰입감 있는 전개, 대화 비중 높이고 감정 묘사 풍부"


def load_all_webnovels_from_db():
    """DB에서 전체 웹소설 목록을 읽어 스타일 설정과 병합"""
    from book.models import Books
    config = _merge_auto_books_to_config()
    novels = []

    db_books = Books.objects.filter(book_type='webnovel').order_by('created_at')
    for book in db_books:
        uid = str(book.public_uuid)
        cfg = config.get(uid)

        if cfg:
            # 기존 설정 있음
            novels.append({
                "book_uuid": uid,
                "name": book.name,
                "writing_style": cfg["writing_style"],
                "provider": cfg.get("provider", "gpt"),
                "max_episodes": cfg.get("max_episodes", 30),
                "adult": cfg.get("adult", False),
                "completed": cfg.get("completed", False),
            })
        else:
            # 신규 책 — writing_style 자동 생성
            _log(f"  새 책 발견: 『{book.name}』({uid[:8]}) — writing_style 자동 생성")
            genres = list(book.genres.values_list('name', flat=True))
            description = getattr(book, 'description', '') or ''
            writing_style = _generate_writing_style_for_book(book.name, description, genres)
            novels.append({
                "book_uuid": uid,
                "name": book.name,
                "writing_style": writing_style,
                "provider": "gpt",
                "max_episodes": 30,
                "adult": False,
                "completed": False,
            })

    _log(f"DB 웹소설 {len(novels)}권 로드 완료")
    return novels


def run_once():
    _log("웹소설 자동 생성 시작")
    ok, fail, skip = 0, 0, 0

    # DB에서 전체 웹소설 자동 로드
    all_novels = load_all_webnovels_from_db()

    for novel in all_novels:
        uuid = novel.get("book_uuid", "")
        if not uuid:
            continue

        # 수동 완결 플래그
        if novel.get("completed", False):
            _log(f"  ⏭  {novel.get('name', uuid[:8])} [완결 — 스킵]")
            skip += 1
            continue

        max_ep = novel.get("max_episodes")

        # max_episodes 설정된 경우 현재 화수 확인
        if max_ep:
            current = get_episode_count(uuid)
            if current >= max_ep:
                _log(f"  ⏭  {novel.get('name', uuid[:8])} [{current}/{max_ep}화 — 목표 달성, 스킵]")
                if mark_book_completed(uuid):
                    _log(f"  ✅ 완결 처리 완료: {novel.get('name', uuid[:8])}")
                skip += 1
                continue
        else:
            current = None

        # 19금 책은 무조건 grok 사용
        provider = "grok" if novel.get("adult", False) else novel.get("provider", "gpt")

        # 캐릭터 시트 + 플롯 아웃라인 자동 생성 (첫 실행 시 1회, 이후 캐시)
        book_context = generate_book_context(
            uuid,
            novel.get("name", uuid[:8]),
            "",
            novel["writing_style"],
        )

        ep_info = f"{current+1}/{max_ep}화" if max_ep and current is not None else "다음화"
        _log(f"  📖 『{novel.get('name', uuid[:8])}』 [{provider}] {ep_info}")

        if generate_episode(uuid, novel["writing_style"], provider, max_ep, current, book_context):
            ok += 1
        else:
            fail += 1

    _log(f"완료 — 성공 {ok} / 실패 {fail} / 스킵 {skip}")


def load_weekly_state():
    try:
        with open(WEEKLY_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_creation": None}


def save_weekly_state(state):
    with open(WEEKLY_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_auto_books():
    """자동 생성된 책 목록 로드"""
    try:
        with open(AUTO_BOOKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_auto_books(books):
    with open(AUTO_BOOKS_FILE, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)


def generate_book_concepts():
    """GPT로 새로운 웹소설 아이디어 5개 생성"""
    if not OPENAI_API_KEY:
        _log("❌ OPENAI_API_KEY 없음 — 기본 아이디어 사용")
        return _default_book_concepts()

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=3000,
            messages=[
                {
                    "role": "system",
                    "content": "한국 웹소설 기획자입니다. 독자들이 열광할 독창적인 웹소설 아이디어를 제안합니다."
                },
                {
                    "role": "user",
                    "content": """한국 웹소설 신작 5개의 기획안을 JSON 배열로 작성하세요.
기존 흔한 소재(빙의, 이세계전생, 황제로맨스)는 피하고 참신한 장르를 선택하세요.

각 항목 형식:
{
  "name": "제목",
  "description": "2-3문장 소개 (독자가 바로 읽고 싶게)",
  "genres": ["장르1", "장르2"],
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "writing_style": "상세한 문체/시점/분위기 지시 (한국 웹소설 스타일 명시)",
  "provider": "gpt 또는 grok 또는 gemini 중 장르에 맞게",
  "max_episodes": 25~40 사이 숫자,
  "adult": false
}

조건:
1. 5개 중 반드시 1개는 "adult": true인 19세 이상 성인 로맨스 소설을 포함하세요.
   - 성인작의 writing_style에는 "성인 로맨스, 관능적 긴장감, 선정적 분위기 포함" 문구를 넣고 provider는 "grok"으로 설정하세요.
   - 성인작 장르 예시: 재벌로맨스, 금지된사랑, 계약연애, 복수로맨스, 나이차로맨스 등
2. 나머지 4개는 다양한 장르(현대판타지, 스포츠, 요리, 음악, 역사, 공포, SF, 스릴러 등)를 섞어주세요.
JSON 배열만 출력하세요. 마크다운 코드블록 없이."""
                }
            ]
        )
        text = resp.choices[0].message.content.strip()
        # JSON 배열 파싱
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        concepts = json.loads(text)
        _log(f"✅ GPT로 {len(concepts)}개 아이디어 생성 완료")
        return concepts[:WEEKLY_CREATION_COUNT]
    except Exception as e:
        _log(f"❌ 아이디어 생성 실패: {e} — 기본 아이디어 사용")
        return _default_book_concepts()


def _default_book_concepts():
    """GPT 실패 시 기본 아이디어 풀에서 랜덤 선택"""
    import random
    pool = [
        {
            "name": "셰프의 마지막 레시피",
            "description": "국가대표 요리사가 은퇴 직전 잃어버린 첫사랑의 레시피를 찾아 나서는 이야기. 음식 하나하나에 숨겨진 기억과 사랑.",
            "genres": ["로맨스", "일상"], "tags": ["요리", "로맨스", "추억", "셰프", "성장"],
            "writing_style": "한국 웹소설 스타일, 3인칭 시점, 음식과 감정을 연결하는 감성적 묘사, 현실적 요리 묘사와 로맨스 균형",
            "provider": "gemini", "max_episodes": 25,
        },
        {
            "name": "프로게이머의 두 번째 봄",
            "description": "부상으로 은퇴한 전설의 프로게이머. 5년 후, 그의 제자가 세계무대에 섰다. 스승으로서, 그는 다시 현역으로 돌아올 것인가.",
            "genres": ["스포츠", "성장"], "tags": ["게임", "은퇴", "복귀", "사제", "도전"],
            "writing_style": "한국 웹소설 스타일, 1인칭 남주 시점, e스포츠 현실 묘사, 경기 장면 박진감 넘치게, 성장과 감동",
            "provider": "gpt", "max_episodes": 30,
        },
        {
            "name": "야간 특수대의 비밀",
            "description": "표면상 경찰, 실제는 초자연 현상을 처리하는 비밀 부대. 신입 요원 박지호는 오늘도 유령, 괴물, 이해 못할 사건들과 씨름한다.",
            "genres": ["판타지", "액션", "코미디"], "tags": ["경찰", "초자연", "현대판타지", "팀물", "개그"],
            "writing_style": "한국 웹소설 스타일, 1인칭 남주 시점, 현대 배경 초자연 액션+코미디, 팀원들 간의 케미, 긴박한 사건과 유머 교차",
            "provider": "grok", "max_episodes": 35,
        },
        {
            "name": "조선 최초의 여형사",
            "description": "조선 시대, 신분을 숨기고 포졸로 잠입한 양반가 딸 윤서연. 한양을 뒤흔드는 연쇄 살인 사건을 추적하며 왕의 눈에 띄기 시작한다.",
            "genres": ["역사", "미스터리", "로맨스"], "tags": ["조선", "여주", "추리", "역사로맨스", "강한여주"],
            "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 역사 배경 추리+로맨스, 시대 고증 디테일, 지략 있는 여주와 냉철한 남주",
            "provider": "gemini", "max_episodes": 35,
        },
        {
            "name": "멸종 위기종 구조센터",
            "description": "도시 한복판에 생긴 기묘한 구조센터. 그런데 여기 드나드는 건 동물이 아니라 신화 속 멸종 위기 마법 생물들이다.",
            "genres": ["판타지", "코미디", "힐링"], "tags": ["마법", "동물", "힐링", "도시판타지", "개그"],
            "writing_style": "한국 웹소설 스타일, 1인칭 여주 시점, 도시 배경 판타지 코미디, 귀여운 마법 생물들과의 좌충우돌, 따뜻한 힐링",
            "provider": "gpt", "max_episodes": 25, "adult": False,
        },
    ]
    # 19금 기본 풀 (항상 1개 랜덤 선택)
    adult_pool = [
        {
            "name": "금지된 계약",
            "description": "냉혹한 재벌 회장과 신입 비서의 계약 관계. 선을 넘지 않겠다던 약속은 첫날 밤부터 흔들리기 시작했다.",
            "genres": ["로맨스", "성인"], "tags": ["재벌", "계약", "금지된사랑", "비서", "성인로맨스"],
            "writing_style": "한국 성인 웹소설 스타일, 1인칭 여주 시점, 재벌×비서 금지된 로맨스, 관능적 긴장감과 선정적 분위기 포함, 냉혹한 남주가 서서히 무너지는 감정선, 밀당과 설레임",
            "provider": "grok", "max_episodes": 30, "adult": True,
        },
        {
            "name": "밤의 주치의",
            "description": "낮에는 차가운 외과 의사, 밤에는 나만을 바라보는 남자. 병원 안에서 시작된 위험한 감정은 수술실 밖으로 번져나간다.",
            "genres": ["로맨스", "성인"], "tags": ["의사", "병원로맨스", "금지된사랑", "성인로맨스", "연상"],
            "writing_style": "한국 성인 웹소설 스타일, 1인칭 여주 시점, 의사×환자 금지된 로맨스, 관능적 긴장감과 선정적 분위기 포함, 감정선 섬세하게, 다음 화가 궁금한 결말",
            "provider": "grok", "max_episodes": 25, "adult": True,
        },
        {
            "name": "복수의 신부",
            "description": "나를 배신한 남자의 동생과 위장 결혼을 선택했다. 복수를 위한 결혼이었는데, 왜 그의 품이 이렇게 따뜻한 걸까.",
            "genres": ["로맨스", "성인"], "tags": ["복수", "위장결혼", "금지된사랑", "성인로맨스", "반전"],
            "writing_style": "한국 성인 웹소설 스타일, 1인칭 여주 시점, 복수×위장결혼 로맨스, 관능적 긴장감과 선정적 분위기 포함, 냉혹한 계획과 흔들리는 감정의 충돌, 긴장감 넘치는 전개",
            "provider": "grok", "max_episodes": 30, "adult": True,
        },
    ]
    random.shuffle(pool)
    random.shuffle(adult_pool)
    # 일반 4개 + 성인 1개
    return pool[:WEEKLY_CREATION_COUNT - 1] + adult_pool[:1]


def create_book_via_api(concept):
    """API로 책 생성 후 UUID 반환"""
    r = requests.post(
        f"{BASE_URL}/create-book/",
        headers=HEADERS,
        json={
            "title": concept["name"],          # API는 "title" 키 사용
            "description": concept["description"],
            "book_type": "webnovel",
            "genres": concept.get("genres", []),   # 이름 문자열 배열
            "tags": concept.get("tags", []),        # 이름 문자열 배열
        },
        timeout=30,
    )
    if r.status_code in (200, 201):
        data = r.json()
        if data.get("success"):
            return data.get("data", {}).get("book_uuid") or data.get("book_uuid")
    _log(f"  ❌ 책 생성 실패: {r.status_code} {r.text[:100]}")
    return None


def weekly_create_books():
    """주간 신규 책 5권 자동 생성"""
    state = load_weekly_state()
    last = state.get("last_creation")

    if last:
        last_dt = datetime.fromisoformat(last)
        days_since = (datetime.now() - last_dt).days
        if days_since < WEEKLY_CREATION_DAYS:
            remaining = WEEKLY_CREATION_DAYS - days_since
            _log(f"📅 주간 생성 스킵 — 다음 생성까지 {remaining}일 남음")
            return

    _log(f"📚 주간 신규 웹소설 {WEEKLY_CREATION_COUNT}권 생성 시작!")
    concepts = generate_book_concepts()
    auto_books = load_auto_books()
    created = 0

    for concept in concepts:
        _log(f"  📖 『{concept['name']}』 생성 중...")
        uuid = create_book_via_api(concept)
        if not uuid:
            continue

        # 1화 생성
        generate_episode(
            uuid, concept["writing_style"],
            concept.get("provider", "gpt"),
            concept.get("max_episodes", 30), 0
        )

        # 신규 책 캐릭터/플롯 미리 생성 (캐시)
        generate_book_context(
            uuid, concept["name"],
            concept.get("description", ""),
            concept["writing_style"],
        )

        # DALL-E 3 HD 표지 자동 생성
        generate_cover_dalle3(
            uuid, concept["name"],
            concept.get("description", ""),
            concept["writing_style"],
        )

        # auto_books 리스트에 추가 (스케줄러가 다음 사이클부터 자동 연재)
        auto_books.append({
            "book_uuid": uuid,
            "name": concept["name"],
            "writing_style": concept["writing_style"],
            "provider": concept.get("provider", "gpt"),
            "max_episodes": concept.get("max_episodes", 30),
            "adult": concept.get("adult", False),
            "completed": False,
            "created_at": datetime.now().isoformat(),
        })
        _log(f"  ✅ 『{concept['name']}』 생성 완료: {uuid}")
        created += 1

    save_auto_books(auto_books)
    save_weekly_state({"last_creation": datetime.now().isoformat()})
    _log(f"📚 주간 생성 완료 — {created}권 추가됨. 다음 생성: {WEEKLY_CREATION_DAYS}일 후")


def run_loop():
    _log(f"스케줄러 시작 — 에피소드: {INTERVAL_HOURS}시간 간격 / 신규 책: {WEEKLY_CREATION_DAYS}일 간격")
    while True:
        if is_paused():
            _log("⏸  일시정지 상태 — 1시간 후 재확인")
            time.sleep(3600)
            continue

        # 주간 신규 책 생성 확인
        weekly_create_books()

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
