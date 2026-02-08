"""
VOXLIBER 자동 오디오북 생성 API
- Claude(AI)가 소설을 쓰고, API로 책 생성 + 에피소드 TTS 변환까지 자동 처리
"""
import json
import os
import traceback

from django.views.decorators.http import require_http_methods
from django.core.files import File

from book.models import Books, Content, Genres, Tags, VoiceList
from book.api_utils import require_api_key_secure, api_response
from book.utils import generate_tts


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


# ==================== 2. 에피소드 + TTS 생성 API ====================

@require_api_key_secure
@require_http_methods(["POST"])
def api_create_episode(request):
    """
    에피소드 생성 + TTS 자동 변환 API

    POST /api/v1/create-episode/
    Headers: X-API-Key: <your_api_key>
    Body (JSON):
    {
        "book_uuid": "xxxx-xxxx-xxxx",
        "episode_number": 1,
        "episode_title": "제1화: 시작",
        "content_text": "어둠이 내려앉은 숲속에서 한 검사가...",
        "voice_id": "WAhoMTNdLdMoq1j3wf3I",
        "language_code": "ko",
        "speed_value": 1.0,
        "style_value": 0.5,
        "similarity_value": 0.75
    }

    Returns:
    {
        "success": true,
        "data": {
            "content_uuid": "xxxx-xxxx-xxxx",
            "episode_number": 1,
            "episode_title": "제1화: 시작",
            "audio_url": "/media/uploads/audio/response_xxx.mp3",
            "duration_seconds": 180,
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
    content_text = data.get("content_text", "").strip()
    voice_id = data.get("voice_id", "").strip()
    language_code = data.get("language_code", "ko").strip()
    speed_value = data.get("speed_value", 1.0)
    style_value = data.get("style_value", 0.5)
    similarity_value = data.get("similarity_value", 0.75)

    # 필수값 검증
    if not all([book_uuid, episode_number, episode_title, content_text, voice_id]):
        return api_response(
            error="필수 필드: book_uuid, episode_number, episode_title, content_text, voice_id",
            status=400
        )

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
        # 1. 에피소드 생성
        content = Content.objects.create(
            book=book,
            title=episode_title,
            number=int(episode_number),
            text=content_text,
        )
        print(f"📝 [API] 에피소드 생성: {book.name} - {episode_title}")

        # 2. TTS 생성
        print(f"🔊 [API] TTS 생성 시작... (voice: {voice_id}, lang: {language_code})")
        audio_path = generate_tts(
            content_text,
            voice_id,
            language_code,
            speed_value,
            style_value,
            similarity_value,
        )

        audio_url = None
        duration_seconds = 0

        if audio_path and os.path.exists(audio_path):
            # 3. 오디오 파일 저장
            with open(audio_path, 'rb') as audio_file:
                content.audio_file.save(
                    os.path.basename(audio_path),
                    File(audio_file),
                    save=True
                )
            print(f"💾 [API] 오디오 저장 완료: {content.audio_file.url}")

            # 4. 오디오 길이 계산
            from pydub import AudioSegment
            audio_segment = AudioSegment.from_file(audio_path)
            duration_seconds = int(len(audio_segment) / 1000)
            content.duration_seconds = duration_seconds
            content.save()

            audio_url = content.audio_file.url

            # 임시 파일 삭제
            os.remove(audio_path)
            print(f"✅ [API] 에피소드 완료: {duration_seconds}초")
        else:
            print("⚠️ [API] TTS 생성 실패 - 에피소드는 저장됨 (오디오 없음)")

        return api_response(data={
            "content_uuid": str(content.public_uuid),
            "episode_number": content.number,
            "episode_title": content.title,
            "audio_url": audio_url,
            "duration_seconds": duration_seconds,
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

    GET /api/v1/voices/
    Headers: X-API-Key: <your_api_key>
    """
    voices = VoiceList.objects.all().order_by('voice_name')
    voice_data = []
    for v in voices:
        voice_data.append({
            "voice_id": v.voice_id,
            "voice_name": v.voice_name,
            "language_code": v.language_code,
            "description": v.voice_description or "",
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
