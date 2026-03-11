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
import random

from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.core.files import File
from django.core.files.base import ContentFile

from book.models import (
    Books, Content, Genres, Tags, VoiceList, VoiceType,
    SoundEffectLibrary, BackgroundMusicLibrary, BookSnap,
)
from book.api_utils import require_api_key_secure, api_response
from book.utils import generate_tts, merge_audio_files, sound_effect, background_music, mix_audio_with_background
from advertisment.models import Advertisement, AdImpression, UserAdCounter


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
    genre_names = data.get("genres", [])   # 이름으로도 가능
    tag_names = data.get("tags", [])       # 이름으로도 가능
    status = data.get("status", "ongoing")
    adult_choice = data.get("adult_choice", False)
    author_name = data.get("author_name", "").strip() or "미상"
    book_type = data.get("book_type", "audiobook")  # "audiobook" or "webnovel"

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
        author_name=author_name,
        book_type=book_type,
    )

    # 장르 연결 (ID 또는 이름)
    if genre_ids:
        genres = Genres.objects.filter(id__in=genre_ids)
        book.genres.set(genres)
    elif genre_names:
        genre_objs = []
        for gname in genre_names:
            g, _ = Genres.objects.get_or_create(name=gname, defaults={"genres_color": "#6366f1"})
            genre_objs.append(g)
        book.genres.set(genre_objs)

    # 태그 연결 (ID 또는 이름)
    if tag_ids:
        tags = Tags.objects.filter(id__in=tag_ids)
        book.tags.set(tags)
    elif tag_names:
        from django.utils.text import slugify
        tag_objs = []
        for tname in tag_names:
            slug = slugify(tname, allow_unicode=True)
            t, _ = Tags.objects.get_or_create(name=tname, defaults={"slug": slug or tname})
            tag_objs.append(t)
        book.tags.set(tag_objs)

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

    # 각 페이지 검증 (silence_seconds / voices 페이지는 text/voice_id 불필요)
    for i, page in enumerate(pages):
        if page.get("silence_seconds") is not None or page.get("voices"):
            continue
        if not page.get("text", "").strip():
            return api_response(error=f"페이지 {i+1}의 text가 비어있습니다.", status=400)
        if not page.get("voice_id", "").strip():
            return api_response(error=f"페이지 {i+1}의 voice_id가 필요합니다.", status=400)

    # 책 조회 (본인 소유 확인)
    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    # 에피소드 번호 중복 체크
    if Content.objects.filter(book=book, number=int(episode_number), is_deleted=False).exists():
        return api_response(
            error=f"이미 {episode_number}화가 존재합니다.",
            status=409
        )

    try:
        # 전체 텍스트 합치기 (silence/voices 페이지는 빈 문자열)
        full_text = "\n\n---\n\n".join([p.get("text", "").strip() for p in pages if p.get("text")])

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
            # ── 무음 페이지 ──────────────────────────────
            silence_seconds = page.get("silence_seconds")
            if silence_seconds is not None and float(silence_seconds) > 0:
                try:
                    from book.utils import generate_silence
                    silence_path = generate_silence(float(silence_seconds))
                    if silence_path and os.path.exists(silence_path):
                        audio_paths.append(silence_path)
                        pages_text.append('')
                        temp_files.append(silence_path)
                        print(f"  🔇 페이지 {i+1} 무음 {silence_seconds}초")
                except Exception as e:
                    print(f"  ⚠️ 페이지 {i+1} 무음 생성 오류: {e}")
                continue

            # ── 동시 대화(voices) 페이지 ──────────────────
            voices = page.get("voices", [])
            if voices:
                duet_paths = []
                for ve in voices:
                    v_text = ve.get("text", "").strip()
                    v_voice_id = ve.get("voice_id", "").strip()
                    if not v_text or not v_voice_id:
                        continue
                    try:
                        v_tts = generate_tts(v_text, v_voice_id, "ko", 1.0, 0.0, 0.75)
                        if v_tts:
                            v_path = v_tts if isinstance(v_tts, str) else v_tts.path
                            duet_paths.append(v_path)
                            temp_files.append(v_path)
                    except Exception as e:
                        print(f"  ⚠️ 페이지 {i+1} 듀엣 TTS 오류: {e}")
                if duet_paths:
                    try:
                        from book.utils import merge_duet_audio
                        duet_mp3 = merge_duet_audio(duet_paths, mode=page.get("mode", "alternate"))
                        if duet_mp3:
                            audio_paths.append(duet_mp3)
                            temp_files.append(duet_mp3)
                            combined_text = '\n'.join(v.get("text", "") for v in voices if v.get("text"))
                            pages_text.append(combined_text)
                            print(f"  🎭 페이지 {i+1} 동시 대화 완료 ({page.get('mode','alternate')} 모드)")
                    except Exception as e:
                        print(f"  ⚠️ 페이지 {i+1} 듀엣 병합 오류: {e}")
                continue

            # ── 일반 TTS 페이지 ───────────────────────────
            page_text = page.get("text", "").strip()
            page_voice = page.get("voice_id", "").strip()
            if not page_text or not page_voice:
                print(f"  ⚠️ 페이지 {i+1} text/voice_id 없음 - 건너뜀")
                continue
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
            merged_path, timestamps_info, _ = merge_audio_files(audio_paths, pages_text)

            if merged_path and os.path.exists(merged_path):
                # 4. 병합된 오디오 저장
                with open(merged_path, 'rb') as audio_file:
                    content.audio_file.save(
                        os.path.basename(merged_path),
                        File(audio_file),
                        save=True
                    )

                # 5. 타임스탬프 저장 (JSONField에 Python 객체 직접 저장 - json.dumps 불필요)
                if timestamps_info:
                    content.audio_timestamps = timestamps_info
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
    books = Books.objects.filter(user=request.api_user, is_deleted=False).order_by('-created_at')
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
        # sound_effect() saves file internally, returns file path
        audio_path = sound_effect(effect_name, effect_description, duration_seconds)

        if not audio_path:
            return api_response(error="사운드 이펙트 생성에 실패했습니다.", status=500)

        # DB에 저장
        effect_obj = SoundEffectLibrary.objects.create(
            effect_name=effect_name,
            effect_description=effect_description,
            user=request.api_user,
        )

        with open(audio_path, 'rb') as f:
            effect_obj.audio_file.save(f"effect_{effect_obj.id}.mp3", File(f), save=True)

        os.remove(audio_path)

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
        audio_path = background_music(music_name, music_description, duration_seconds)

        if not audio_path:
            return api_response(error="배경음 생성에 실패했습니다.", status=500)

        # DB에 저장 (background_music()이 이미 파일 경로를 반환)
        music_obj = BackgroundMusicLibrary.objects.create(
            music_name=music_name,
            music_description=music_description,
            duration_seconds=duration_seconds,
            user=request.api_user,
        )

        with open(audio_path, 'rb') as f:
            music_obj.audio_file.save(f"bgm_{music_obj.id}.mp3", File(f), save=True)

        # background_music()이 media/audio/에 저장한 임시 파일 삭제
        try:
            os.remove(audio_path)
        except OSError:
            pass

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

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
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

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
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
            {"music_id": 5, "start_page": 0, "end_page": 3, "volume": 0.3}
        ],
        "sound_effects": [
            {"effect_id": 1, "page": 3, "volume": 0.7}
        ]
    }

    volume: 0.0~1.0 (0.3 = 30% 볼륨)
    start_page/end_page: 타임스탬프 기반으로 해당 페이지 구간에 배경음 삽입
    sound_effects: 특정 페이지 시작 지점에 사운드 이펙트 오버레이
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    book_uuid = data.get("book_uuid", "").strip()
    episode_number = data.get("episode_number")
    bg_tracks = data.get("background_tracks", [])
    sfx_tracks = data.get("sound_effects", [])

    if not book_uuid or not episode_number:
        return api_response(error="book_uuid와 episode_number는 필수입니다.", status=400)

    if not bg_tracks and not sfx_tracks:
        return api_response(error="background_tracks 또는 sound_effects 배열이 필요합니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
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

            bg_music = BackgroundMusicLibrary.objects.filter(
                id=music_id, user=request.api_user
            ).first()

            if not bg_music or not bg_music.audio_file:
                continue

            audio_file = bg_music.audio_file

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
                tmp.write(audio_file.read())
                temp_bg_path = tmp.name
                temp_bg_files.append(temp_bg_path)

            background_tracks_info.append({
                'audioPath': temp_bg_path,
                'startTime': start_time,
                'endTime': end_time,
                'volume': volume_db,
            })

        # 사운드 이펙트 트랙 처리
        sfx_timestamp_entries = []
        for sfx in sfx_tracks:
            effect_id = sfx.get("effect_id")
            page = sfx.get("page_number") or sfx.get("page") or 1
            volume = sfx.get("volume", 0.7)

            sfx_obj = SoundEffectLibrary.objects.filter(
                id=effect_id, user=request.api_user
            ).first()

            if not sfx_obj or not sfx_obj.audio_file:
                print(f"⚠️ [API] SFX {effect_id} 없음, 건너뜀")
                continue

            # SFX 시작 시간 = 해당 페이지의 실제 startTime
            start_time = 0
            if timestamps and 0 <= page - 1 < len(timestamps):
                start_time = timestamps[page - 1].get("startTime", 0)

            # SFX 오디오 길이로 종료 시간 계산
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp.write(sfx_obj.audio_file.read())
                temp_sfx_path = tmp.name
                temp_bg_files.append(temp_sfx_path)

            sfx_audio = AudioSegment.from_file(temp_sfx_path)
            sfx_duration = len(sfx_audio)
            end_time = start_time + sfx_duration

            import math
            volume_db = 20 * math.log10(max(volume, 0.01))

            background_tracks_info.append({
                'audioPath': temp_sfx_path,
                'startTime': start_time,
                'endTime': end_time,
                'volume': volume_db,
            })
            sfx_timestamp_entries.append({
                'pageIndex': -1,
                'startTime': int(start_time),
                'endTime': int(end_time),
                'text': '',
                'type': 'sfx',
                'effectName': sfx_obj.effect_name,
            })
            print(f"🔊 [API] SFX '{sfx_obj.effect_name}' → {start_time}ms~{end_time}ms ({volume_db:.1f}dB)")

        if not background_tracks_info:
            return api_response(error="유효한 배경음/사운드 이펙트 트랙이 없습니다.", status=400)

        # 믹싱 실행
        print(f"🎼 [API] 배경음+SFX 믹싱: {len(background_tracks_info)}개 트랙")
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

            # SFX 타임스탬프 업데이트: 기존 SFX 항목 제거 후 새 항목 추가
            if sfx_timestamp_entries and timestamps:
                clean_ts = [t for t in timestamps if t.get('type') != 'sfx']
                merged_ts = clean_ts + sfx_timestamp_entries
                merged_ts.sort(key=lambda x: x.get('startTime', 0))
                content.audio_timestamps = merged_ts
                print(f"📝 [API] SFX 타임스탬프 {len(sfx_timestamp_entries)}개 추가됨")

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

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
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

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
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

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
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
    new_status = data.get("status")  # 'ongoing' | 'completed' | 'hiatus'

    if not book_uuid:
        return api_response(error="book_uuid는 필수입니다.", status=400)

    book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
    if not book:
        return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)

    # 연재 상태 업데이트
    if new_status in ('ongoing', 'completed', 'hiatus'):
        book.status = new_status
        book.save(update_fields=['status'])

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


# ==================== 20. 스냅 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_snap(request):
    """
    스냅(짧은 영상) 생성 API
    - snap_title: 제목 (필수)
    - snap_video: 동영상 파일 (필수)
    - thumbnail: 썸네일 이미지 (선택)
    - book_uuid: 연결할 책 UUID (선택)
    - book_comment: 설명 (선택)
    """
    snap_title = request.POST.get("snap_title", "").strip()
    book_uuid = request.POST.get("book_uuid", "").strip()
    book_comment = request.POST.get("book_comment", "").strip()
    snap_video = request.FILES.get("snap_video")
    thumbnail = request.FILES.get("thumbnail")

    if not snap_title:
        return api_response(error="snap_title은 필수입니다.", status=400)

    if not snap_video and not thumbnail:
        return api_response(error="snap_video 또는 thumbnail 파일이 필요합니다.", status=400)

    # 책 연결
    connected_book = None
    book_link = ""
    if book_uuid:
        try:
            connected_book = Books.objects.get(public_uuid=book_uuid)
            book_link = f"/book/detail/{connected_book.public_uuid}/"
        except Books.DoesNotExist:
            return api_response(error="해당 UUID의 책을 찾을 수 없습니다.", status=404)

    snap = BookSnap(
        snap_title=snap_title,
        book=connected_book,
        book_link=book_link,
        book_comment=book_comment,
        allow_comments=True,
    )

    if snap_video:
        snap.snap_video = snap_video
    if thumbnail:
        snap.thumbnail = thumbnail

    snap.save()

    print(f"📸 [API] 스냅 생성: {snap_title} (UUID: {snap.public_uuid})")

    return api_response(data={
        "snap_uuid": str(snap.public_uuid),
        "snap_title": snap.snap_title,
        "snap_video": snap.snap_video.url if snap.snap_video else None,
        "thumbnail": snap.thumbnail.url if snap.thumbnail else None,
        "book_uuid": str(connected_book.public_uuid) if connected_book else None,
        "message": "스냅이 생성되었습니다."
    })


# ==================== 21. 광고 체크 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_ad_check(request):
    """
    광고 노출 여부 확인 API (카운터 증가 포함)
    - 앱에서 에피소드/스냅 진입 또는 채팅 메시지 전송 시 호출
    - 카운터를 증가시키고 광고 노출 여부를 판단 후 광고 데이터 반환

    POST /api/v1/ads/check/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "placement": "episode"  // "episode" | "chat" | "tts" | "snap"
    }

    Returns (광고 있을 때):
    {
        "success": true,
        "data": {
            "show_ad": true,
            "ad": {
                "uuid": "...",
                "title": "...",
                "ad_type": "audio",
                "placement": "episode",
                "media_url": "https://...",
                "thumbnail_url": null,
                "link_url": "https://...",
                "duration_seconds": 30
            }
        }
    }

    Returns (광고 없을 때):
    {
        "success": true,
        "data": { "show_ad": false, "ad": null }
    }

    노출 빈도:
    - episode: 3번 재생마다 1회 (오디오 광고)
    - chat:    10번 메시지마다 1회 (이미지 광고)
    - tts:     3번 생성마다 1회 (이미지 광고)
    - snap:    20% 랜덤 확률 (영상 광고)
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    placement = data.get("placement", "").strip()
    valid_placements = ["episode", "chat", "tts", "snap"]
    if placement not in valid_placements:
        return api_response(
            error=f"placement는 {', '.join(valid_placements)} 중 하나여야 합니다.",
            status=400,
        )

    user = request.api_user
    counter, _ = UserAdCounter.objects.get_or_create(user=user)

    # 카운터 증가
    if placement == "episode":
        counter.episode_play_count += 1
    elif placement == "chat":
        counter.chat_message_count += 1
    elif placement == "tts":
        counter.tts_count += 1
    elif placement == "snap":
        counter.snap_view_count += 1
    counter.save()

    # 광고 노출 여부 판단 (웹 뷰와 동일한 임계값)
    show_ad = False
    if placement == "snap":
        show_ad = random.random() < 0.2
    elif placement == "episode":
        show_ad = counter.episode_play_count > 0 and counter.episode_play_count % 3 == 0
    elif placement == "chat":
        show_ad = counter.chat_message_count > 0 and counter.chat_message_count % 10 == 0
    elif placement == "tts":
        show_ad = counter.tts_count > 0 and counter.tts_count % 3 == 0

    if not show_ad:
        return api_response(data={"show_ad": False, "ad": None})

    # placement → ad_type 매핑
    type_map = {"episode": "audio", "chat": "image", "tts": "image", "snap": "video"}
    ad_type = type_map[placement]

    # 유효한 광고 랜덤 선택 (날짜 범위 체크)
    now = timezone.now()
    ad = (
        Advertisement.objects.filter(
            placement=placement,
            ad_type=ad_type,
            is_active=True,
        )
        .filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now),
            Q(end_date__isnull=True) | Q(end_date__gte=now),
        )
        .order_by("?")
        .first()
    )

    if not ad:
        return api_response(data={"show_ad": False, "ad": None})

    base_url = request.build_absolute_uri("/").rstrip("/")

    media_url = None
    if ad.audio and ad.ad_type == "audio":
        media_url = base_url + ad.audio.url
    elif ad.image and ad.ad_type == "image":
        media_url = base_url + ad.image.url
    elif ad.video and ad.ad_type == "video":
        media_url = base_url + ad.video.url

    thumbnail_url = base_url + ad.thumbnail.url if ad.thumbnail else None

    print(f"📢 [API] 광고 노출: placement={placement}, ad={ad.title}")

    return api_response(data={
        "show_ad": True,
        "ad": {
            "uuid": str(ad.public_uuid),
            "title": ad.title,
            "ad_type": ad.ad_type,
            "placement": ad.placement,
            "media_url": media_url,
            "thumbnail_url": thumbnail_url,
            "link_url": ad.link_url,
            "duration_seconds": ad.duration_seconds,
        },
    })


# ==================== 22. 광고 노출 기록 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_ad_impression(request):
    """
    광고 노출 기록 API
    - 광고가 실제로 유저에게 보여진 시점에 호출

    POST /api/v1/ads/impression/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "ad_uuid": "xxxx-xxxx-xxxx",
        "placement": "episode"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    ad_uuid = data.get("ad_uuid", "").strip()
    placement = data.get("placement", "").strip()

    if not ad_uuid:
        return api_response(error="ad_uuid는 필수입니다.", status=400)

    try:
        ad = Advertisement.objects.get(public_uuid=ad_uuid)
    except Advertisement.DoesNotExist:
        return api_response(error="광고를 찾을 수 없습니다.", status=404)

    AdImpression.objects.create(
        ad=ad,
        user=request.api_user,
        placement=placement or ad.placement,
    )

    return api_response(data={"message": "노출 기록 완료"})


# ==================== 23. 광고 클릭 기록 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_ad_click(request):
    """
    광고 클릭 기록 API
    - 유저가 광고를 클릭했을 때 호출

    POST /api/v1/ads/click/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "ad_uuid": "xxxx-xxxx-xxxx"
    }

    Returns:
    {
        "success": true,
        "data": {
            "message": "클릭 기록 완료",
            "redirect_url": "https://advertiser.com"
        }
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    ad_uuid = data.get("ad_uuid", "").strip()
    if not ad_uuid:
        return api_response(error="ad_uuid는 필수입니다.", status=400)

    try:
        ad = Advertisement.objects.get(public_uuid=ad_uuid)
    except Advertisement.DoesNotExist:
        return api_response(error="광고를 찾을 수 없습니다.", status=404)

    impression = (
        AdImpression.objects.filter(ad=ad, user=request.api_user)
        .order_by("-created_at")
        .first()
    )
    if impression:
        impression.is_clicked = True
        impression.clicked_at = timezone.now()
        impression.save(update_fields=["is_clicked", "clicked_at"])

    return api_response(data={
        "message": "클릭 기록 완료",
        "redirect_url": ad.link_url,
    })


# ==================== 24. 광고 스킵 기록 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_ad_skip(request):
    """
    광고 스킵 기록 API
    - 유저가 광고를 스킵했을 때 호출 (오디오/영상 광고)

    POST /api/v1/ads/skip/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "ad_uuid": "xxxx-xxxx-xxxx",
        "watched_seconds": 5
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    ad_uuid = data.get("ad_uuid", "").strip()
    watched_seconds = int(data.get("watched_seconds", 0))

    if not ad_uuid:
        return api_response(error="ad_uuid는 필수입니다.", status=400)

    try:
        ad = Advertisement.objects.get(public_uuid=ad_uuid)
    except Advertisement.DoesNotExist:
        return api_response(error="광고를 찾을 수 없습니다.", status=404)

    impression = (
        AdImpression.objects.filter(ad=ad, user=request.api_user)
        .order_by("-created_at")
        .first()
    )
    if impression:
        impression.is_skipped = True
        impression.watched_seconds = watched_seconds
        impression.save(update_fields=["is_skipped", "watched_seconds"])

    return api_response(data={"message": "스킵 기록 완료"})


# ==================== 25. 광고 완료 기록 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_ad_complete(request):
    """
    광고 완료 기록 API
    - 오디오/영상 광고를 스킵 없이 끝까지 시청/청취했을 때 호출
    - CPV 단가 방식일 때 min_watch_seconds 이상 시청 시 CPV 카운트

    POST /api/v1/ads/complete/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "ad_uuid": "xxxx-xxxx-xxxx",
        "watched_seconds": 15
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    ad_uuid = data.get("ad_uuid", "").strip()
    watched_seconds = int(data.get("watched_seconds", 0))

    if not ad_uuid:
        return api_response(error="ad_uuid는 필수입니다.", status=400)

    try:
        ad = Advertisement.objects.get(public_uuid=ad_uuid)
    except Advertisement.DoesNotExist:
        return api_response(error="광고를 찾을 수 없습니다.", status=404)

    impression = (
        AdImpression.objects.filter(ad=ad, user=request.api_user)
        .order_by("-created_at")
        .first()
    )
    if impression:
        impression.is_skipped = False
        impression.watched_seconds = watched_seconds
        impression.save(update_fields=["is_skipped", "watched_seconds"])

    # CPV 달성 여부: pricing_type이 cpv이고 min_watch_seconds 이상 시청
    cpv_counted = (
        ad.pricing_type == "cpv"
        and watched_seconds >= ad.min_watch_seconds
        and ad.min_watch_seconds > 0
    )

    return api_response(data={
        "message": "완료 기록 완료",
        "cpv_counted": cpv_counted,
    })


# ==================== 26. AI 스토리 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_ai_story(request):
    """
    AI 스토리 + LLM 캐릭터 자동 생성 API (이미지/영상 제외 전 필드)

    POST /api/v1/create-ai-story/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "title": "스토리 제목",
        "description": "스토리 설명",
        "genre_ids": [7, 9],
        "tag_names": ["로맨스", "츤데레"],
        "is_adult": false,
        "is_public": false,
        "character_name": "캐릭터 이름",
        "character_title": "캐릭터 한 줄 소개",
        "character_description": "캐릭터 공개 소개문",
        "character_prompt": "캐릭터 시스템 프롬프트",
        "first_sentence": "AI의 첫 마디",
        "narrator_voice_id": "voice_id (선택)",
        "llm_model": "gpt:gpt-4o-mini",
        "temperature": 1.0,
        "stability": 0.5,
        "speed": 1.0,
        "style": 0.5
    }
    """
    from book.api_utils import check_rate_limit
    from character.models import Story, LLM
    from book.models import Genres, Tags, VoiceList

    # AI 생성 전용 엄격한 rate limit (분당 5회)
    is_allowed, _, _ = check_rate_limit(request, key_suffix='create_ai_story', limit=5, period=60)
    if not is_allowed:
        return api_response(error="AI 생성 요청 제한 초과. 1분당 최대 5회 가능합니다.", status=429)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    title = data.get("title", "").strip()
    if not title:
        return api_response(error="title은 필수입니다.", status=400)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        return api_response(error="관리자 계정이 없습니다.", status=500)

    try:
        # Story 생성 (이미지/영상 필드 제외)
        story = Story.objects.create(
            user=admin_user,
            title=title,
            description=data.get("description", ""),
            adult_choice=data.get("is_adult", False),
            is_public=data.get("is_public", False),
        )

        # 장르 설정
        genre_ids = data.get("genre_ids", [])
        if genre_ids:
            story.genres.set(Genres.objects.filter(id__in=genre_ids))

        # 태그 설정 (이름으로 조회)
        tag_names = data.get("tag_names", [])
        if tag_names:
            tags = Tags.objects.filter(name__in=tag_names)
            story.tags.set(tags)

        story.save()

        # LLM 캐릭터 생성 (이미지 필드 제외 전부)
        narrator_voice = None
        narrator_voice_id = data.get("narrator_voice_id", "")
        if narrator_voice_id:
            narrator_voice = VoiceList.objects.filter(voice_id=narrator_voice_id).first()

        llm = LLM.objects.create(
            user=admin_user,
            story=story,
            name=data.get("character_name", title),
            title=data.get("character_title", ""),
            description=data.get("character_description", ""),
            prompt=data.get("character_prompt", ""),
            first_sentence=data.get("first_sentence", ""),
            model=data.get("llm_model", "gpt:gpt-4o-mini"),
            narrator_voice=narrator_voice,
            language="ko",
            temperature=float(data.get("temperature", 1.0)),
            stability=float(data.get("stability", 0.5)),
            speed=float(data.get("speed", 1.0)),
            style=float(data.get("style", 0.5)),
        )

        # 서브이미지 + HP 매핑 생성 (이미지 파일 없음, 텍스트만)
        from character.models import LLMSubImage, HPImageMapping, LastWard, LoreEntry
        sub_images_data = data.get("sub_images", [])
        sub_images_count = 0
        for item in sub_images_data:
            sub_img = LLMSubImage.objects.create(
                llm=llm,
                title=item.get("description", ""),   # 설명 내용 → 제목으로
                description=item.get("title", ""),   # 짧은 제목 → description에
                order=item.get("order", 0),
                is_public=False,
            )
            # HP 매핑 연결
            hp_min = item.get("hp_min")
            hp_max = item.get("hp_max")
            if hp_min is not None and hp_max is not None:
                HPImageMapping.objects.create(
                    llm=llm,
                    sub_image=sub_img,
                    min_hp=hp_min,
                    max_hp=hp_max,
                    note=f"HP {hp_min}~{hp_max} - {item.get('title','')}",
                    priority=item.get("order", 0),
                )
            sub_images_count += 1

        # 마지막 이미지 생성 (이미지 파일 없음, 텍스트만)
        last_wards_data = data.get("last_wards", [])
        last_wards_count = 0
        for item in last_wards_data:
            LastWard.objects.create(
                llm=llm,
                ward=item.get("ward", ""),
                description=item.get("description", ""),
                order=item.get("order", 0),
                is_public=False,
            )
            last_wards_count += 1

        # 로어북 항목 생성
        lore_entries_data = data.get("lore_entries", [])
        lore_count = 0
        for item in lore_entries_data:
            LoreEntry.objects.create(
                llm=llm,
                keys=item.get("keys", ""),
                content=item.get("content", ""),
                priority=item.get("priority", 0),
                always_active=item.get("always_active", False),
                category=item.get("category", "world"),
            )
            lore_count += 1

        return api_response(data={
            "story_uuid":       str(story.public_uuid),
            "story_title":      story.title,
            "llm_uuid":         str(llm.public_uuid),
            "character_name":   llm.name,
            "sub_images_count": sub_images_count,
            "last_wards_count": last_wards_count,
            "lore_count":       lore_count,
            "story_url":        f"https://voxliber.ink/character/story/{story.public_uuid}/",
        })

    except Exception as e:
        return api_response(error=f"스토리 생성 실패: {str(e)}", status=500)


# ==================== 26. AI LLM 추가 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_ai_llm(request):
    """
    기존 스토리에 LLM 캐릭터 추가 생성 API (이미지/영상 제외 전 필드)

    POST /api/v1/create-ai-llm/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "story_uuid": "기존 스토리 UUID (필수)",
        "character_name": "캐릭터 이름",
        "character_title": "캐릭터 한 줄 소개",
        "character_description": "캐릭터 공개 소개문",
        "character_prompt": "캐릭터 시스템 프롬프트",
        "first_sentence": "AI의 첫 마디",
        "narrator_voice_id": "voice_id (선택)",
        "llm_model": "gpt:gpt-4o-mini",
        "temperature": 1.0,
        "stability": 0.5,
        "speed": 1.0,
        "style": 0.5,
        "sub_images": [...],
        "last_wards": [...]
    }
    """
    from book.api_utils import check_rate_limit
    from character.models import Story, LLM, LLMSubImage, HPImageMapping, LastWard
    from book.models import VoiceList

    # AI 생성 전용 엄격한 rate limit (분당 5회)
    is_allowed, _, _ = check_rate_limit(request, key_suffix='create_ai_llm', limit=5, period=60)
    if not is_allowed:
        return api_response(error="AI 생성 요청 제한 초과. 1분당 최대 5회 가능합니다.", status=429)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    story_uuid = data.get("story_uuid", "").strip()
    if not story_uuid:
        return api_response(error="story_uuid는 필수입니다.", status=400)

    try:
        story = Story.objects.get(public_uuid=story_uuid)
    except Story.DoesNotExist:
        return api_response(error=f"스토리를 찾을 수 없습니다: {story_uuid}", status=404)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        return api_response(error="관리자 계정이 없습니다.", status=500)

    try:
        narrator_voice = None
        narrator_voice_id = data.get("narrator_voice_id", "")
        if narrator_voice_id:
            narrator_voice = VoiceList.objects.filter(voice_id=narrator_voice_id).first()

        character_name = data.get("character_name", "").strip()
        if not character_name:
            return api_response(error="character_name은 필수입니다.", status=400)

        llm = LLM.objects.create(
            user=admin_user,
            story=story,
            name=character_name,
            title=data.get("character_title", ""),
            description=data.get("character_description", ""),
            prompt=data.get("character_prompt", ""),
            first_sentence=data.get("first_sentence", ""),
            model=data.get("llm_model", "gpt:gpt-4o-mini"),
            narrator_voice=narrator_voice,
            language="ko",
            temperature=float(data.get("temperature", 1.0)),
            stability=float(data.get("stability", 0.5)),
            speed=float(data.get("speed", 1.0)),
            style=float(data.get("style", 0.5)),
        )

        # 서브이미지 + HP 매핑
        sub_images_count = 0
        for item in data.get("sub_images", []):
            sub_img = LLMSubImage.objects.create(
                llm=llm,
                title=item.get("title", ""),
                description=item.get("description", ""),
                order=item.get("order", 0),
                is_public=False,
            )
            hp_min = item.get("hp_min")
            hp_max = item.get("hp_max")
            if hp_min is not None and hp_max is not None:
                HPImageMapping.objects.create(
                    llm=llm,
                    sub_image=sub_img,
                    min_hp=hp_min,
                    max_hp=hp_max,
                    note=f"HP {hp_min}~{hp_max} - {item.get('title','')}",
                    priority=item.get("order", 0),
                )
            sub_images_count += 1

        # 마지막 이미지
        last_wards_count = 0
        for item in data.get("last_wards", []):
            LastWard.objects.create(
                llm=llm,
                ward=item.get("ward", ""),
                description=item.get("description", ""),
                order=item.get("order", 0),
                is_public=False,
            )
            last_wards_count += 1

        return api_response(data={
            "story_uuid":       str(story.public_uuid),
            "story_title":      story.title,
            "llm_uuid":         str(llm.public_uuid),
            "character_name":   llm.name,
            "sub_images_count": sub_images_count,
            "last_wards_count": last_wards_count,
            "story_url":        f"https://voxliber.ink/character/story/{story.public_uuid}/",
        })

    except Exception as e:
        return api_response(error=f"LLM 생성 실패: {str(e)}", status=500)


# ==================== 27. 로어북 CRUD API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_lore_entry_create(request):
    """
    로어북 항목 생성/수정 API

    POST /api/v1/lore-entry/
    Body (JSON):
    {
        "llm_uuid": "LLM UUID (필수)",
        "entries": [
            {
                "keys": "키워드1, 키워드2",
                "content": "이 키워드가 등장하면 주입될 내용",
                "priority": 10,
                "always_active": false,
                "category": "world"  // personality | world | relationship
            }
        ],
        "replace_all": false  // true면 기존 항목 모두 삭제 후 교체
    }
    """
    from character.models import LLM, LoreEntry

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    llm_uuid = data.get("llm_uuid", "").strip()
    if not llm_uuid:
        return api_response(error="llm_uuid는 필수입니다.", status=400)

    try:
        llm = LLM.objects.get(public_uuid=llm_uuid)
    except LLM.DoesNotExist:
        return api_response(error="LLM을 찾을 수 없습니다.", status=404)

    entries_data = data.get("entries", [])
    if not entries_data:
        return api_response(error="entries는 필수입니다.", status=400)

    VALID_CATEGORIES = {"personality", "world", "relationship", ""}

    try:
        # replace_all=True면 기존 항목 삭제
        if data.get("replace_all", False):
            LoreEntry.objects.filter(llm=llm).delete()

        created = []
        for item in entries_data:
            category = item.get("category", "world")
            if category not in VALID_CATEGORIES:
                category = "world"
            entry = LoreEntry.objects.create(
                llm=llm,
                keys=item.get("keys", ""),
                content=item.get("content", ""),
                priority=int(item.get("priority", 0)),
                always_active=bool(item.get("always_active", False)),
                category=category,
            )
            created.append({
                "id": entry.id,
                "keys": entry.keys,
                "category": entry.category,
                "priority": entry.priority,
                "always_active": entry.always_active,
            })

        return api_response(data={
            "llm_uuid": llm_uuid,
            "created_count": len(created),
            "entries": created,
        })

    except Exception as e:
        return api_response(error=f"로어북 생성 실패: {str(e)}", status=500)


@require_api_key_secure
@require_http_methods(["GET"])
def api_lore_entry_list(request):
    """
    로어북 항목 조회 API

    GET /api/v1/lore-entry/?llm_uuid=<UUID>
    """
    from character.models import LLM, LoreEntry

    llm_uuid = request.GET.get("llm_uuid", "").strip()
    if not llm_uuid:
        return api_response(error="llm_uuid 파라미터가 필요합니다.", status=400)

    try:
        llm = LLM.objects.get(public_uuid=llm_uuid)
    except LLM.DoesNotExist:
        return api_response(error="LLM을 찾을 수 없습니다.", status=404)

    entries = LoreEntry.objects.filter(llm=llm).order_by("-priority", "id")
    return api_response(data={
        "llm_uuid": llm_uuid,
        "character_name": llm.name,
        "total": entries.count(),
        "entries": [
            {
                "id": e.id,
                "keys": e.keys,
                "content": e.content,
                "priority": e.priority,
                "always_active": e.always_active,
                "category": e.category,
            }
            for e in entries
        ],
    })


# ==================== 28. 인기 작가 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_popular_authors(request):
    """
    이달의 작가 (인기 작가) 목록 API

    GET /api/v1/popular-authors/
    Headers: X-API-Key: <your_api_key>

    Returns:
    {
        "success": true,
        "data": {
            "authors": [
                {
                    "user_uuid": "...",
                    "nickname": "작가명",
                    "profile_img": "https://...",
                    "book_count": 3,
                    "avg_score": 4.5,
                    "representative_books": [
                        {"book_uuid": "...", "title": "...", "cover_img": "..."}
                    ]
                }
            ]
        }
    }
    """
    from django.db.models import Count, Sum
    from register.models import Users

    limit = min(int(request.GET.get("limit", 8)), 20)

    authors = (
        Users.objects.annotate(
            book_count=Count("books", distinct=True),
            avg_score=Sum("books__book_score") / Count("books", distinct=True),
        )
        .filter(book_count__gt=0)
        .order_by("-avg_score", "-book_count")[:limit]
    )

    base_url = request.build_absolute_uri("/").rstrip("/")

    authors_data = []
    for author in authors:
        rep_books = Books.objects.filter(user=author, is_deleted=False).order_by("-book_score", "-created_at")[:3]
        rep_books_data = []
        for b in rep_books:
            rep_books_data.append({
                "book_uuid": str(b.public_uuid),
                "title": b.name,
                "cover_img": base_url + b.cover_img.url if b.cover_img else None,
            })

        authors_data.append({
            "user_uuid": str(author.public_uuid) if author.public_uuid else None,
            "nickname": author.nickname,
            "profile_img": base_url + author.user_img.url if author.user_img else None,
            "book_count": author.book_count,
            "avg_score": round(float(author.avg_score or 0), 2),
            "representative_books": rep_books_data,
        })

    return api_response(data={
        "authors": authors_data,
        "total": len(authors_data),
    })


# ==================== 29. 실시간 인기 차트 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_realtime_chart(request):
    """
    실시간 인기 차트 (청취 수 기반) API

    GET /api/v1/realtime-chart/
    Headers: X-API-Key: <your_api_key>

    Query params:
    - limit: 반환 개수 (기본 12, 최대 30)

    Returns:
    {
        "success": true,
        "data": {
            "books": [
                {
                    "rank": 1,
                    "book_uuid": "...",
                    "title": "...",
                    "cover_img": "https://...",
                    "author": "작가명",
                    "author_uuid": "...",
                    "genres": [{"name": "판타지", "color": "#fff"}],
                    "book_score": 4.8,
                    "listener_count": 120,
                    "total_listened_seconds": 36000,
                    "episode_count": 5
                }
            ]
        }
    }
    """
    from django.db.models import Count, Sum

    limit = min(int(request.GET.get("limit", 12)), 30)

    books = (
        Books.objects
        .select_related("user")
        .prefetch_related("genres")
        .annotate(
            total_listened=Sum("listening_stats__listened_seconds"),
            listener_count=Count("listening_stats__user", distinct=True),
            episode_count=Count("contents", distinct=True),
        )
        .order_by("-listener_count", "-total_listened")[:limit]
    )

    base_url = request.build_absolute_uri("/").rstrip("/")

    books_data = []
    for rank, book in enumerate(books, start=1):
        books_data.append({
            "rank": rank,
            "book_uuid": str(book.public_uuid),
            "title": book.name,
            "cover_img": base_url + book.cover_img.url if book.cover_img else None,
            "author": book.user.nickname if book.user else None,
            "author_uuid": str(book.user.public_uuid) if book.user and book.user.public_uuid else None,
            "genres": [{"name": g.name, "color": g.genres_color} for g in book.genres.all()],
            "book_score": float(book.book_score or 0),
            "listener_count": book.listener_count or 0,
            "total_listened_seconds": book.total_listened or 0,
            "episode_count": book.episode_count or 0,
        })

    return api_response(data={
        "books": books_data,
        "total": len(books_data),
    })


# ==================== 30. 공지/새소식 배너 API ====================

@require_api_key_secure
@require_http_methods(["GET"])
def api_announcement(request):
    """
    공지/새소식 배너 API (ScreenAI 첫 번째 항목)

    GET /api/v1/announcement/
    Headers: X-API-Key: <your_api_key>

    Returns:
    {
        "success": true,
        "data": {
            "announcement": {
                "title": "새 기능 출시!",
                "link": "https://voxliber.ink/...",
                "image_url": "https://..."
            }
        }
    }
    """
    from main.models import ScreenAI

    item = ScreenAI.objects.first()
    if not item:
        return api_response(data={"announcement": None})

    base_url = request.build_absolute_uri("/").rstrip("/")
    image_url = base_url + item.advertisment_img.url if item.advertisment_img else None

    return api_response(data={
        "announcement": {
            "title": item.title,
            "link": item.link,
            "image_url": image_url,
        }
    })


# ==================== 웹소설 자동 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_webnovel_generate_episode(request):
    """
    AI 웹소설 에피소드 자동 생성 API

    POST /api/v1/webnovel/generate-episode/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "...",          // 대상 웹소설 UUID
        "episode_number": 2,         // 생성할 화 번호 (없으면 다음 번호 자동)
        "episode_title": "제목",     // 선택 (없으면 AI가 결정)
        "writing_style": "판타지 로맨스, 섬세한 감정 묘사 위주"  // 선택
    }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return api_response(error="JSON 파싱 오류", status=400)

    book_uuid = data.get("book_uuid")
    if not book_uuid:
        return api_response(error="book_uuid 필요", status=400)

    try:
        book = Books.objects.get(public_uuid=book_uuid, is_deleted=False)
    except Books.DoesNotExist:
        return api_response(error="책을 찾을 수 없습니다", status=404)

    # book_type이 webnovel이 아니면 자동 업데이트
    if book.book_type != 'webnovel':
        book.book_type = 'webnovel'
        book.save(update_fields=['book_type'])

    # 다음 에피소드 번호 결정
    last_ep = Content.objects.filter(book=book, is_deleted=False).order_by('-number').first()
    next_number = (last_ep.number + 1) if last_ep else 1
    episode_number = data.get("episode_number", next_number)

    # 이미 존재하면 충돌
    if Content.objects.filter(book=book, number=episode_number, is_deleted=False).exists():
        return api_response(error=f"{episode_number}화가 이미 존재합니다", status=409)

    # provider 결정
    # OpenAI 호환 (큰 컨텍스트): gpt, grok, gemini, qwen, deepseek, mistral, llama
    # Anthropic: claude (기본)
    # 한국 모델: hyperclova, exaone
    LARGE_CONTEXT_PROVIDERS = {"gpt", "grok", "gemini", "qwen", "deepseek", "mistral", "llama"}
    provider = data.get("provider", "claude")

    # 이전 에피소드 컨텍스트
    if provider in LARGE_CONTEXT_PROVIDERS:
        prev_episodes = Content.objects.filter(book=book, is_deleted=False).order_by('-number')[:5]
        prev_context = ""
        for ep in reversed(list(prev_episodes)):
            prev_context += f"\n\n[{ep.number}화: {ep.title}]\n{ep.text}"
    else:
        prev_episodes = Content.objects.filter(book=book, is_deleted=False).order_by('-number')[:3]
        prev_context = ""
        for ep in reversed(list(prev_episodes)):
            prev_context += f"\n\n[{ep.number}화: {ep.title}]\n{ep.text[:600]}..."

    writing_style = data.get("writing_style", "한국 웹소설 스타일, 감정 묘사 풍부, 대화와 서술 균형")
    episode_title_hint = data.get("episode_title", "")

    title_instruction = f"제목: {episode_title_hint}" if episode_title_hint else "적절한 제목을 직접 결정하세요."

    is_adult_book = book.adult_choice
    adult_note = ""
    if is_adult_book:
        adult_note = (
            "\n- 이 작품은 19세 이상 성인 전용 웹소설입니다."
            " 성인 로맨스, 긴장감 있는 밀당, 관능적인 분위기와 선정적 묘사를 포함할 수 있습니다."
            " 단, 지나치게 직접적이거나 노골적인 표현보다는 암시적이고 감각적인 묘사를 우선하며,"
            " 감정선과 스토리 흐름이 끊기지 않는 수준에서 성인 묘사를 자연스럽게 녹여주세요."
        )

    SYSTEM_PROMPT = """당신은 한국에서 가장 흡입력 있는 웹소설을 쓰는 전업 작가입니다.
독자를 이야기 속으로 끌어당기는 강렬한 문장과 예측 불가능한 전개가 당신의 특기입니다.
매화 독자가 다음 화를 기다리지 않을 수 없게 만드는 것이 당신의 사명입니다."""

    prompt = f"""작품 정보:
- 제목: {book.name}
- 설명: {book.description or '없음'}
- 문체/장르: {writing_style}{adult_note}

이전 스토리 흐름:
{prev_context if prev_context else "(첫 번째 화입니다. 매력적인 도입부로 독자를 즉시 사로잡으세요.)"}

---
{episode_number}화를 작성하세요.
{title_instruction}

출력 형식 (아래 구분자를 그대로 사용하세요):
---TITLE---
화 제목
---TEXT---
본문 전체 내용 (줄바꿈으로 단락 구분, 반드시 7000자 이상 10000자 이내)
---END---

【집필 품질 기준】
① 오프닝 훅: 첫 문장부터 독자를 잡아당기세요. 강렬한 행동, 충격적 대사, 또는 긴장감 넘치는 상황으로 시작하세요. "~했다. ~였다." 식의 평범한 도입 금지.
② 장면 구성: 한 화에 최소 3개의 뚜렷한 씬(장면)을 넣으세요. 장면 전환은 자연스럽게.
③ 캐릭터 말투: 각 등장인물은 반드시 고유한 말투를 가져야 합니다 (어휘, 문장 길이, 반말/존댓말, 거친/우아한 표현 등).
④ 감정 표현 (Show, Don't Tell): 감정을 직접 쓰지 마세요. 신체 반응과 행동으로 보여주세요.
   ❌ "그는 분노했다" → ✅ "그의 손이 탁자 모서리를 쥐어뜯었다. 관자놀이에 핏줄이 섰다."
   ❌ "그녀가 설레었다" → ✅ "심장이 제멋대로 뛰었다. 그가 이쪽을 볼까봐, 안 볼까봐 동시에 무서웠다."
⑤ 감각 묘사: 시각에만 의존하지 말고 청각, 촉각, 냄새, 온도감을 활용하여 장면을 생생하게 만드세요.
⑥ 대화 vs 서술 균형: 대화 비중 40% 이상. 대화문은 "" 안에, 앞뒤로 빈 줄 삽입.
⑦ 반복 금지: 같은 단어·표현을 2문단 내에서 반복하지 마세요.
⑧ 단락 구분: 빈 줄로 단락 분리. 감정 태그([calm] 등) 절대 넣지 마세요.
⑨ 출력 형식: 반드시 위 구분자(---TITLE--- 등)만 사용. JSON, 마크다운, 코드블록 금지.

【결말 필수 규칙 — 반드시 지킬 것】
- 이 화는 절대로 완결/해피엔딩/마무리로 끝나면 안 됩니다
- 반드시 다음 중 하나로 끝내세요:
  ① 클리프행어: 위기 상황, 충격적 사실 발각, 예상치 못한 인물 등장
  ② 떡밥 투척: 해결되지 않은 수수께끼나 새로운 의문 제기
  ③ 감정적 훅: 중요한 감정 고조 직전에서 끊기 (고백 직전, 결전 직전 등)
- "~하고 끝났다", "~해서 다행이었다" 같은 해소형 마무리 절대 금지
- 마지막 문장은 독자가 "다음 화가 뭐지?!"라고 느낄 수 있어야 합니다
- 이 화에서 생긴 모든 갈등을 해소하지 말고, 더 큰 갈등의 씨앗을 남기세요
- 이야기는 장편 연재 중이며, 아직 전체 스토리의 절반도 진행되지 않았음을 항상 염두에 두세요"""

    # OpenAI 호환 provider 설정 (base_url, model, env_key)
    _OPENAI_COMPAT = {
        "gpt":       (None,                              "gpt-4o",                    "OPENAI_API_KEY"),
        "grok":      ("https://api.x.ai/v1",             "grok-3",                    "GROK_API_KEY"),
        "gemini":    ("https://generativelanguage.googleapis.com/v1beta/openai/",
                                                         "gemini-2.5-pro",            "GEMINI_API_KEY"),
        "qwen":      ("https://dashscope.aliyuncs.com/compatible-mode/v1",
                                                         "qwen-max",                  "QWEN_API_KEY"),
        "deepseek":  ("https://api.deepseek.com/v1",        "deepseek-chat",                 "DEEPSEEK_API_KEY"),
        "mistral":   ("https://api.mistral.ai/v1",       "mistral-large-latest",      "MISTRAL_API_KEY"),
        "llama":     ("https://api.groq.com/openai/v1",  "llama-3.3-70b-versatile",   "GROQ_API_KEY"),
        "hyperclova":("https://clovastudio.stream.ntruss.com/testapp/v1/chat-completions/HCX-003",
                                                         "HCX-003",                   "HYPERCLOVA_API_KEY"),
        "exaone":    ("https://api.lgresearch.ai/v1",    "EXAONE-4.0-32B",            "EXAONE_API_KEY"),
    }

    try:
        # provider별 AI 호출
        if provider in _OPENAI_COMPAT:
            from openai import OpenAI as _OpenAI
            base_url, model_name, env_key = _OPENAI_COMPAT[provider]
            _key = os.environ.get(env_key, "")
            if not _key:
                return api_response(error=f"{env_key} 환경변수가 설정되지 않았습니다", status=500)
            _ai = _OpenAI(api_key=_key, **({"base_url": base_url} if base_url else {}))
            completion = _ai.chat.completions.create(
                model=model_name,
                max_tokens=12000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            response_text = completion.choices[0].message.content.strip()
        else:
            # Claude (기본) 또는 알 수 없는 provider → claude로 폴백
            import anthropic
            anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not anthropic_api_key:
                return api_response(error="ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다", status=500)
            _client = anthropic.Anthropic(api_key=anthropic_api_key)
            message = _client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=12000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text.strip()

        # 구분자 기반 파싱 (JSON 파싱 오류 방지)
        import re
        title_match = re.search(r'---TITLE---\s*(.*?)\s*---TEXT---', response_text, re.DOTALL)
        # ---END--- 없어도 파싱 (Gemini 응답 잘림 대응)
        text_match = re.search(r'---TEXT---\s*([\s\S]+?)\s*---END---', response_text)
        if not text_match:
            text_match = re.search(r'---TEXT---\s*([\s\S]+)', response_text)
        if not title_match or not text_match:
            return api_response(error=f"AI 응답 파싱 실패: {response_text[:300]}", status=500)
        ep_title = title_match.group(1).strip()
        ep_text = text_match.group(1).strip()

        if not ep_text:
            return api_response(error="AI가 본문을 생성하지 못했습니다", status=500)

        # Content 저장
        episode = Content.objects.create(
            book=book,
            number=episode_number,
            title=ep_title,
            text=ep_text,
            llm_provider=provider,
        )

        return api_response(data={
            "episode_number": episode.number,
            "episode_title": episode.title,
            "content_uuid": str(episode.public_uuid),
            "text_length": len(ep_text),
            "url": f"/book/webnovel/episode/{episode.public_uuid}/",
        })

    except json.JSONDecodeError as e:
        return api_response(error=f"AI 응답 JSON 파싱 오류: {str(e)}", status=500)
    except Exception as e:
        return api_response(error=f"에피소드 생성 오류: {str(e)}", status=500)
