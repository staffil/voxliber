"""
VOXLIBER 자동 오디오북 생성 API
- Claude(AI)가 소설을 쓰고, API로 책 생성 + 에피소드 TTS 변환까지 자동 처리
- 에피소드 = 여러 페이지(대사/나레이션), 각 페이지별 개별 TTS → 병합
- 사운드 이펙트/배경음 생성 + 음성 효과 프리셋 지원
"""
import json
import os
import tempfile
import traceback

from django.views.decorators.http import require_http_methods
from django.core.files import File
from django.core.files.base import ContentFile

from book.models import (
    Books, Content, Genres, Tags, VoiceList, VoiceType,
    SoundEffectLibrary, BackgroundMusicLibrary,
)
from book.api_utils import require_api_key_secure, api_response
from book.utils import generate_tts, merge_audio_files, sound_effect, background_music, mix_audio_with_background


# ==================== 1. 책 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_book(request):
    """
    책(오디오북) 프로필 생성 API

    POST /api/v1/create-book/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "title": "달빛 아래의 검사",
        "description": "어둠 속에서 빛을 찾는 검사의 이야기...",
        "genre_ids": [1, 3],
        "tag_ids": [5, 12],
        "status": "ongoing",
        "adult_choice": false
    }

    Returns:
    {
        "success": true,
        "data": {
            "book_uuid": "xxxx-xxxx-xxxx",
            "title": "달빛 아래의 검사",
            "message": "책이 성공적으로 생성되었습니다."
        }
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    genre_ids = data.get("genre_ids", [])
    tag_ids = data.get("tag_ids", [])
    status = data.get("status", "ongoing")
    adult_choice = data.get("adult_choice", False)

    if not title:
        return api_response(error="제목(title)은 필수입니다.", status=400)

    # 중복 제목 체크
    existing = Books.objects.filter(name=title, user=request.api_user).first()
    if existing:
        return api_response(error=f"이미 같은 제목의 책이 있습니다. (UUID: {existing.public_uuid})", status=409)

    # 책 생성
    book = Books.objects.create(
        user=request.api_user,
        name=title,
        description=description,
        status=status,
        adult_choice=adult_choice,
    )

    # 장르 연결
    if genre_ids:
        genres = Genres.objects.filter(id__in=genre_ids)
        book.genres.set(genres)

    # 태그 연결
    if tag_ids:
        tags = Tags.objects.filter(id__in=tag_ids)
        book.tags.set(tags)

    print(f"✅ [API] 책 생성 완료: {book.name} (UUID: {book.public_uuid})")

    return api_response(data={
        "book_uuid": str(book.public_uuid),
        "title": book.name,
        "description": book.description,
        "message": "책이 성공적으로 생성되었습니다."
    })


# ==================== 2. 에피소드 + TTS 생성 API (멀티 페이지) ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_episode(request):
    """
    에피소드 생성 + 멀티 페이지 TTS 자동 변환 API
    - 각 페이지(대사/나레이션)별로 개별 TTS 생성 후 병합
    - 나레이션은 DB에서 '나레이션' 타입 음성 자동 사용 가능

    POST /api/v1/create-episode/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx-xxxx-xxxx",
        "episode_number": 1,
        "episode_title": "제1화: 시작",
        "pages": [
            {
                "text": "[calm] 어둠이 내려앉은 숲속이었다.",
                "voice_id": "narrator_voice_id",
                "language_code": "ko",
                "speed_value": 0.95,
                "style_value": 0.85,
                "similarity_value": 0.75
            },
            {
                "text": "[scared] 누... 누구세요?",
                "voice_id": "character_voice_id",
                "language_code": "ko",
                "speed_value": 0.9,
                "style_value": 0.95,
                "similarity_value": 0.75
            }
        ]
    }

    Returns:
    {
        "success": true,
        "data": {
            "content_uuid": "xxxx-xxxx-xxxx",
            "episode_number": 1,
            "episode_title": "제1화: 시작",
            "audio_url": "/media/audio/merged_xxx.mp3",
            "duration_seconds": 180,
            "pages_count": 2,
            "timestamps": [...],
            "message": "에피소드가 생성되고 TTS 변환이 완료되었습니다."
        }
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    book_uuid = data.get("book_uuid", "").strip()
    episode_number = data.get("episode_number")
    episode_title = data.get("episode_title", "").strip()
    pages = data.get("pages", [])

    # 필수값 검증
    if not all([book_uuid, episode_number, episode_title]):
        return api_response(
            error="필수 필드: book_uuid, episode_number, episode_title",
            status=400
        )

    if not pages or not isinstance(pages, list):
        return api_response(
            error="pages 배열이 필요합니다. 각 페이지에 text와 voice_id를 포함하세요.",
            status=400
        )

    if len(pages) > 200:
        return api_response(error="페이지는 최대 200개까지 가능합니다.", status=400)

    # 각 페이지 검증
    for i, page in enumerate(pages):
        if not page.get("text", "").strip():
            return api_response(error=f"페이지 {i+1}의 text가 비어있습니다.", status=400)
        if not page.get("voice_id", "").strip():
            return api_response(error=f"페이지 {i+1}의 voice_id가 필요합니다.", status=400)

    # 책 조회 (본인 소유 확인)
    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    # 에피소드 번호 중복 체크
    if Content.objects.filter(book=book, number=int(episode_number), is_deleted=False).exists():
        return api_response(
            error=f"이미 {episode_number}화가 존재합니다.",
            status=409
        )

    try:
        # 전체 텍스트 합치기 (페이지 구분)
        full_text = "\n\n---\n\n".join([p.get("text", "").strip() for p in pages])

        # 1. 에피소드 생성
        content = Content.objects.create(
            book=book,
            title=episode_title,
            number=int(episode_number),
            text=full_text,
        )
        print(f"📝 [API] 에피소드 생성: {book.name} - {episode_title} ({len(pages)}페이지)")

        # 2. 각 페이지별 TTS 생성
        audio_paths = []
        pages_text = []
        temp_files = []

        for i, page in enumerate(pages):
            page_text = page["text"].strip()
            page_voice = page["voice_id"].strip()
            page_lang = page.get("language_code", "ko").strip()
            page_speed = page.get("speed_value", 1.0)
            page_style = page.get("style_value", 0.5)
            page_similarity = page.get("similarity_value", 0.75)

            print(f"🔊 [API] 페이지 {i+1}/{len(pages)} TTS 생성... (voice: {page_voice})")

            audio_path = generate_tts(
                page_text,
                page_voice,
                page_lang,
                page_speed,
                page_style,
                page_similarity,
            )

            if audio_path and os.path.exists(audio_path):
                audio_paths.append(audio_path)
                pages_text.append(page_text)
                temp_files.append(audio_path)
                print(f"  ✅ 페이지 {i+1} TTS 완료")
            else:
                print(f"  ⚠️ 페이지 {i+1} TTS 실패 - 건너뜀")

        audio_url = None
        duration_seconds = 0
        timestamps = None

        if audio_paths:
            # 3. 오디오 병합 (merge_audio_files)
            print(f"🔀 [API] {len(audio_paths)}개 오디오 병합 중...")
            merged_path, timestamps_info = merge_audio_files(audio_paths, pages_text)

            if merged_path and os.path.exists(merged_path):
                # 4. 병합된 오디오 저장
                with open(merged_path, 'rb') as audio_file:
                    content.audio_file.save(
                        os.path.basename(merged_path),
                        File(audio_file),
                        save=True
                    )

                # 5. 타임스탬프 저장
                if timestamps_info:
                    content.audio_timestamps = json.dumps(timestamps_info)
                    timestamps = timestamps_info

                # 6. 오디오 길이 계산
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_file(merged_path)
                duration_seconds = int(len(audio_segment) / 1000)
                content.duration_seconds = duration_seconds
                content.save()

                audio_url = content.audio_file.url

                # 병합 파일 삭제
                os.remove(merged_path)
                print(f"💾 [API] 병합 오디오 저장 완료: {duration_seconds}초")

            # 7. 임시 개별 TTS 파일 삭제
            for temp_path in temp_files:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            print(f"✅ [API] 에피소드 완료: {len(audio_paths)}페이지, {duration_seconds}초")
        else:
            print("⚠️ [API] 모든 페이지 TTS 생성 실패 - 에피소드는 저장됨 (오디오 없음)")

        return api_response(data={
            "content_uuid": str(content.public_uuid),
            "episode_number": content.number,
            "episode_title": content.title,
            "audio_url": audio_url,
            "duration_seconds": duration_seconds,
            "pages_count": len(audio_paths),
            "total_pages": len(pages),
            "timestamps": timestamps,
            "message": "에피소드가 생성되고 TTS 변환이 완료되었습니다." if audio_url
                       else "에피소드는 저장되었지만 TTS 변환에 실패했습니다."
        })

    except Exception as e:
        print(f"❌ [API] 에피소드 생성 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"에피소드 생성 중 오류: {str(e)}", status=500)


# ==================== 3. 음성 목록 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_voice_list(request):
    """
    사용 가능한 음성 목록 조회
    - ?type=나레이션 으로 타입 필터링 가능

    GET /api/v1/voices/
    GET /api/v1/voices/?type=나레이션
    Headers: X-API-Key: <your_api_key>
    """
    voice_type_filter = request.GET.get("type", "").strip()

    voices = VoiceList.objects.all().order_by('voice_name')
    if voice_type_filter:
        voices = voices.filter(types__name__icontains=voice_type_filter)

    voice_data = []
    for v in voices:
        types = list(v.types.values_list('name', flat=True))
        voice_data.append({
            "voice_id": v.voice_id,
            "voice_name": v.voice_name,
            "language_code": v.language_code,
            "description": v.voice_description or "",
            "types": types,
            "sample_audio": v.sample_audio.url if v.sample_audio else None,
        })

    return api_response(data={
        "voices": voice_data,
        "total": len(voice_data),
    })


# ==================== 4. 장르 목록 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_genre_list(request):
    """
    장르 목록 조회

    GET /api/v1/genres/
    Headers: X-API-Key: <your_api_key>
    """
    genres = Genres.objects.all().order_by('name')
    genre_data = [{"id": g.id, "name": g.name} for g in genres]

    return api_response(data={
        "genres": genre_data,
        "total": len(genre_data),
    })


# ==================== 5. 내 책 목록 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_my_books(request):
    """
    내가 만든 책 목록 조회

    GET /api/v1/my-books/
    Headers: X-API-Key: <your_api_key>
    """
    books = Books.objects.filter(user=request.api_user).order_by('-created_at')
    book_data = []
    for b in books:
        episodes = Content.objects.filter(book=b, is_deleted=False).count()
        book_data.append({
            "book_uuid": str(b.public_uuid),
            "title": b.name,
            "description": b.description or "",
            "status": b.status,
            "episodes_count": episodes,
            "cover_img": b.cover_img.url if b.cover_img else None,
            "created_at": b.created_at.isoformat(),
        })

    return api_response(data={
        "books": book_data,
        "total": len(book_data),
    })


# ==================== 6. 사운드 이펙트 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_sound_effect(request):
    """
    AI 사운드 이펙트 생성 API (ElevenLabs Sound Effects)
    - 설명을 기반으로 AI가 사운드 이펙트 오디오를 생성
    - 생성된 이펙트는 라이브러리에 저장됨

    POST /api/v1/sound-effect/create/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "effect_name": "빗소리",
        "effect_description": "창문에 부딪히는 빗소리, 천둥이 멀리서 울리는 소리",
        "duration_seconds": 5
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    effect_name = data.get("effect_name", "").strip()
    effect_description = data.get("effect_description", "").strip()
    duration_seconds = data.get("duration_seconds", 5)

    if not effect_name or not effect_description:
        return api_response(error="effect_name과 effect_description은 필수입니다.", status=400)

    if duration_seconds < 1 or duration_seconds > 22:
        return api_response(error="duration_seconds는 1~22초 사이여야 합니다.", status=400)

    try:
        print(f"🎵 [API] 사운드 이펙트 생성: {effect_name} - {effect_description}")
        audio_stream = sound_effect(effect_name, effect_description, duration_seconds)

        if not audio_stream:
            return api_response(error="사운드 이펙트 생성에 실패했습니다.", status=500)

        # 스트림을 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
            for chunk in audio_stream:
                temp_file.write(chunk)

        # DB에 저장
        effect_obj = SoundEffectLibrary.objects.create(
            effect_name=effect_name,
            effect_description=effect_description,
            user=request.api_user,
        )

        with open(temp_path, 'rb') as f:
            effect_obj.audio_file.save(f"effect_{effect_obj.id}.mp3", File(f), save=True)

        os.remove(temp_path)

        print(f"✅ [API] 사운드 이펙트 생성 완료: {effect_name}")

        return api_response(data={
            "effect_id": effect_obj.id,
            "effect_name": effect_obj.effect_name,
            "audio_url": effect_obj.audio_file.url,
            "message": "사운드 이펙트가 생성되었습니다."
        })

    except Exception as e:
        print(f"❌ [API] 사운드 이펙트 생성 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"사운드 이펙트 생성 중 오류: {str(e)}", status=500)


# ==================== 7. 배경음 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_background_music(request):
    """
    AI 배경음악 생성 API (ElevenLabs Music Generation)
    - 설명을 기반으로 AI가 배경음악을 생성
    - 생성된 배경음은 라이브러리에 저장됨

    POST /api/v1/background-music/create/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "music_name": "슬픈 피아노",
        "music_description": "비 오는 날 창가에서 듣는 잔잔한 피아노 선율",
        "duration_seconds": 30
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    music_name = data.get("music_name", "").strip()
    music_description = data.get("music_description", "").strip()
    duration_seconds = data.get("duration_seconds", 30)

    if not music_name or not music_description:
        return api_response(error="music_name과 music_description은 필수입니다.", status=400)

    if duration_seconds < 5 or duration_seconds > 300:
        return api_response(error="duration_seconds는 5~300초 사이여야 합니다.", status=400)

    try:
        print(f"🎼 [API] 배경음 생성: {music_name} - {music_description} ({duration_seconds}초)")
        audio_stream = background_music(music_name, music_description, duration_seconds)

        if not audio_stream:
            return api_response(error="배경음 생성에 실패했습니다.", status=500)

        # 스트림을 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
            for chunk in audio_stream:
                temp_file.write(chunk)

        # DB에 저장
        music_obj = BackgroundMusicLibrary.objects.create(
            music_name=music_name,
            music_description=music_description,
            duration_seconds=duration_seconds,
            user=request.api_user,
        )

        with open(temp_path, 'rb') as f:
            music_obj.audio_file.save(f"bgm_{music_obj.id}.mp3", File(f), save=True)

        os.remove(temp_path)

        print(f"✅ [API] 배경음 생성 완료: {music_name}")

        return api_response(data={
            "music_id": music_obj.id,
            "music_name": music_obj.music_name,
            "audio_url": music_obj.audio_file.url,
            "duration_seconds": duration_seconds,
            "message": "배경음이 생성되었습니다."
        })

    except Exception as e:
        print(f"❌ [API] 배경음 생성 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"배경음 생성 중 오류: {str(e)}", status=500)


# ==================== 8. 사운드 이펙트 라이브러리 조회 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_sound_effect_library(request):
    """
    내 사운드 이펙트 라이브러리 조회

    GET /api/v1/sound-effects/
    Headers: X-API-Key: <your_api_key>
    """
    effects = SoundEffectLibrary.objects.filter(user=request.api_user).order_by('-created_at')
    effect_data = []
    for e in effects:
        effect_data.append({
            "effect_id": e.id,
            "effect_name": e.effect_name,
            "effect_description": e.effect_description,
            "audio_url": e.audio_file.url if e.audio_file else None,
            "created_at": e.created_at.isoformat(),
        })

    return api_response(data={
        "sound_effects": effect_data,
        "total": len(effect_data),
    })


# ==================== 9. 배경음 라이브러리 조회 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_background_music_library(request):
    """
    내 배경음 라이브러리 조회

    GET /api/v1/background-music/
    Headers: X-API-Key: <your_api_key>
    """
    musics = BackgroundMusicLibrary.objects.filter(user=request.api_user).order_by('-created_at')
    music_data = []
    for m in musics:
        music_data.append({
            "music_id": m.id,
            "music_name": m.music_name,
            "music_description": m.music_description,
            "audio_url": m.audio_file.url if m.audio_file else None,
            "duration_seconds": m.duration_seconds,
            "created_at": m.created_at.isoformat(),
        })

    return api_response(data={
        "background_music": music_data,
        "total": len(music_data),
    })


# ==================== 10. 음성 효과 프리셋 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_voice_effect_presets(request):
    """
    사용 가능한 음성 효과(오디오 필터) 프리셋 목록
    - editor-core.js의 Web Audio API 효과들을 API로 제공
    - 에피소드 생성 시 각 페이지에 voice_effect 필드로 적용 가능

    GET /api/v1/voice-effects/
    Headers: X-API-Key: <your_api_key>
    """
    presets = {
        "normal": {"name": "기본", "description": "효과 없음", "filter_type": "allpass", "frequency": 1000, "q": 1, "delay": 0, "feedback": 0, "tremolo": 0, "tremolo_freq": 0},
        "phone": {"name": "전화", "description": "전화 통화 느낌", "filter_type": "highpass", "frequency": 2000, "q": 8, "delay": 0, "feedback": 0, "tremolo": 0, "tremolo_freq": 0},
        "cave": {"name": "동굴", "description": "동굴 속 울림", "filter_type": "lowpass", "frequency": 600, "q": 6, "delay": 0.45, "feedback": 0.7, "tremolo": 0, "tremolo_freq": 0},
        "underwater": {"name": "물속", "description": "물속에서 말하는 느낌", "filter_type": "lowpass", "frequency": 400, "q": 2, "delay": 0.15, "feedback": 0.3, "tremolo": 0.2, "tremolo_freq": 5},
        "robot": {"name": "로봇", "description": "로봇 음성", "filter_type": "highpass", "frequency": 1200, "q": 1, "delay": 0, "feedback": 0, "tremolo": 1, "tremolo_freq": 30},
        "ghost": {"name": "유령", "description": "공포/유령 느낌", "filter_type": "bandpass", "frequency": 500, "q": 9, "delay": 0.5, "feedback": 0.8, "tremolo": 0.4, "tremolo_freq": 3},
        "old": {"name": "노인", "description": "나이든 목소리", "filter_type": "lowpass", "frequency": 700, "q": 3, "delay": 0.2, "feedback": 0.5, "tremolo": 0.2, "tremolo_freq": 2},
        "echo": {"name": "메아리", "description": "메아리 효과", "filter_type": "allpass", "frequency": 1000, "q": 1, "delay": 0.6, "feedback": 0.7, "tremolo": 0, "tremolo_freq": 0},
        "whisper": {"name": "속삭임", "description": "속삭이는 느낌", "filter_type": "bandpass", "frequency": 1800, "q": 4, "delay": 0.03, "feedback": 0.2, "tremolo": 0.15, "tremolo_freq": 4},
        "radio": {"name": "라디오", "description": "라디오 방송 느낌", "filter_type": "bandpass", "frequency": 1800, "q": 2, "delay": 0, "feedback": 0, "tremolo": 0.4, "tremolo_freq": 6.5},
        "megaphone": {"name": "확성기", "description": "확성기/스피커 느낌", "filter_type": "highpass", "frequency": 900, "q": 5, "delay": 0.05, "feedback": 0.35, "tremolo": 0, "tremolo_freq": 0},
        "protoss": {"name": "신성한 목소리", "description": "프로토스/신성한 느낌", "filter_type": "allpass", "frequency": 1100, "q": 6, "delay": 0.09, "feedback": 0.42, "tremolo": 0, "tremolo_freq": 0},
        "demon": {"name": "악마", "description": "악마의 목소리", "filter_type": "lowpass", "frequency": 800, "q": 3, "delay": 0.07, "feedback": 0.6, "tremolo": 0.5, "tremolo_freq": 120},
        "angel": {"name": "천사", "description": "천상의 목소리", "filter_type": "highpass", "frequency": 800, "q": 5, "delay": 0.35, "feedback": 0.65, "tremolo": 0.2, "tremolo_freq": 1.5},
        "vader": {"name": "다스베이더", "description": "다스베이더 목소리", "filter_type": "bandpass", "frequency": 400, "q": 8, "delay": 0.04, "feedback": 0.4, "tremolo": 0.3, "tremolo_freq": 80},
        "giant": {"name": "거인", "description": "거인의 울림", "filter_type": "lowpass", "frequency": 300, "q": 4, "delay": 0.6, "feedback": 0.7, "tremolo": 0, "tremolo_freq": 0},
        "tiny": {"name": "꼬마요정", "description": "작고 높은 목소리", "filter_type": "highpass", "frequency": 2200, "q": 6, "delay": 0.02, "feedback": 0.3, "tremolo": 0.4, "tremolo_freq": 8},
        "possessed": {"name": "빙의", "description": "빙의된 목소리", "filter_type": "bandpass", "frequency": 600, "q": 5, "delay": 0.07, "feedback": 0.7, "tremolo": 0.6, "tremolo_freq": 100},
        "horror": {"name": "호러", "description": "소름 끼치는 공포", "filter_type": "bandpass", "frequency": 620, "q": 14, "delay": 0.38, "feedback": 0.78, "tremolo": 0.6, "tremolo_freq": 2.8},
        "helium": {"name": "헬륨", "description": "헬륨 가스 목소리", "filter_type": "highpass", "frequency": 2900, "q": 7, "delay": 0.015, "feedback": 0.18, "tremolo": 0.2, "tremolo_freq": 12},
        "timewarp": {"name": "시간왜곡", "description": "시간이 느려지는 효과", "filter_type": "lowpass", "frequency": 580, "q": 9, "delay": 0.42, "feedback": 0.89, "tremolo": 0.5, "tremolo_freq": 0.25},
        "glitch": {"name": "글리치 AI", "description": "디지털 깨진 AI 목소리", "filter_type": "bandpass", "frequency": 1300, "q": 22, "delay": 0.008, "feedback": 0.35, "tremolo": 0.92, "tremolo_freq": 280},
        "choir": {"name": "성가대", "description": "성가대 합창 효과", "filter_type": "allpass", "frequency": 1600, "q": 5, "delay": 0.28, "feedback": 0.72, "tremolo": 0.28, "tremolo_freq": 1.1},
        "hyperpop": {"name": "Hyperpop", "description": "TikTok/Hyperpop 보컬", "filter_type": "highpass", "frequency": 3200, "q": 14, "delay": 0.018, "feedback": 0.42, "tremolo": 0.7, "tremolo_freq": 220},
        "vaporwave": {"name": "Vaporwave", "description": "80년대 몽환 리버브", "filter_type": "lowpass", "frequency": 3400, "q": 2, "delay": 0.38, "feedback": 0.78, "tremolo": 0.65, "tremolo_freq": 0.35},
        "darksynth": {"name": "Dark Synth", "description": "사이버펑크 DJ", "filter_type": "bandpass", "frequency": 950, "q": 11, "delay": 0.24, "feedback": 0.70, "tremolo": 0.55, "tremolo_freq": 130},
        "lofi-girl": {"name": "Lo-Fi Girl", "description": "Lo-Fi 라디오 ASMR", "filter_type": "lowpass", "frequency": 4200, "q": 1.8, "delay": 0.45, "feedback": 0.62, "tremolo": 0.35, "tremolo_freq": 0.12},
        "bitcrush-voice": {"name": "Bitcrush", "description": "8bit 게임 목소리", "filter_type": "bandpass", "frequency": 2200, "q": 28, "delay": 0.004, "feedback": 0.25, "tremolo": 0.96, "tremolo_freq": 420},
        "portal": {"name": "Portal", "description": "차원문 공간 왜곡", "filter_type": "allpass", "frequency": 750, "q": 18, "delay": 0.65, "feedback": 0.94, "tremolo": 0.8, "tremolo_freq": 0.7},
        "neoncity": {"name": "Neon City", "description": "네온 도시 아나운서", "filter_type": "bandpass", "frequency": 1150, "q": 9, "delay": 0.52, "feedback": 0.80, "tremolo": 0.45, "tremolo_freq": 2.8},
        "ghost-in-machine": {"name": "Ghost AI", "description": "AI 귀신 호러", "filter_type": "bandpass", "frequency": 780, "q": 20, "delay": 0.09, "feedback": 0.58, "tremolo": 0.88, "tremolo_freq": 190},
    }

    return api_response(data={
        "voice_effects": presets,
        "total": len(presets),
        "usage": "에피소드 생성 시 각 page에 'voice_effect': 'ghost' 형태로 지정하면 해당 효과가 적용됩니다."
    })


# ==================== 11. 감정 태그 목록 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_emotion_tags(request):
    """
    TTS에 사용 가능한 감정 태그 목록
    - 텍스트 앞에 [태그] 형태로 넣으면 TTS 음성에 감정이 반영됨
    - 예: "[happy] 오늘 정말 좋은 날이야!"

    GET /api/v1/emotion-tags/
    Headers: X-API-Key: <your_api_key>
    """
    emotion_tags = {
        "joy_laugh": {
            "category": "기쁨/웃음",
            "tags": ["happy", "very_happy", "excited", "laughing", "giggling", "bursting_laughter", "bright_smile", "chuckling", "loving_it", "cheering"]
        },
        "sadness_cry": {
            "category": "슬픔/울음",
            "tags": ["sad", "heartbroken", "teary", "sobbing", "sniffling", "crying", "sorrowful", "whimpering", "anguished", "choked_voice"]
        },
        "anger": {
            "category": "분노",
            "tags": ["angry", "shouting", "yelling", "snapping", "irate", "growling", "furious", "gritting_teeth", "angered", "frustrated"]
        },
        "shout": {
            "category": "외침",
            "tags": ["shout", "yell", "exclaim", "scream", "loud_voice", "moan"]
        },
        "fear": {
            "category": "공포/두려움",
            "tags": ["scared", "trembling", "whisper_fear", "shaking", "panicked", "terrified", "nervous_voice", "cold_sweat", "fearful"]
        },
        "calm": {
            "category": "차분/진지",
            "tags": ["calm", "serious", "quiet", "steady", "composed", "firm", "cold", "expressionless"]
        },
        "whisper": {
            "category": "속삭임",
            "tags": ["whispering", "chuckles", "soft_whisper", "exhales sharply", "short pause", "murmur", "hushed", "secretive", "quietly", "under_breath", "sneaky_voice"]
        },
        "drunk": {
            "category": "취함/졸림",
            "tags": ["drunk", "slurred", "staggering", "sleepy", "yawning", "drowsy", "tipsy", "wine_breath"]
        },
        "etc": {
            "category": "기타 감정",
            "tags": ["warried", "clears throat", "embarrassed", "confused", "awkward", "ashamed", "discouraged", "puzzled", "shocked", "startled", "uneasy", "bothered"]
        },
        "speech_style": {
            "category": "말투/스타일",
            "tags": ["slow", "fast", "sarcastic", "sly", "cute", "cool", "arrogant", "charming", "formal", "gentle", "warm"]
        },
        "intensity": {
            "category": "강도/볼륨",
            "tags": ["soft", "slightly", "normal", "loud", "very_loud", "maximum", "quiet", "very_soft", "very_slow"]
        }
    }

    return api_response(data={
        "emotion_tags": emotion_tags,
        "usage": "텍스트 앞에 [태그] 형태로 넣어주세요. 예: '[happy] 안녕하세요!', '[sad][whispering] 잘가...'",
        "example": "[excited] 드디어 해냈어! [crying] 너무 감동이야..."
    })


# ==================== 12. 에피소드 삭제 (재생성용) API ====================

@require_api_key_secure
@require_http_methods(["DELETE"])
def api_delete_episode(request):
    """
    에피소드 삭제 API (재생성을 위해)
    - 오디오가 이상하면 삭제 후 다시 create-episode 호출

    DELETE /api/v1/delete-episode/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx-xxxx-xxxx",
        "episode_number": 1
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    book_uuid = data.get("book_uuid", "").strip()
    episode_number = data.get("episode_number")

    if not book_uuid or not episode_number:
        return api_response(error="book_uuid와 episode_number는 필수입니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    content = Content.objects.filter(
        book=book, number=int(episode_number), is_deleted=False
    ).first()

    if not content:
        return api_response(error=f"{episode_number}화를 찾을 수 없습니다.", status=404)

    # soft delete
    content.is_deleted = True
    content.save()
    print(f"🗑️ [API] 에피소드 삭제: {book.name} - {content.title} ({episode_number}화)")

    return api_response(data={
        "book_uuid": book_uuid,
        "episode_number": episode_number,
        "message": f"{episode_number}화가 삭제되었습니다. 같은 번호로 다시 생성할 수 있습니다."
    })


# ==================== 13. 에피소드 재생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_regenerate_episode(request):
    """
    에피소드 재생성 API (기존 에피소드 삭제 + 새로 생성)
    - 오디오가 이상할 때 삭제 없이 바로 재생성

    POST /api/v1/regenerate-episode/
    Headers: X-API-Key: <your_api_key>
    Body: api_create_episode와 동일 (book_uuid, episode_number, episode_title, pages)
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    book_uuid = data.get("book_uuid", "").strip()
    episode_number = data.get("episode_number")

    if not book_uuid or not episode_number:
        return api_response(error="book_uuid와 episode_number는 필수입니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    # 기존 에피소드 soft delete
    existing = Content.objects.filter(
        book=book, number=int(episode_number), is_deleted=False
    ).first()

    if existing:
        existing.is_deleted = True
        existing.save()
        print(f"🔄 [API] 기존 {episode_number}화 삭제 후 재생성 시작...")

    # api_create_episode 로직 재사용
    return api_create_episode(request)


# ==================== 14. 에피소드 + 배경음 믹싱 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_mix_background_music(request):
    """
    기존 에피소드에 배경음을 믹싱하는 API
    - 이미 생성된 에피소드의 오디오에 배경음을 오버레이

    POST /api/v1/mix-background/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx-xxxx-xxxx",
        "episode_number": 1,
        "background_tracks": [
            {
                "music_id": 5,
                "start_page": 0,
                "end_page": 3,
                "volume": 0.3
            }
        ]
    }

    volume: 0.0~1.0 (0.3 = 30% 볼륨)
    start_page/end_page: 타임스탬프 기반으로 해당 페이지 구간에 배경음 삽입
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    book_uuid = data.get("book_uuid", "").strip()
    episode_number = data.get("episode_number")
    bg_tracks = data.get("background_tracks", [])

    if not book_uuid or not episode_number:
        return api_response(error="book_uuid와 episode_number는 필수입니다.", status=400)

    if not bg_tracks:
        return api_response(error="background_tracks 배열이 필요합니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    content = Content.objects.filter(
        book=book, number=int(episode_number), is_deleted=False
    ).first()

    if not content or not content.audio_file:
        return api_response(error="에피소드 또는 오디오 파일을 찾을 수 없습니다.", status=404)

    try:
        from pydub import AudioSegment

        # 현재 에피소드 오디오 경로
        current_audio_path = content.audio_file.path

        # 타임스탬프 파싱
        timestamps = []
        if content.audio_timestamps:
            timestamps = json.loads(content.audio_timestamps) if isinstance(content.audio_timestamps, str) else content.audio_timestamps

        # 배경음 트랙 정보 구성
        background_tracks_info = []
        temp_bg_files = []

        for track in bg_tracks:
            music_id = track.get("music_id")
            start_page = track.get("start_page", 0)
            end_page = track.get("end_page", len(timestamps) - 1 if timestamps else 0)
            volume = track.get("volume", 0.3)

            # 배경음 라이브러리에서 조회
            bg_music = BackgroundMusicLibrary.objects.filter(
                id=music_id, user=request.api_user
            ).first()

            if not bg_music or not bg_music.audio_file:
                continue

            # 시작/종료 시간 계산 (타임스탬프 기반)
            start_time = 0
            end_time = content.duration_seconds * 1000 if content.duration_seconds else 0

            if timestamps:
                if start_page > 0 and start_page - 1 < len(timestamps):
                    start_time = timestamps[start_page - 1].get("endTime", 0)
                if end_page < len(timestamps):
                    end_time = timestamps[end_page].get("endTime", end_time)

            # 볼륨을 dB로 변환 (0.3 → -10.5dB)
            import math
            volume_db = 20 * math.log10(max(volume, 0.01))

            # 임시 파일로 복사
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(bg_music.audio_file.read())
                temp_bg_path = tmp.name
                temp_bg_files.append(temp_bg_path)

            background_tracks_info.append({
                'audioPath': temp_bg_path,
                'startTime': start_time,
                'endTime': end_time,
                'volume': volume_db,
            })

        if not background_tracks_info:
            return api_response(error="유효한 배경음 트랙이 없습니다.", status=400)

        # 믹싱 실행
        print(f"🎼 [API] 배경음 믹싱: {len(background_tracks_info)}개 트랙")
        mixed_path = mix_audio_with_background(current_audio_path, background_tracks_info)

        # 임시 파일 정리
        for tmp_path in temp_bg_files:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        if mixed_path and mixed_path != current_audio_path:
            # 새 오디오로 교체
            with open(mixed_path, 'rb') as f:
                content.audio_file.save(
                    os.path.basename(mixed_path),
                    File(f),
                    save=True
                )

            # 길이 재계산
            audio_segment = AudioSegment.from_file(mixed_path)
            content.duration_seconds = int(len(audio_segment) / 1000)
            content.save()

            os.remove(mixed_path)
            print(f"✅ [API] 배경음 믹싱 완료: {content.duration_seconds}초")

            return api_response(data={
                "content_uuid": str(content.public_uuid),
                "episode_number": content.number,
                "audio_url": content.audio_file.url,
                "duration_seconds": content.duration_seconds,
                "message": "배경음이 에피소드에 믹싱되었습니다."
            })
        else:
            return api_response(error="배경음 믹싱에 실패했습니다.", status=500)

    except Exception as e:
        print(f"❌ [API] 배경음 믹싱 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"배경음 믹싱 중 오류: {str(e)}", status=500)


# ==================== 15. 책 커버 이미지 업로드 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_upload_book_cover(request):
    """
    책 커버 이미지 업로드 API
    - AI 이미지 생성 API로 만든 이미지를 업로드

    POST /api/v1/upload-book-cover/
    Headers: X-API-Key: <your_api_key>
    Content-Type: multipart/form-data
    Body:
        book_uuid: "xxxx-xxxx-xxxx"
        cover_image: (이미지 파일)
    """
    book_uuid = request.POST.get("book_uuid", "").strip()

    if not book_uuid:
        return api_response(error="book_uuid는 필수입니다.", status=400)

    if "cover_image" not in request.FILES:
        return api_response(error="cover_image 파일이 필요합니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    image_file = request.FILES["cover_image"]

    # 파일 크기 체크 (5MB)
    if image_file.size > 5 * 1024 * 1024:
        return api_response(error="이미지 파일은 5MB 이하여야 합니다.", status=400)

    book.cover_img.save(image_file.name, image_file, save=True)
    print(f"🖼️ [API] 책 커버 업로드: {book.name}")

    return api_response(data={
        "book_uuid": str(book.public_uuid),
        "cover_img": book.cover_img.url,
        "message": "책 커버 이미지가 업로드되었습니다."
    })


# ==================== 16. 에피소드 이미지 업로드 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_upload_episode_image(request):
    """
    에피소드 이미지 업로드 API
    - AI 이미지 생성 API로 만든 이미지를 에피소드에 업로드

    POST /api/v1/upload-episode-image/
    Headers: X-API-Key: <your_api_key>
    Content-Type: multipart/form-data
    Body:
        book_uuid: "xxxx-xxxx-xxxx"
        episode_number: 1
        episode_image: (이미지 파일)
    """
    book_uuid = request.POST.get("book_uuid", "").strip()
    episode_number = request.POST.get("episode_number")

    if not book_uuid or not episode_number:
        return api_response(error="book_uuid와 episode_number는 필수입니다.", status=400)

    if "episode_image" not in request.FILES:
        return api_response(error="episode_image 파일이 필요합니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    content = Content.objects.filter(
        book=book, number=int(episode_number), is_deleted=False
    ).first()

    if not content:
        return api_response(error=f"{episode_number}화를 찾을 수 없습니다.", status=404)

    image_file = request.FILES["episode_image"]

    if image_file.size > 5 * 1024 * 1024:
        return api_response(error="이미지 파일은 5MB 이하여야 합니다.", status=400)

    content.episode_image.save(image_file.name, image_file, save=True)
    print(f"🖼️ [API] 에피소드 이미지 업로드: {book.name} - {content.title}")

    return api_response(data={
        "content_uuid": str(content.public_uuid),
        "episode_number": content.number,
        "episode_image": content.episode_image.url,
        "message": "에피소드 이미지가 업로드되었습니다."
    })


# ==================== 17. URL로 이미지 업로드 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_upload_image_from_url(request):
    """
    URL에서 이미지를 다운로드하여 책 커버 또는 에피소드 이미지에 저장
    - AI 이미지 생성 API가 URL을 반환하는 경우 사용

    POST /api/v1/upload-image-url/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx-xxxx-xxxx",
        "image_url": "https://example.com/generated_image.png",
        "target": "book_cover"  // "book_cover" 또는 "episode_image"
        "episode_number": 1     // target이 "episode_image"인 경우 필수
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    book_uuid = data.get("book_uuid", "").strip()
    image_url = data.get("image_url", "").strip()
    target = data.get("target", "book_cover").strip()
    episode_number = data.get("episode_number")

    if not book_uuid or not image_url:
        return api_response(error="book_uuid와 image_url은 필수입니다.", status=400)

    if target not in ("book_cover", "episode_image"):
        return api_response(error="target은 'book_cover' 또는 'episode_image'여야 합니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    try:
        import requests as req
        response = req.get(image_url, timeout=30)
        if response.status_code != 200:
            return api_response(error="이미지를 다운로드할 수 없습니다.", status=400)

        # 파일 크기 체크 (5MB)
        if len(response.content) > 5 * 1024 * 1024:
            return api_response(error="이미지 파일은 5MB 이하여야 합니다.", status=400)

        # 확장자 추출
        from urllib.parse import urlparse
        parsed = urlparse(image_url)
        ext = os.path.splitext(parsed.path)[1] or '.png'
        filename = f"ai_generated_{book.public_uuid}{ext}"

        if target == "book_cover":
            book.cover_img.save(filename, ContentFile(response.content), save=True)
            print(f"🖼️ [API] URL→책 커버 업로드: {book.name}")
            return api_response(data={
                "book_uuid": str(book.public_uuid),
                "cover_img": book.cover_img.url,
                "message": "책 커버 이미지가 업로드되었습니다."
            })
        else:
            if not episode_number:
                return api_response(error="episode_image일 때 episode_number는 필수입니다.", status=400)

            content = Content.objects.filter(
                book=book, number=int(episode_number), is_deleted=False
            ).first()
            if not content:
                return api_response(error=f"{episode_number}화를 찾을 수 없습니다.", status=404)

            content.episode_image.save(filename, ContentFile(response.content), save=True)
            print(f"🖼️ [API] URL→에피소드 이미지 업로드: {book.name} - {content.title}")
            return api_response(data={
                "content_uuid": str(content.public_uuid),
                "episode_number": content.number,
                "episode_image": content.episode_image.url,
                "message": "에피소드 이미지가 업로드되었습니다."
            })

    except Exception as e:
        print(f"❌ [API] 이미지 URL 업로드 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"이미지 업로드 중 오류: {str(e)}", status=500)


# ==================== 18. 태그 목록 조회 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_tag_list(request):
    """
    태그 목록 조회

    GET /api/v1/tags/
    Headers: X-API-Key: <your_api_key>
    """
    tags = Tags.objects.all().order_by('name')
    tag_data = [{"id": t.id, "name": t.name, "slug": t.slug} for t in tags]

    return api_response(data={
        "tags": tag_data,
        "total": len(tag_data),
    })


# ==================== 19. 책 장르/태그 업데이트 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_update_book_metadata(request):
    """
    책의 장르/태그를 업데이트하는 API (여러 개 선택 가능)

    POST /api/v1/update-book-metadata/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx-xxxx-xxxx",
        "genre_ids": [1, 3, 5],
        "tag_ids": [2, 7, 12],
        "mode": "set"  // "set"(교체) 또는 "add"(추가). 기본값: "set"
    }

    Returns:
    {
        "success": true,
        "data": {
            "book_uuid": "xxxx",
            "genres": [{"id": 1, "name": "판타지"}, ...],
            "tags": [{"id": 2, "name": "이세계"}, ...],
            "message": "장르/태그가 업데이트되었습니다."
        }
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    book_uuid = data.get("book_uuid", "").strip()
    genre_ids = data.get("genre_ids")
    tag_ids = data.get("tag_ids")
    mode = data.get("mode", "set")

    if not book_uuid:
        return api_response(error="book_uuid는 필수입니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    # 장르 업데이트
    if genre_ids is not None:
        genres = Genres.objects.filter(id__in=genre_ids)
        if mode == "add":
            book.genres.add(*genres)
        else:
            book.genres.set(genres)

    # 태그 업데이트
    if tag_ids is not None:
        tags = Tags.objects.filter(id__in=tag_ids)
        if mode == "add":
            book.tags.add(*tags)
        else:
            book.tags.set(tags)

    # 현재 설정된 장르/태그 반환
    current_genres = [{"id": g.id, "name": g.name} for g in book.genres.all()]
    current_tags = [{"id": t.id, "name": t.name} for t in book.tags.all()]

    print(f"📝 [API] 책 메타데이터 업데이트: {book.name} - 장르 {len(current_genres)}개, 태그 {len(current_tags)}개")

    return api_response(data={
        "book_uuid": str(book.public_uuid),
        "title": book.name,
        "genres": current_genres,
        "tags": current_tags,
        "message": "장르/태그가 업데이트되었습니다."
    })
