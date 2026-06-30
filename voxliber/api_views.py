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
    SoundEffectLibrary, BackgroundMusicLibrary, BookSnap, PageAudio,
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
        page_infos = []  # PageAudio 저장용: (audio_path, page_number, text, voice_id, page_type, speed, style, sim)

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
                        page_infos.append({'path': silence_path, 'page_number': len(audio_paths),
                            'text': '', 'voice_id': '', 'page_type': 'silence',
                            'speed': 1.0, 'style': 0.0, 'sim': 0.75})
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
                            page_infos.append({'path': duet_mp3, 'page_number': len(audio_paths),
                                'text': combined_text, 'voice_id': (voices[0].get('voice_id','') if voices else ''),
                                'page_type': 'duet', 'speed': 1.0, 'style': 0.0, 'sim': 0.75})
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
                page_infos.append({'path': audio_path, 'page_number': len(audio_paths),
                    'text': page_text, 'voice_id': page_voice, 'page_type': 'tts',
                    'speed': page_speed, 'style': page_style, 'sim': page_similarity})
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

            # 7. PageAudio 개별 저장 (regen_page 등에서 참조 가능하도록)
            try:
                for info in page_infos:
                    fpath = info['path']
                    if not fpath or not os.path.exists(fpath):
                        continue
                    try:
                        pa = PageAudio(
                            content=content,
                            page_number=info['page_number'],
                            text=info['text'],
                            voice_id=info['voice_id'],
                            language_code='ko',
                            speed_value=info['speed'],
                            style_value=info['style'],
                            similarity_value=info['sim'],
                            webaudio_effect='normal',
                            page_type=info['page_type'],
                        )
                        with open(fpath, 'rb') as pf:
                            pa.audio_file.save(os.path.basename(fpath), File(pf), save=True)
                    except Exception as e:
                        print(f"  ⚠️ PageAudio 저장 실패 P{info['page_number']}: {e}")
                print(f"💾 [API] PageAudio {len(page_infos)}개 저장 완료")
            except Exception as e:
                print(f"  ⚠️ PageAudio 전체 저장 오류: {e}")

            # 8. 임시 개별 TTS 파일 삭제
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

def _resolve_content(api_user, book_uuid=None, episode_number=None, content_uuid=None):
    """공통 Content 조회 헬퍼. (content, error_msg) 반환"""
    if content_uuid:
        content = Content.objects.filter(
            public_uuid=content_uuid, book__user=api_user, is_deleted=False
        ).first()
    elif book_uuid and episode_number is not None:
        book = Books.objects.filter(public_uuid=book_uuid, user=api_user, is_deleted=False).first()
        if not book:
            return None, "책을 찾을 수 없거나 권한이 없습니다."
        content = Content.objects.filter(book=book, number=int(episode_number), is_deleted=False).first()
    else:
        return None, "book_uuid+episode_number 또는 content_uuid가 필요합니다."
    if not content:
        return None, "에피소드를 찾을 수 없습니다."
    if not content.audio_file:
        return None, "에피소드 오디오 파일이 없습니다."
    return content, None


def _do_episode_mix(content, bg_tracks, sfx_tracks, api_user):
    """
    BGM + SFX 믹싱 실행 헬퍼.
    - content.tts_audio_file이 있으면 그것을 base로 사용 (re-mix 가능)
    - 없으면 content.audio_file을 base로 사용하고 tts_audio_file에 백업
    - bg_tracks: [{"music_id":N, "start_page":N, "end_page":N, "volume":0.3}, ...]
    - sfx_tracks: [{"effect_id":N, "page_number":N, "volume":0.7}, ...]
    반환: (result_data dict, error_str or None)
    """
    import math
    from pydub import AudioSegment

    # 원본 TTS 오디오 결정 (tts_audio_file 우선)
    if content.tts_audio_file:
        base_audio_path = content.tts_audio_file.path
    else:
        # 최초 믹싱: 현재 audio_file을 tts_audio_file로 백업
        base_audio_path = content.audio_file.path
        with open(base_audio_path, 'rb') as f:
            import os as _os
            content.tts_audio_file.save(
                'tts_' + _os.path.basename(base_audio_path),
                File(f),
                save=True
            )
        print(f"💾 [MIX] 원본 TTS 오디오 백업 완료")

    timestamps = content.audio_timestamps or []
    if isinstance(timestamps, str):
        timestamps = json.loads(timestamps)

    background_tracks_info = []
    temp_files = []
    new_bgm_config = []
    new_sfx_config = []

    # BGM 트랙 처리
    for track in bg_tracks:
        music_id = track.get("music_id")
        start_page = track.get("start_page", 0)
        end_page = track.get("end_page", len(timestamps) - 1 if timestamps else 0)
        volume = track.get("volume", 0.3)

        bg_music = BackgroundMusicLibrary.objects.filter(id=music_id, user=api_user).first()
        if not bg_music or not bg_music.audio_file:
            print(f"⚠️ [MIX] BGM {music_id} 없음, 건너뜀")
            continue

        start_time = 0
        end_time = (content.duration_seconds or 0) * 1000
        if timestamps:
            if start_page > 0 and start_page - 1 < len(timestamps):
                start_time = timestamps[start_page - 1].get("endTime", 0)
            if end_page < len(timestamps):
                end_time = timestamps[end_page].get("endTime", end_time)

        volume_db = 20 * math.log10(max(volume, 0.01))

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(bg_music.audio_file.read())
            temp_path = tmp.name
            temp_files.append(temp_path)

        background_tracks_info.append({
            'audioPath': temp_path,
            'startTime': start_time,
            'endTime': end_time,
            'volume': volume_db,
        })
        new_bgm_config.append({
            'id': music_id,
            'name': bg_music.music_name,
            'desc': bg_music.music_description or '',
            'volume': volume,
            'start_page': start_page,
            'end_page': end_page,
        })

    # SFX 트랙 처리
    sfx_timestamp_entries = []
    for sfx in sfx_tracks:
        effect_id = sfx.get("effect_id")
        page = sfx.get("page_number") or sfx.get("page") or 1
        volume = sfx.get("volume", 0.7)

        sfx_obj = SoundEffectLibrary.objects.filter(id=effect_id, user=api_user).first()
        if not sfx_obj or not sfx_obj.audio_file:
            print(f"⚠️ [MIX] SFX {effect_id} 없음, 건너뜀")
            continue

        start_time = 0
        if timestamps and 0 <= page - 1 < len(timestamps):
            start_time = timestamps[page - 1].get("startTime", 0)

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(sfx_obj.audio_file.read())
            temp_path = tmp.name
            temp_files.append(temp_path)

        sfx_audio = AudioSegment.from_file(temp_path)
        sfx_duration = len(sfx_audio)
        end_time = start_time + sfx_duration
        volume_db = 20 * math.log10(max(volume, 0.01))

        background_tracks_info.append({
            'audioPath': temp_path,
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
        new_sfx_config.append({
            'id': effect_id,
            'name': sfx_obj.effect_name,
            'desc': sfx_obj.effect_description or '',
            'volume': volume,
            'page_number': page,
        })
        print(f"🔊 [MIX] SFX '{sfx_obj.effect_name}' → {start_time}ms~{end_time}ms ({volume_db:.1f}dB)")

    if not background_tracks_info:
        return None, "유효한 BGM/SFX 트랙이 없습니다."

    print(f"🎼 [MIX] 믹싱 실행: BGM {len(new_bgm_config)}개 + SFX {len(new_sfx_config)}개")
    mixed_path = mix_audio_with_background(base_audio_path, background_tracks_info)

    for tmp_path in temp_files:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not mixed_path or mixed_path == base_audio_path:
        return None, "믹싱에 실패했습니다."

    try:
        with open(mixed_path, 'rb') as f:
            content.audio_file.save(os.path.basename(mixed_path), File(f), save=True)

        audio_segment = AudioSegment.from_file(mixed_path)
        content.duration_seconds = int(len(audio_segment) / 1000)

        # SFX 타임스탬프 업데이트
        if sfx_timestamp_entries and timestamps:
            clean_ts = [t for t in timestamps if t.get('type') != 'sfx']
            merged_ts = sorted(clean_ts + sfx_timestamp_entries, key=lambda x: x.get('startTime', 0))
            content.audio_timestamps = merged_ts

        # mix_config 저장
        content.mix_config = {
            'bgm': new_bgm_config,
            'sfx': new_sfx_config,
        }
        content.save()

        os.remove(mixed_path)
        print(f"✅ [MIX] 완료: {content.duration_seconds}초")

        return {
            "content_uuid": str(content.public_uuid),
            "episode_number": content.number,
            "audio_url": content.audio_file.url,
            "duration_seconds": content.duration_seconds,
            "mix_config": content.mix_config,
        }, None

    except Exception as e:
        if os.path.exists(mixed_path):
            os.remove(mixed_path)
        raise


@require_api_key_secure
@require_http_methods(["POST"])
def api_mix_background_music(request):
    """
    에피소드에 BGM + SFX 믹싱 API (전체 설정)

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
            {"effect_id": 1, "page_number": 3, "volume": 0.7}
        ]
    }
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

    content, err = _resolve_content(request.api_user, book_uuid=book_uuid, episode_number=episode_number)
    if err:
        return api_response(error=err, status=404)

    try:
        result, err = _do_episode_mix(content, bg_tracks, sfx_tracks, request.api_user)
        if err:
            return api_response(error=err, status=400)
        return api_response(data={**result, "message": "BGM/SFX 믹싱 완료"})
    except Exception as e:
        print(f"❌ [API] 배경음 믹싱 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"배경음 믹싱 중 오류: {str(e)}", status=500)


@require_api_key_secure
@require_http_methods(["POST"])
def api_set_episode_bgm(request):
    """
    에피소드 BGM만 교체 (기존 SFX 설정은 유지)

    POST /api/v1/set-bgm/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx",          // book_uuid+episode_number 또는
        "episode_number": 1,          //   content_uuid 중 하나
        "content_uuid": "xxxx",       // (선택)
        "background_tracks": [
            {"music_id": 5, "start_page": 0, "end_page": 9, "volume": 0.22}
        ]
    }
    빈 배열 [] 전달 시 BGM 제거 후 SFX만으로 재믹싱.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    bg_tracks = data.get("background_tracks", [])
    if bg_tracks is None:
        return api_response(error="background_tracks 키가 필요합니다.", status=400)

    content, err = _resolve_content(
        request.api_user,
        book_uuid=data.get("book_uuid", "").strip(),
        episode_number=data.get("episode_number"),
        content_uuid=data.get("content_uuid", "").strip() or None,
    )
    if err:
        return api_response(error=err, status=404)

    # 기존 SFX 설정 유지
    mc = content.mix_config or {}
    existing_sfx = mc.get('sfx', [])
    sfx_tracks = [{'effect_id': s['id'], 'page_number': s.get('page_number', 1), 'volume': s.get('volume', 0.7)}
                  for s in existing_sfx]

    if not bg_tracks and not sfx_tracks:
        return api_response(error="background_tracks가 비어있고 기존 SFX도 없습니다.", status=400)

    try:
        result, err = _do_episode_mix(content, bg_tracks, sfx_tracks, request.api_user)
        if err:
            return api_response(error=err, status=400)
        return api_response(data={**result, "message": "BGM 업데이트 완료 (SFX 유지)"})
    except Exception as e:
        print(f"❌ [API] set-bgm 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"BGM 설정 오류: {str(e)}", status=500)


@require_api_key_secure
@require_http_methods(["POST"])
def api_set_episode_sfx(request):
    """
    에피소드 SFX만 교체 (기존 BGM 설정은 유지)

    POST /api/v1/set-sfx/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx",          // book_uuid+episode_number 또는
        "episode_number": 1,          //   content_uuid 중 하나
        "content_uuid": "xxxx",       // (선택)
        "sound_effects": [
            {"effect_id": 243, "page_number": 3, "volume": 0.7}
        ]
    }
    빈 배열 [] 전달 시 SFX 제거 후 BGM만으로 재믹싱.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    sfx_tracks = data.get("sound_effects", [])
    if sfx_tracks is None:
        return api_response(error="sound_effects 키가 필요합니다.", status=400)

    content, err = _resolve_content(
        request.api_user,
        book_uuid=data.get("book_uuid", "").strip(),
        episode_number=data.get("episode_number"),
        content_uuid=data.get("content_uuid", "").strip() or None,
    )
    if err:
        return api_response(error=err, status=404)

    # 기존 BGM 설정 유지
    mc = content.mix_config or {}
    existing_bgm = mc.get('bgm', [])
    bg_tracks = [{'music_id': b['id'], 'start_page': b.get('start_page', 0),
                  'end_page': b.get('end_page', -1), 'volume': b.get('volume', 0.25)}
                 for b in existing_bgm]

    if not sfx_tracks and not bg_tracks:
        return api_response(error="sound_effects가 비어있고 기존 BGM도 없습니다.", status=400)

    try:
        result, err = _do_episode_mix(content, bg_tracks, sfx_tracks, request.api_user)
        if err:
            return api_response(error=err, status=400)
        return api_response(data={**result, "message": "SFX 업데이트 완료 (BGM 유지)"})
    except Exception as e:
        print(f"❌ [API] set-sfx 오류: {e}")
        traceback.print_exc()
        return api_response(error=f"SFX 설정 오류: {str(e)}", status=500)


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



# ==================== 26. AI 스토리 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
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



# ==================== 웹소설 자동 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_episode_detail(request):
    """
    에피소드 상세 조회 (페이지 목록 + BGM/SFX 정보)

    GET /api/v1/episode-detail/?content_uuid=xxx
    GET /api/v1/episode-detail/?book_uuid=xxx&episode_number=2
    Headers: X-API-Key: <your_api_key>
    """
    content_uuid = request.GET.get("content_uuid", "").strip()
    book_uuid = request.GET.get("book_uuid", "").strip()
    episode_number = request.GET.get("episode_number")

    if content_uuid:
        content = Content.objects.filter(
            public_uuid=content_uuid, book__user=request.api_user, is_deleted=False
        ).first()
    elif book_uuid and episode_number:
        content = Content.objects.filter(
            book__public_uuid=book_uuid, book__user=request.api_user,
            number=int(episode_number), is_deleted=False
        ).first()
    else:
        return api_response(error="content_uuid 또는 book_uuid+episode_number 필수", status=400)

    if not content:
        return api_response(error="에피소드를 찾을 수 없습니다.", status=404)

    pages_data = []
    for pa in PageAudio.objects.filter(content=content).order_by('page_number'):
        pages_data.append({
            "page_number": pa.page_number,
            "page_type": pa.page_type or "tts",
            "text": pa.text or "",
            "voice_id": pa.voice_id or "",
            "webaudio_effect": pa.webaudio_effect or "",
            "speed_value": pa.speed_value,
            "audio_url": pa.audio_file.url if pa.audio_file else None,
        })

    mc = content.mix_config or {}
    bgm_list, sfx_list = [], []
    for b in mc.get('bgm', []):
        bgm_list.append({
            "bgm_id": b.get('id'),
            "name": b.get('name', ''),
            "start_page": b.get('start_page', 0),
            "end_page": b.get('end_page', -1),
            "volume": b.get('volume', 0.25),
        })
    for s in mc.get('sfx', []):
        sfx_list.append({
            "sfx_id": s.get('id'),
            "name": s.get('name', ''),
            "page_number": s.get('page_number', 1),
            "volume": s.get('volume', 0.7),
        })

    return api_response(data={
        "content_uuid": str(content.public_uuid),
        "book_uuid": str(content.book.public_uuid),
        "title": content.title or "",
        "number": content.number,
        "duration_seconds": content.duration_seconds or 0,
        "pages": pages_data,
        "bgm": bgm_list,
        "sfx": sfx_list,
    })


# ==================== 부분 재생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_regenerate_page(request):
    """
    단일 페이지 TTS 재생성 API

    POST /api/v1/regenerate-page/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "content_uuid": "xxxx-xxxx",
        "page_number": 3,
        "text": "재생성할 텍스트",
        "voice_id": "voice_id",
        "speed_value": 1.0,      (선택, 기존값 유지)
        "style_value": 0.85,     (선택)
        "similarity_value": 0.75 (선택)
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    content_uuid = data.get("content_uuid", "").strip()
    page_number = data.get("page_number")
    text = data.get("text", "").strip()
    voice_id = data.get("voice_id", "").strip()

    if not content_uuid or page_number is None or not text or not voice_id:
        return api_response(error="content_uuid, page_number, text, voice_id는 필수입니다.", status=400)

    content = Content.objects.filter(
        public_uuid=content_uuid, book__user=request.api_user, is_deleted=False
    ).first()
    if not content:
        return api_response(error="에피소드를 찾을 수 없거나 권한이 없습니다.", status=404)

    pa = PageAudio.objects.filter(content=content, page_number=int(page_number)).first()
    if not pa:
        return api_response(error=f"페이지 {page_number}을 찾을 수 없습니다.", status=404)

    speed = float(data.get("speed_value", pa.speed_value))
    style = float(data.get("style_value", pa.style_value))
    similarity = float(data.get("similarity_value", pa.similarity_value))

    try:
        audio_path = generate_tts(text, voice_id, pa.language_code, speed, style, similarity)
        if not audio_path:
            return api_response(error="TTS 생성 실패", status=500)

        if pa.audio_file:
            try:
                old_path = pa.audio_file.path
                pa.audio_file.delete(save=False)
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception:
                pass

        pa.text = text
        pa.voice_id = voice_id
        pa.speed_value = speed
        pa.style_value = style
        pa.similarity_value = similarity
        with open(audio_path, 'rb') as f:
            pa.audio_file.save(os.path.basename(audio_path), File(f), save=True)
        if os.path.exists(audio_path):
            os.remove(audio_path)

        print(f"✅ [API] 페이지 {page_number} TTS 재생성 완료")
        return api_response(data={
            "page_number": int(page_number),
            "audio_url": pa.audio_file.url,
            "message": f"페이지 {page_number} TTS 재생성 완료"
        })
    except Exception as e:
        traceback.print_exc()
        return api_response(error=f"TTS 재생성 오류: {str(e)}", status=500)


@require_api_key_secure
@require_http_methods(["POST"])
def api_register_pages(request):
    """
    에피소드 페이지 메타데이터 등록 API (TTS 생성 없이 PageAudio 엔트리만 생성)
    - create_episode 후 에디터에서 블록을 표시하기 위한 메타 등록
    - 이미 PageAudio가 존재하면 text/voice_id를 업데이트

    POST /api/v1/register-pages/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "content_uuid": "xxxx",   // content_uuid 또는 book_uuid+episode_number
        "book_uuid": "xxxx",
        "episode_number": 1,
        "pages": [
            {"text": "[calm] 나레이션 텍스트", "voice_id": "ThT5Kc...", "webaudio_effect": "normal"},
            {"text": "[formal] 대사", "voice_id": "9BWts...", "webaudio_effect": "normal"},
            {"silence_seconds": 1.0},
            {"voices": [{"text": "A 대사", "voice_id": "..."}, {"text": "B 대사", "voice_id": "..."}]}
        ]
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    pages_input = data.get("pages", [])
    if not pages_input:
        return api_response(error="pages 배열이 필요합니다.", status=400)

    content_uuid = data.get("content_uuid", "").strip()
    book_uuid = data.get("book_uuid", "").strip()
    episode_number = data.get("episode_number")

    if content_uuid:
        content = Content.objects.filter(
            public_uuid=content_uuid, book__user=request.api_user, is_deleted=False
        ).first()
    elif book_uuid and episode_number is not None:
        book = Books.objects.filter(public_uuid=book_uuid, user=request.api_user, is_deleted=False).first()
        if not book:
            return api_response(error="책을 찾을 수 없거나 권한이 없습니다.", status=404)
        content = Content.objects.filter(book=book, number=int(episode_number), is_deleted=False).first()
    else:
        return api_response(error="content_uuid 또는 book_uuid+episode_number가 필요합니다.", status=400)

    if not content:
        return api_response(error="에피소드를 찾을 수 없습니다.", status=404)

    created, updated = 0, 0
    page_num = 0
    for page in pages_input:
        page_num += 1

        # 페이지 타입 결정
        if page.get("silence_seconds") is not None:
            p_type = 'silence'
            p_text = ''
            p_voice = ''
        elif page.get("voices"):
            p_type = 'duet'
            p_text = '\n'.join(v.get("text", "") for v in page["voices"] if v.get("text"))
            p_voice = page["voices"][0].get("voice_id", "") if page["voices"] else ""
        else:
            p_type = 'tts'
            p_text = page.get("text", "")
            p_voice = page.get("voice_id", "")

        webaudio = page.get("webaudio_effect", "normal") or "normal"
        speed = float(page.get("speed_value", 1.0))
        style = float(page.get("style_value", 0.5))
        sim = float(page.get("similarity_value", 0.75))

        pa = PageAudio.objects.filter(content=content, page_number=page_num).first()
        if pa:
            # 기존 항목 업데이트 (audio_file 유지)
            pa.text = p_text
            pa.voice_id = p_voice
            pa.page_type = p_type
            pa.webaudio_effect = webaudio
            pa.speed_value = speed
            pa.style_value = style
            pa.similarity_value = sim
            pa.save(update_fields=['text', 'voice_id', 'page_type', 'webaudio_effect',
                                   'speed_value', 'style_value', 'similarity_value'])
            updated += 1
        else:
            PageAudio.objects.create(
                content=content,
                page_number=page_num,
                text=p_text,
                voice_id=p_voice,
                page_type=p_type,
                webaudio_effect=webaudio,
                speed_value=speed,
                style_value=style,
                similarity_value=sim,
                language_code='ko',
            )
            created += 1

    print(f"✅ [API] register-pages: created={created} updated={updated} total={page_num}")
    return api_response(data={
        "content_uuid": str(content.public_uuid),
        "total_pages": page_num,
        "created": created,
        "updated": updated,
        "message": f"PageAudio 등록 완료 ({created}개 생성, {updated}개 업데이트)"
    })


@require_api_key_secure
@require_http_methods(["POST"])
def api_regenerate_sfx(request):
    """
    SFX 재생성 API (기존 SFX 오디오를 새로 생성)

    POST /api/v1/regenerate-sfx/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "sfx_id": 5,
        "desc": "새 설명 (선택, 없으면 기존 설명 유지)",
        "duration": 5
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    sfx_id = data.get("sfx_id")
    if not sfx_id:
        return api_response(error="sfx_id는 필수입니다.", status=400)

    sfx_obj = SoundEffectLibrary.objects.filter(id=sfx_id, user=request.api_user).first()
    if not sfx_obj:
        return api_response(error="SFX를 찾을 수 없거나 권한이 없습니다.", status=404)

    desc = data.get("desc", sfx_obj.effect_description)
    duration = int(data.get("duration", 5))

    try:
        new_path = sound_effect(sfx_obj.effect_name, desc, duration)
        if not new_path or not os.path.exists(new_path):
            return api_response(error="SFX 생성 실패", status=500)

        if sfx_obj.audio_file:
            try:
                old = sfx_obj.audio_file.path
                sfx_obj.audio_file.delete(save=False)
                if os.path.exists(old):
                    os.remove(old)
            except Exception:
                pass

        with open(new_path, 'rb') as f:
            sfx_obj.audio_file.save(os.path.basename(new_path), File(f), save=True)
        sfx_obj.effect_description = desc
        sfx_obj.save()
        if os.path.exists(new_path):
            os.remove(new_path)

        print(f"✅ [API] SFX {sfx_id} 재생성 완료")
        return api_response(data={
            "sfx_id": sfx_obj.id,
            "effect_name": sfx_obj.effect_name,
            "audio_url": sfx_obj.audio_file.url,
            "message": "SFX 재생성 완료"
        })
    except Exception as e:
        traceback.print_exc()
        return api_response(error=f"SFX 재생성 오류: {str(e)}", status=500)


@require_api_key_secure
@require_http_methods(["POST"])
def api_regenerate_bgm(request):
    """
    BGM 재생성 API (기존 BGM 오디오를 새로 생성)

    POST /api/v1/regenerate-bgm/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "bgm_id": 3,
        "desc": "새 설명 (선택, 없으면 기존 설명 유지)",
        "duration": 30
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return api_response(error="JSON 형식이 올바르지 않습니다.", status=400)

    bgm_id = data.get("bgm_id")
    if not bgm_id:
        return api_response(error="bgm_id는 필수입니다.", status=400)

    bgm_obj = BackgroundMusicLibrary.objects.filter(id=bgm_id, user=request.api_user).first()
    if not bgm_obj:
        return api_response(error="BGM을 찾을 수 없거나 권한이 없습니다.", status=404)

    desc = data.get("desc", bgm_obj.music_description)
    duration = int(data.get("duration", bgm_obj.duration_seconds or 30))

    try:
        new_path = background_music(bgm_obj.music_name, desc, duration)
        if not new_path or not os.path.exists(new_path):
            return api_response(error="BGM 생성 실패", status=500)

        if bgm_obj.audio_file:
            try:
                old = bgm_obj.audio_file.path
                bgm_obj.audio_file.delete(save=False)
                if os.path.exists(old):
                    os.remove(old)
            except Exception:
                pass

        with open(new_path, 'rb') as f:
            bgm_obj.audio_file.save(os.path.basename(new_path), File(f), save=True)
        bgm_obj.music_description = desc
        bgm_obj.duration_seconds = duration
        bgm_obj.save()
        if os.path.exists(new_path):
            os.remove(new_path)

        print(f"✅ [API] BGM {bgm_id} 재생성 완료")
        return api_response(data={
            "bgm_id": bgm_obj.id,
            "music_name": bgm_obj.music_name,
            "audio_url": bgm_obj.audio_file.url,
            "message": "BGM 재생성 완료"
        })
    except Exception as e:
        traceback.print_exc()
        return api_response(error=f"BGM 재생성 오류: {str(e)}", status=500)
