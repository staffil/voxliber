from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse,HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from book.models import Genres, Books, Tags, VoiceList, BookSnap, MyVoiceList, Content, APIKey
from book.api_utils import require_api_key_secure
from voxliber.security import validate_image_file, validate_video_file, validate_audio_file
import os
from django.conf import settings
from register.decorator import login_required_to_main
from character.models import LLM, Story, Conversation, ConversationMessage
from book.utils import merge_audio_files
from django.urls import reverse
COLAB_TTS_URL = os.getenv('COLAB_TTS_URL', 'https://xxxx.ngrok-free.app')

# 작품 등록 이용약관

def book_tos(request):
    context = {
        'some_data': ..., 
    }

    # 로그인 여부 체크
    if not request.user.is_authenticated:
        context['show_login_card'] = True
        context['content_locked'] = True  # 콘텐츠 숨기기 플래그
    else:
        context['show_login_card'] = False
        context['content_locked'] = False
    return render(request, "book/book_TOS.html")


# 태그 검색
@require_GET
def search_tags(request):
    query = request.GET.get("q", "")
    tags = Tags.objects.filter(name__icontains=query)
    result = [{"id": tag.id, "name": tag.name} for tag in tags]
    return JsonResponse(result, safe=False)


# 태그 추가
@require_POST
def add_tags(request):
    from django.utils.text import slugify
    import uuid

    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "태그 이름이 필요합니다."}, status=400)

    # slug 생성 (중복 방지를 위해 unique한 값 추가)
    base_slug = slugify(name, allow_unicode=True)
    if not base_slug:
        base_slug = f"tag-{uuid.uuid4().hex[:8]}"

    # 같은 이름의 태그가 있는지 확인
    tag = Tags.objects.filter(name=name).first()
    if tag:
        return JsonResponse({"id": tag.id, "name": tag.name, "created": False})

    # 중복되지 않는 slug 찾기
    slug = base_slug
    counter = 1
    while Tags.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    # 새 태그 생성
    tag = Tags.objects.create(name=name, slug=slug)
    return JsonResponse({"id": tag.id, "name": tag.name, "created": True})

# 작품 프로필 등록
@login_required_to_main
def book_profile(request):
    genres_list = Genres.objects.all()
    tag_list = Tags.objects.all()
    voice_list = VoiceList.objects.all()
    book_uuid = request.GET.get("public_uuid")
    book = Books.objects.filter(public_uuid=book_uuid, is_deleted=False).first() if book_uuid else None

    if request.method == "POST":
        novel_title = request.POST.get("novel_title", "").strip()
        novel_description = request.POST.get("novel_description", "").strip()
        genre_ids = request.POST.getlist("genres")
        episode_interval_weeks = request.POST.get("episode_interval_weeks", "1")
        is_adult = request.POST.get("adult_choice") == "on"
        write_mode = request.POST.get("write_mode", "beginner")  # ★ 모드 수신
        print(f"[DEBUG] is_adult 값: {is_adult}, write_mode: {write_mode}")

        if not novel_title:
            context = {
                "error": "소설 제목을 입력해주세요.",
                "genres_list": genres_list,
                "tag_list": tag_list,
                "book": book,
            }
            return render(request, "book/book_profile.html", context)

        if book:
            book.name = novel_title
            book.description = novel_description
            book.episode_interval_weeks = int(episode_interval_weeks)
            book.adult_choice = is_adult
            if "cover-image" in request.FILES:
                book.cover_img = request.FILES["cover-image"]
            book.save()
        else:
            existing = Books.objects.filter(name=novel_title).first()
            if existing:
                book = existing
                book.description = novel_description
                book.episode_interval_weeks = int(episode_interval_weeks)
                book.adult_choice = is_adult
                if "cover-image" in request.FILES:
                    book.cover_img = request.FILES["cover-image"]
                book.save()
            else:
                book = Books.objects.create(
                    user=request.user,
                    name=novel_title,
                    description=novel_description,
                    episode_interval_weeks=int(episode_interval_weeks),
                    adult_choice=is_adult,
                )
                if "cover-image" in request.FILES:
                    book.cover_img = request.FILES["cover-image"]
                    book.save()

        # 장르 처리
        if genre_ids:
            genre_ids = [int(g) for g in genre_ids if g.strip().isdigit()]
            if genre_ids:
                book.genres.set(Genres.objects.filter(id__in=genre_ids))
            else:
                book.genres.clear()
        else:
            book.genres.clear()

        # 태그 처리
        tag_ids = request.POST.getlist("tags")
        if tag_ids:
            tag_ids = [int(t) for t in tag_ids if t.strip().isdigit()]
            if tag_ids:
                book.tags.set(Tags.objects.filter(id__in=tag_ids))
            else:
                book.tags.clear()
        else:
            book.tags.clear()

        # ★ 모드별 리다이렉트
        if write_mode == "expert":
            return redirect(f"/book/book/serialization/?public_uuid={book.public_uuid}")
        elif write_mode == "voice":
            return redirect(f"/voice/voice/list/")
        else:  # beginner (기본)
            return redirect(f"/book/serialization/fast/{book.public_uuid}/")

    context = {
        "genres_list": genres_list,
        "tag_list": tag_list,
        "book": book,
        "voice_list": voice_list,
    }
    return render(request, "book/book_profile.html", context)

from uuid import uuid4
# 작품 연재 등록 (집필 페이지)
@login_required_to_main
def book_serialization(request):
    import json
    from book.models import Content, AudioBookGuide
    from django.core import serializers

    book_uuid = request.GET.get("public_uuid") or request.POST.get("public_uuid")
    book = Books.objects.filter(public_uuid=book_uuid).first() if book_uuid else None

    # 오디오북 가이드
    audioBookGuide = AudioBookGuide.objects.all()
    # ImageField와 FileField의 URL을 포함하도록 수동 직렬화
    audioBookGuide_data = []
    for guide in audioBookGuide:
        audioBookGuide_data.append({
            'pk': guide.id,
            'fields': {
                'title': guide.title,
                'short_description': guide.short_description,
                'description': guide.description,
                'category': guide.category,
                'tags': guide.tags,
                'thumbnail': guide.thumbnail.url if guide.thumbnail else None,
                'video_url': guide.video_url,
                'guide_video': guide.guide_video.url if guide.guide_video else None,
            }
        })
    audioBookGuide = json.dumps(audioBookGuide_data)

    if not book:
        if request.method == "POST":
            return JsonResponse({"success": False, "error": "책을 찾을 수 없습니다."}, status=404)
        return redirect("book:book_profile")

    if request.method == "POST":
        content_number = request.POST.get("content_number")
        content_title = request.POST.get("content_title", "").strip()
        content_text = request.POST.get("content_text", "").strip()
        voice_id = request.POST.get("voice_id", "").strip()
        language_code = request.POST.get("language_code", "ko").strip()
        speed_value = request.POST.get("speed_value")
        style_value = request.POST.get("style_value")
        similarity_value = request.POST.get("similarity_value")

        # 각 페이지의 텍스트 정보 수집
        pages_text = []
        page_index = 0
        while True:
            page_text = request.POST.get(f'page_text_{page_index}')
            if page_text is None:
                break
            pages_text.append(page_text)
            page_index += 1

        # page_text_N이 비어있을 경우 content_text 단락에서 복원 (동시 대화 등)
        import re as _re
        content_paragraphs = [_re.sub(r'\[[^\]]*\]', '', p).strip()
                               for p in content_text.split('\n\n---\n\n')] if content_text else []
        for i in range(len(pages_text)):
            if not pages_text[i].strip() and i < len(content_paragraphs) and content_paragraphs[i]:
                pages_text[i] = content_paragraphs[i]
                print(f"  ℹ️ page_text_{i} 비어있어 content_text 단락으로 복원: {content_paragraphs[i][:40]}")

        if not all([content_number, content_title, content_text]):
            return JsonResponse({
                "success": False,
                "error": "모든 필드를 입력해주세요."
            }, status=400)

        try:
            # 에피소드 생성
            content = Content.objects.create(
                book=book,
                title=content_title,
                number=int(content_number),
                text=content_text
            )

            # 🔥 에피소드 이미지 저장
            episode_image = request.FILES.get('episode_image')
            if episode_image:
                try:
                    validate_image_file(episode_image)
                    content.episode_image = episode_image
                except ValidationError as e:
                    return JsonResponse({'success': False, 'error': f'이미지 검증 실패: {str(e)}'}, status=400)
                content.save()
                print(f"📷 에피소드 이미지 저장 완료: {content.episode_image.url}")

            from book.utils import merge_audio_files, generate_tts, mix_audio_with_background
            from django.core.files import File
            import tempfile

            # 🔥 미리듣기에서 생성된 최종 merge된 오디오가 있는지 확인
            merged_audio_file = request.FILES.get('merged_audio')

            if merged_audio_file:
                try:
                    validate_audio_file(merged_audio_file)
                except ValidationError as e:
                    return JsonResponse({'success': False, 'error': f'오디오 검증 실패: {str(e)}'}, status=400)
                # ✅ 미리듣기에서 이미 merge된 오디오 사용 (배경음 포함)
                print('🎵 미리듣기에서 생성된 최종 merge 오디오 사용 (배경음 포함)')
                print(f'📎 파일 크기: {merged_audio_file.size / 1024 / 1024:.2f} MB')

                # 임시 파일로 저장
                temp_path = os.path.join(settings.MEDIA_ROOT, 'audio', f'merged_{uuid4().hex}.mp3')
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)

                with open(temp_path, 'wb') as f:
                    for chunk in merged_audio_file.chunks():
                        f.write(chunk)

                # Content에 바로 저장
                with open(temp_path, 'rb') as audio_file:
                    content.audio_file.save(
                        os.path.basename(temp_path),
                        File(audio_file),
                        save=True
                    )
                print(f"💾 최종 오디오 파일 저장 완료: {content.audio_file.url}")

                # 오디오 길이 계산 (pydub 사용)
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_file(temp_path)
                total_duration_ms = len(audio_segment)
                content.duration_seconds = int(total_duration_ms / 1000)

                # 🔥 타임스탬프: 미리듣기에서 생성된 정확한 값 우선 사용
                merged_timestamps_json = request.POST.get('merged_timestamps')
                if merged_timestamps_json:
                    try:
                        dialogue_durations = json.loads(merged_timestamps_json)
                        content.audio_timestamps = dialogue_durations
                        print(f"⏱️ 미리듣기 타임스탬프 {len(dialogue_durations)}개 사용 (정확)")
                    except Exception as ts_err:
                        print(f"⚠️ 타임스탬프 파싱 실패: {ts_err}")
                        dialogue_durations = []
                else:
                    # fallback: 균등 분할 (미리듣기 없이 발행한 경우)
                    page_count = sum(1 for pt in pages_text if pt.strip())
                    print(f"📝 타임스탬프 균등 생성: {page_count}개 대사")
                    if page_count > 0:
                        dialogue_durations = []
                        segment_duration = total_duration_ms / page_count
                        dialogue_index = 0
                        for page_text in pages_text:
                            if page_text.strip():
                                start_time = int(dialogue_index * segment_duration)
                                end_time = int((dialogue_index + 1) * segment_duration)
                                dialogue_durations.append({
                                    'pageIndex': dialogue_index,
                                    'startTime': start_time,
                                    'endTime': end_time,
                                    'text': page_text
                                })
                                dialogue_index += 1
                        content.audio_timestamps = dialogue_durations
                        print(f"⏱️ {len(dialogue_durations)}개 대사의 타임스탬프 생성 완료 (균등 분할)")

                content.save()
                print(f"⏱️ 총 길이: {content.duration_seconds}초")

                # 임시 파일 삭제
                os.remove(temp_path)
                print("🗑️ 임시 파일 삭제 완료")
                print("✅ 미리듣기 오디오를 사용하여 빠르게 발행 완료!")

            else:
                # ⚠️ 미리듣기를 하지 않은 경우 - 기존 방식으로 merge 수행
                print("⚠️ 미리듣기 오디오가 없음 - 개별 파일 merge 수행")

                # 업로드된 오디오 파일들 수집 (페이지 인덱스 순서 유지)
                audio_items = []
                for key in request.FILES.keys():
                    if key.startswith('audio_'):
                        suffix = key[len('audio_'):]
                        if suffix.isdigit():
                            audio_items.append((int(suffix), request.FILES[key]))
                            print(f"📎 오디오 파일 수신: {key}")
                audio_items.sort(key=lambda x: x[0])
                audio_files = [f for _, f in audio_items]
                # 페이지 인덱스에 맞는 텍스트 정렬 (인덱스 불일치 방지)
                aligned_pages_text = [pages_text[idx] if idx < len(pages_text) else '' for idx, _ in audio_items]

                # 배경음 정보 수집
                background_tracks_count = int(request.POST.get('background_tracks_count', 0))
                background_tracks = []
                print(f"🎼 배경음 트랙 개수: {background_tracks_count}")

                # 오디오 파일이 있으면 합치기, 없으면 TTS 생성
                if audio_files:
                    print(f"🎵 {len(audio_files)}개의 오디오 파일 합치기 시작...")

                    # merge_audio_files는 이제 타임스탬프 정보도 함께 반환
                    merged_audio_path, dialogue_durations = merge_audio_files(audio_files, aligned_pages_text)

                    if merged_audio_path and dialogue_durations and os.path.exists(merged_audio_path):
                        print(f"✅ 오디오 합치기 완료: {merged_audio_path}")
                        print(f"⏱️ 타임스탬프 {len(dialogue_durations)}개 생성 완료")

                        # 배경음 처리
                        if background_tracks_count > 0:
                            print(f"🎼 배경음 {background_tracks_count}개 처리 시작...")

                            # 배경음 파일과 정보 수집
                            import math
                            for i in range(background_tracks_count):
                                bg_audio_key = f'background_audio_{i}'
                                if bg_audio_key in request.FILES:
                                    bg_file = request.FILES[bg_audio_key]
                                    start_page = int(request.POST.get(f'background_start_{i}', 0))
                                    end_page = int(request.POST.get(f'background_end_{i}', 0))
                                    music_name = request.POST.get(f'background_name_{i}', '')

                                    # 배경음 볼륨 (0-1 범위) → dB로 변환
                                    volume_linear = float(request.POST.get(f'background_volume_{i}', 1))
                                    print(f"   📊 받은 볼륨 값 (0-1): {volume_linear}")
                                    if volume_linear > 0:
                                        volume_db = 20 * math.log10(volume_linear)
                                    else:
                                        volume_db = -60  # 거의 무음
                                    print(f"   📊 변환된 dB 값: {volume_db:.1f}dB")

                                    # 배경음 파일을 임시 파일로 저장
                                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_bg:
                                        for chunk in bg_file.chunks():
                                            temp_bg.write(chunk)
                                        temp_bg_path = temp_bg.name

                                    # 시작/종료 시간 계산 (ms 단위)
                                    start_time = dialogue_durations[start_page]['startTime'] if start_page < len(dialogue_durations) else 0
                                    end_time = dialogue_durations[end_page]['endTime'] if end_page < len(dialogue_durations) else dialogue_durations[-1]['endTime']

                                    background_tracks.append({
                                        'audioPath': temp_bg_path,
                                        'startTime': start_time,
                                        'endTime': end_time,
                                        'volume': volume_db,  # 배경음 볼륨 (dB 단위)
                                        'name': music_name
                                    })
                                    print(f"   🎵 배경음 {i+1}: {music_name} ({start_time}ms ~ {end_time}ms), 볼륨: {volume_db:.1f}dB")

                            # 배경음 믹싱
                            if background_tracks:
                                mixed_audio_path = mix_audio_with_background(merged_audio_path, background_tracks)

                                # 임시 배경음 파일들 삭제
                                for track in background_tracks:
                                    if os.path.exists(track['audioPath']):
                                        os.remove(track['audioPath'])

                                # 원본 대사 오디오 삭제 (믹싱된 버전 사용)
                                if mixed_audio_path != merged_audio_path and os.path.exists(merged_audio_path):
                                    os.remove(merged_audio_path)

                                merged_audio_path = mixed_audio_path

                        # 최종 오디오 저장
                        with open(merged_audio_path, 'rb') as audio_file:
                            content.audio_file.save(
                                os.path.basename(merged_audio_path),
                                File(audio_file),
                                save=True
                            )
                        print(f"💾 합쳐진 오디오 파일 저장 완료: {content.audio_file.url}")

                        # 타임스탬프 정보와 총 길이 저장
                        content.audio_timestamps = dialogue_durations
                        # 총 오디오 길이 계산 (마지막 대사의 종료 시간을 초 단위로 변환)
                        if dialogue_durations:
                            content.duration_seconds = int(dialogue_durations[-1]['endTime'] / 1000)
                        content.save()
                        print(f"⏱️ {len(dialogue_durations)}개 대사의 타임스탬프 저장 완료")
                        print(f"⏱️ 총 길이: {content.duration_seconds}초")

                        # 임시 파일 삭제
                        os.remove(merged_audio_path)
                        print("🗑️ 임시 파일 삭제 완료")
                    else:
                        print("⚠️ 오디오 합치기 실패 - 대체로 TTS 생성")
                        audio_path = generate_tts(content_text, voice_id, language_code, speed_value,similarity_value,style_value)
                        if audio_path and os.path.exists(audio_path):
                            with open(audio_path, 'rb') as audio_file:
                                content.audio_file.save(
                                    os.path.basename(audio_path),
                                    File(audio_file),
                                    save=True
                                )
                            os.remove(audio_path)
                else:
                    # 오디오 파일이 없으면 전체 텍스트로 TTS 생성
                    print("🎵 TTS 생성 시작...")
                    audio_path = generate_tts(content_text, voice_id, language_code, speed_value,similarity_value,style_value)
                    if audio_path and os.path.exists(audio_path):
                        print(f"✅ TTS 생성 완료: {audio_path}")
                        with open(audio_path, 'rb') as audio_file:
                            content.audio_file.save(
                                os.path.basename(audio_path),
                                File(audio_file),
                                save=True
                            )
                        print(f"💾 오디오 파일 저장 완료: {content.audio_file.url}")
                        # 임시 파일 삭제
                        os.remove(audio_path)
                        print("🗑️ 임시 파일 삭제 완료")
                    else:
                        print("⚠️ TTS 생성 실패 - 에피소드는 저장되었지만 오디오는 없음")

            return JsonResponse({
                "success": True,
                "message": "에피소드가 성공적으로 저장되었습니다.",
                "content_id": content.id,
                "redirect_url": f"/book/detail/{book.public_uuid}/"
            })
        except Exception as e:
            print(f"❌ 에피소드 저장 오류: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                "success": False,
                "error": f"에피소드 저장 중 오류가 발생했습니다: {str(e)}"
            }, status=500)

    # 최신 에피소드 번호 가져오기 (삭제되지 않은 것만)
    latest_episode = Content.objects.filter(book=book, is_deleted=False).order_by('-number').first()
    latest_episode_number = latest_episode.number if latest_episode else 0

    # 음성 목록 가져오기
    voice_list = MyVoiceList.objects.filter(user=request.user)

    if book:
        voice_list = voice_list.filter(book=book)  # 선택한 책 기준 필터링

    voice_list = voice_list.order_by('-is_favorite', '-created_at')
    context = {
        "book": book,
        "latest_episode_number": latest_episode_number,
        "voice_list": voice_list,
        "guide_list": audioBookGuide,
            }
    return render(request, "book/book_serialization.html", context)


# tts 생성 ajax
import json
from book.utils import generate_tts
from django.http import HttpResponse, JsonResponse

def generate_tts_api(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 가능합니다."}, status=405)

    try:
        data = json.loads(request.body)
        text = data.get("text")
        voice_id = data.get("voice_id", "2EiwWnXFnvU5JabPnv8n")
        language_code = data.get("language_code", "ko")
        speed_value = data.get("speed_value", 1)
        style_value = float(data.get("style_value", 0.5))
        similarity_value = float(data.get("similarity_value", 1.0))
        # speed_value는 숫자로 변환
        try:
            speed_value = float(speed_value)
        except:
            speed_value = 1

        try:
            speed_value = float(speed_value)
        except ValueError:
            speed_value = 1.0

        if isinstance(text, dict):
            text = text.get("content", "")
        elif not isinstance(text, str):
            text = str(text)

        text = text.strip()
        if not text:
            return JsonResponse({"success": False, "error": "텍스트가 없습니다."}, status=400)

        # 🔥 여기 speed_value 추가
        audio_path = generate_tts(text, voice_id, language_code, speed_value, style_value, similarity_value)
        if not audio_path:
            return JsonResponse({"success": False, "error": "TTS 생성 실패"}, status=500)

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        return HttpResponse(audio_data, content_type="audio/mpeg")

    except Exception as e:
        print("❌ 오류:", e)
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ==================== 2인 대화 TTS 생성 ====================
def duet_tts_generate(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 가능합니다."}, status=405)
    try:
        import os
        data = json.loads(request.body)
        mode = data.get("mode", "alternate")

        # N명 배열 형식: {"voices": [{"voice_id":..., "text":...}, ...], "mode":...}
        # 구버전 2인 형식: {"text1":..., "voice_id1":..., "text2":..., "voice_id2":...}
        voices_raw = data.get("voices")
        if voices_raw:
            voice_list_input = [(v.get("voice_id", ""), v.get("text", "").strip()) for v in voices_raw]
        else:
            text1 = data.get("text1", "").strip()
            voice_id1 = data.get("voice_id1", "")
            text2 = data.get("text2", "").strip()
            voice_id2 = data.get("voice_id2", "")
            voice_list_input = [(voice_id1, text1), (voice_id2, text2)]

        if len(voice_list_input) < 2:
            return JsonResponse({"success": False, "error": "최소 2명의 목소리가 필요합니다."}, status=400)
        for vid, txt in voice_list_input:
            if not txt or not vid:
                return JsonResponse({"success": False, "error": "모든 목소리와 텍스트를 입력하세요."}, status=400)

        from book.utils import generate_tts, merge_duet_audio
        paths = []
        for vid, txt in voice_list_input:
            p = generate_tts(txt, vid, "ko", 1.0, 0.0, 0.75)
            if p:
                paths.append(p)

        if len(paths) < 2:
            return JsonResponse({"success": False, "error": "TTS 생성 실패"}, status=500)

        merged_path = merge_duet_audio(paths, mode=mode)

        for p in paths:
            try:
                if p and os.path.exists(p): os.remove(p)
            except: pass

        if not merged_path or not os.path.exists(merged_path):
            return JsonResponse({"success": False, "error": "듀엣 병합 실패"}, status=500)

        with open(merged_path, "rb") as f:
            audio_data = f.read()
        os.remove(merged_path)

        return HttpResponse(audio_data, content_type="audio/mpeg")

    except Exception as e:
        print("❌ 듀엣 TTS 오류:", e)
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# 사운드 이팩트 생성 API
def generate_sound_effect_api(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 가능합니다."}, status=405)

    try:
        from book.models import SoundEffectLibrary
        from django.core.files import File
        from book.utils import sound_effect
        import tempfile

        data = json.loads(request.body)
        effect_name = data.get("effect_name", "").strip()
        effect_description = data.get("effect_description", "").strip()
        duration_seconds = int(data.get("duration_seconds", 5))  # 기본값 5초
        save_to_library = data.get("save_to_library", True)  # 기본적으로 라이브러리에 저장

        if not effect_name or not effect_description:
            return JsonResponse({"success": False, "error": "이팩트 이름과 설명을 입력해주세요."}, status=400)

        print(f"🎵 사운드 이팩트 생성 요청: {effect_name} - {effect_description} ({duration_seconds}초)")

        # 사운드 이팩트 생성 (utils.sound_effect는 파일 경로를 반환)
        audio_path = sound_effect(effect_name, effect_description, duration_seconds)

        if not audio_path:
            return JsonResponse({"success": False, "error": "사운드 이팩트 생성에 실패했습니다."}, status=500)

        print(f"✅ 사운드 이팩트 생성 완료: {audio_path}")

        # 라이브러리에 저장
        if save_to_library and request.user.is_authenticated:
            with open(audio_path, 'rb') as f:
                effect = SoundEffectLibrary.objects.create(
                    effect_name=effect_name,
                    effect_description=effect_description,
                    user=request.user
                )
                effect.audio_file.save(f"effect_{effect.id}.mp3", File(f), save=True)
            print(f"💾 사운드 이팩트 라이브러리에 저장 완료: {effect.id}")

        # 파일 읽어서 반환
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        return HttpResponse(audio_data, content_type="audio/mpeg")

    except Exception as e:
        print("❌ 사운드 이팩트 생성 오류:", e)
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# 배경음 생성 API
def generate_background_music_api(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 가능합니다."}, status=405)

    try:
        from book.models import BackgroundMusicLibrary
        from django.core.files import File
        from book.utils import background_music
        import tempfile

        data = json.loads(request.body)
        music_name = data.get("music_name", "").strip()
        music_description = data.get("music_description", "").strip()
        duration_seconds = int(data.get("duration_seconds", 30))
        save_to_library = data.get("save_to_library", True)

        if not music_name or not music_description:
            return JsonResponse({"success": False, "error": "배경음 이름과 설명을 입력해주세요."}, status=400)

        print(f"🎵 배경음 생성 요청: {music_name} - {music_description} ({duration_seconds}초)")

        # 배경음 생성 (utils.background_music는 파일 경로를 반환)
        audio_path = background_music(music_name, music_description, duration_seconds)

        if not audio_path:
            return JsonResponse({"success": False, "error": "배경음 생성에 실패했습니다."}, status=500)

        print(f"✅ 배경음 생성 완료: {audio_path}")

        # 라이브러리에 저장
        if save_to_library and request.user.is_authenticated:
            with open(audio_path, 'rb') as f:
                music = BackgroundMusicLibrary.objects.create(
                    music_name=music_name,
                    music_description=music_description,
                    duration_seconds=duration_seconds,
                    user=request.user
                )
                music.audio_file.save(f"music_{music.id}.mp3", File(f), save=True)
            print(f"💾 배경음 라이브러리에 저장 완료: {music.id}")

        # 파일 읽어서 반환
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        return HttpResponse(audio_data, content_type="audio/mpeg")

    except Exception as e:
        print("❌ 배경음 생성 오류:", e)
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# 사운드 이팩트 라이브러리 조회 API
def get_sound_effects_library(request):
    from book.models import SoundEffectLibrary

    try:
        if request.user.is_authenticated:
            effects = SoundEffectLibrary.objects.filter(user=request.user)
        else:
            effects = SoundEffectLibrary.objects.none()

        effects_data = [{
            'id': effect.id,
            'effect_name': effect.effect_name,
            'effect_description': effect.effect_description,
            'audio_url': effect.audio_file.url if effect.audio_file else None,
            'created_at': effect.created_at.strftime('%Y-%m-%d %H:%M')
        } for effect in effects]

        return JsonResponse({'success': True, 'effects': effects_data})
    except Exception as e:
        print("❌ 사운드 이팩트 라이브러리 조회 오류:", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# 배경음 라이브러리 조회 API
def get_background_music_library(request):
    from book.models import BackgroundMusicLibrary

    try:
        if request.user.is_authenticated:
            music_list = BackgroundMusicLibrary.objects.filter(user=request.user)
        else:
            music_list = BackgroundMusicLibrary.objects.none()

        music_data = [{
            'id': music.id,
            'music_name': music.music_name,
            'music_description': music.music_description,
            'duration_seconds': music.duration_seconds,
            'audio_url': music.audio_file.url if music.audio_file else None,
            'created_at': music.created_at.strftime('%Y-%m-%d %H:%M')
        } for music in music_list]

        return JsonResponse({'success': True, 'music': music_data})
    except Exception as e:
        print("❌ 배경음 라이브러리 조회 오류:", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

from register.models import Users

# 책 상세보기
def book_detail(request, book_uuid):
    from book.models import BookReview, BookComment, ReadingProgress, AuthorAnnouncement
    from django.db.models import Avg, Prefetch
    from django.core.paginator import Paginator

    # ✅ 쿼리 최적화: select_related, prefetch_related 적용 (삭제된 에피소드 제외)
    book = get_object_or_404(
        Books.objects.select_related('user').prefetch_related(
            'genres',
            'tags',
            Prefetch('contents', queryset=Content.objects.filter(is_deleted=False).order_by('-number'))
        ),
        public_uuid=book_uuid
    )

    is_adult_content = book.adult_choice
    is_authorized = request.user.is_authenticated and request.user.is_adult()
    show_blur = is_adult_content and not is_authorized

    # 컨텐츠 가져오기 (삭제되지 않은 것만)
    contents = book.contents.filter(is_deleted=False).order_by('-number')

    paginator = Paginator(contents, 10)
    page = request.GET.get('page')
    contents_page = paginator.get_page(page)

    # 1화 가져오기 (미리듣기용)
    first_episode = Content.objects.filter(book=book, number=1, is_deleted=False).first()

    avg_rating = book.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = book.reviews.count()

    user_review = None
    reading_progress = None
    if request.user.is_authenticated:
        user_review = BookReview.objects.filter(user=request.user, book=book).first()
        reading_progress = ReadingProgress.objects.filter(user=request.user, book=book).first()

    recent_reviews = book.reviews.select_related('user').order_by('-created_at')[:5]
    comments = book.book_comments.filter(parent=None).select_related('user').prefetch_related('replies__user').order_by('-created_at')
    announcements = book.announcements.select_related('author').order_by('-is_pinned', '-created_at')

        # ------------------------------
        # 📌 성별 통계 (Users 테이블에서 직접 조회)
        # ------------------------------
    book_stats = []
    book_stats_json = []
    readers = ReadingProgress.objects.filter(book=book)
    reader_count = readers.values('user').distinct().count()
    # ReadingProgress에서 user_id만 추출
    reader_user_ids = readers.values_list('user_id', flat=True).distinct()

    # Users 테이블에서 성별 통계 직접 조회 (user_id 사용)
    gender_stats = Users.objects.filter(user_id__in=reader_user_ids).values('gender').annotate(count=Count('user_id'))
    gender_data = {'M': 0, 'F': 0, 'O': 0}
    for g in gender_stats:
        key = g['gender'] or 'O'
        gender_data[key] = g['count']

    # ------------------------------
    # 📌 연령대 통계 (Users 테이블에서 직접 조회)
    # ------------------------------
    # Users 테이블에서 age 직접 조회 (user_id 사용)
    ages = Users.objects.filter(
        user_id__in=reader_user_ids,
        age__gt=0  # age가 0보다 큰 것만
    ).values_list('age', flat=True)
    # 디버깅: 연령대 데이터 확인
    print(f"📊 [{book.name}] 독자 수: {reader_count}")
    print(f"📊 [{book.name}] 독자 user_id 목록: {list(reader_user_ids)[:10]}...")
    print(f"📊 [{book.name}] 조회된 나이 데이터: {list(ages)}")

    age_data = {
        "어린이":0,
        "10대": 0,
        "20대": 0,
        "30대": 0,
        "40대": 0,
        "50대 이상": 0,
    }

    for age in ages:
        if age <10:
            age_data["어린이"] +=1
        if 10 <= age < 20:
            age_data["10대"] += 1
        elif 20 <= age < 30:
            age_data["20대"] += 1
        elif 30 <= age < 40:
            age_data["30대"] += 1
        elif 40 <= age < 50:
            age_data["40대"] += 1
        elif age >= 50:
            age_data["50대 이상"] += 1

    print(f"📊 [{book.name}] 연령대 분포: {age_data}")

    book_stats.append({
        "book": book,
        "gender_data": gender_data,
        "age_data": age_data,

        "book_duration": book.get_total_duration_formatted(),
    })


    # JS에서 쓰기 위한 JSON
    book_stats_json.append({
        "book_id": book.id,
        "book_name": book.name,
        "gender_data": gender_data,
        "age_data": age_data,

    })
    print ("책 상태:",book_stats_json)
    context = {
        "book": book,
        "contents": contents_page,
        "first_episode": first_episode,
        "avg_rating": round(avg_rating, 1),
        "review_count": review_count,
        "user_review": user_review,
        "recent_reviews": recent_reviews,
        "comments": comments,
        "reading_progress": reading_progress,
        "announcements": announcements,
        "show_blur":show_blur,
        "book_stats": book_stats,
        "book_stats_json": json.dumps(book_stats_json),
    }

    return render(request, "book/book_detail.html", context)


# ==================== 웹소설 전용 뷰 ====================

def webnovel_detail(request, book_uuid):
    from book.models import BookReview, BookComment, ReadingProgress, AuthorAnnouncement, BookmarkBook
    from django.db.models import Avg, Count
    from register.models import Users

    book = get_object_or_404(
        Books.objects.select_related('user').prefetch_related('genres', 'tags'),
        public_uuid=book_uuid,
        book_type='webnovel'
    )

    contents = Content.objects.filter(book=book, is_deleted=False).order_by('number')

    avg_rating = book.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = book.reviews.count()
    user_review = None
    reading_progress = None
    is_bookmarked = False
    if request.user.is_authenticated:
        user_review = BookReview.objects.filter(user=request.user, book=book).first()
        reading_progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
        is_bookmarked = BookmarkBook.objects.filter(user=request.user, book=book).exists()

    recent_reviews = book.reviews.select_related('user').order_by('-created_at')[:5]
    comments = book.book_comments.filter(parent=None).select_related('user').prefetch_related('replies__user').order_by('-created_at')
    announcements = AuthorAnnouncement.objects.filter(book=book).select_related('author').order_by('-is_pinned', '-created_at')

    # 독자 통계
    readers = ReadingProgress.objects.filter(book=book)
    reader_count = readers.values('user').distinct().count()
    reader_user_ids = readers.values_list('user_id', flat=True).distinct()
    gender_stats = Users.objects.filter(user_id__in=reader_user_ids).values('gender').annotate(count=Count('user_id'))
    gender_data = {'M': 0, 'F': 0, 'O': 0}
    for g in gender_stats:
        gender_data[g['gender'] or 'O'] = g['count']

    ages = Users.objects.filter(user_id__in=reader_user_ids, age__gt=0).values_list('age', flat=True)
    age_data = {"10대": 0, "20대": 0, "30대": 0, "40대": 0, "50대 이상": 0}
    for age in ages:
        if 10 <= age < 20: age_data["10대"] += 1
        elif 20 <= age < 30: age_data["20대"] += 1
        elif 30 <= age < 40: age_data["30대"] += 1
        elif 40 <= age < 50: age_data["40대"] += 1
        elif age >= 50: age_data["50대 이상"] += 1

    context = {
        "book": book,
        "contents": contents,
        "avg_rating": round(avg_rating, 1),
        "review_count": review_count,
        "user_review": user_review,
        "recent_reviews": recent_reviews,
        "comments": comments,
        "reading_progress": reading_progress,
        "announcements": announcements,
        "reader_count": reader_count,
        "gender_data": gender_data,
        "age_data": age_data,
        "is_bookmarked": is_bookmarked,
    }
    return render(request, "book/webnovel_detail.html", context)


def webnovel_upload_cover(request, book_uuid):
    """관리자 전용: 웹소설 표지 이미지 업로드"""
    from django.contrib.auth.decorators import login_required
    from django.http import HttpResponseForbidden
    if not request.user.is_staff:
        return HttpResponseForbidden()
    if request.method != 'POST':
        from django.shortcuts import redirect
        return redirect('book:webnovel_detail', book_uuid=book_uuid)
    book = get_object_or_404(Books, public_uuid=book_uuid)
    img = request.FILES.get('cover_img')
    if img:
        book.cover_img = img
        book.save(update_fields=['cover_img'])
    from django.contrib import messages
    messages.success(request, '표지가 업데이트되었습니다.')
    from django.shortcuts import redirect
    return redirect('book:webnovel_detail', book_uuid=book_uuid)


def webnovel_episode(request, content_uuid):
    import re
    from book.models import Content, ReadingProgress
    from django.utils import timezone

    content = get_object_or_404(Content, public_uuid=content_uuid, is_deleted=False)
    book = content.book

    if book.book_type != 'webnovel':
        from django.shortcuts import redirect
        return redirect('book:content_detail', content_uuid=content_uuid)

    prev_content = Content.objects.filter(book=book, number__lt=content.number, is_deleted=False).order_by('-number').first()
    next_content = Content.objects.filter(book=book, number__gt=content.number, is_deleted=False).order_by('number').first()

    # 감정 태그 제거 후 단락 분리
    raw_text = content.text or ''
    clean_text = re.sub(r'\[[^\]]+\]', '', raw_text).strip()
    paragraphs = [p.strip() for p in clean_text.split('\n') if p.strip()]

    if request.user.is_authenticated:
        progress, _ = ReadingProgress.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={'status': 'reading', 'last_read_content_number': content.number, 'current_content': content}
        )
        if content.number >= progress.last_read_content_number:
            progress.last_read_content_number = content.number
            progress.current_content = content
            progress.last_read_at = timezone.now()
            total = book.contents.filter(is_deleted=False).count()
            progress.status = 'completed' if content.number >= total else 'reading'
            progress.save()

    context = {
        "content": content,
        "book": book,
        "paragraphs": paragraphs,
        "prev_content": prev_content,
        "next_content": next_content,
    }
    return render(request, "book/webnovel_episode.html", context)


# 내 작품 관리
@login_required
@login_required_to_main
def my_books(request):
    # ✅ 쿼리 최적화: prefetch_related 적용
    books = Books.objects.filter(user=request.user, is_deleted=False).prefetch_related(
        'genres',
        'tags'
    ).order_by('-created_at')

    context = {
        "books": books,
    }
    return render(request, "book/my_books.html", context)


# 책 소프트 삭제 (DB에는 보존)
@login_required
@require_POST
@login_required_to_main
def delete_book(request, book_uuid):
    from django.utils import timezone as tz
    book = get_object_or_404(Books, public_uuid=book_uuid, user=request.user, is_deleted=False)
    if book.user != request.user:
        return JsonResponse({"success": False, "error": "권한 없음"}, status=403)
    book.is_deleted = True
    book.deleted_at = tz.now()
    book.save(update_fields=['is_deleted', 'deleted_at'])
    return JsonResponse({"success": True})

def content_detail(request, content_uuid):
    from book.models import Content, ReadingProgress, ListeningHistory, AuthorAnnouncement
    from advertisment.models import UserAdCounter, Advertisement
    from django.utils import timezone

    content = get_object_or_404(Content, public_uuid=content_uuid, is_deleted=False)
    book = content.book

    prev_content = Content.objects.filter(book=book, number__lt=content.number, is_deleted=False).order_by('-number').first()
    next_content = Content.objects.filter(book=book, number__gt=content.number, is_deleted=False).order_by('number').first()

    last_position = 0
    if request.user.is_authenticated:
        listening_history = ListeningHistory.objects.filter(
            user=request.user,
            content=content
        ).first()
        if listening_history:
            last_position = listening_history.last_position

    announcements = AuthorAnnouncement.objects.filter(book=book).select_related('author')[:3]

    if request.user.is_authenticated:
        progress, created = ReadingProgress.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={
                'status': 'reading',
                'last_read_content_number': content.number,
                'current_content': content,
            }
        )
        if content.number >= progress.last_read_content_number:
            progress.last_read_content_number = content.number
            progress.current_content = content
            progress.last_read_at = timezone.now()

            total_contents = book.contents.filter(is_deleted=False).count()
            if content.number >= total_contents:
                progress.status = 'completed'
                progress.completed_at = timezone.now()
            else:
                progress.status = 'reading'
            progress.save()

        # ── 광고 카운터 체크 ──────────────────────────────
        skip_count = request.GET.get('skip_count')
        
        # 🔍 디버그
        print(f"\n{'='*50}")
        print(f"[content_detail] {content.number}화 진입")
        print(f"[content_detail] skip_count 파라미터: {repr(skip_count)}")
        print(f"[content_detail] 전체 URL: {request.get_full_path()}")

        if not skip_count:
            counter, _ = UserAdCounter.objects.get_or_create(user=request.user)
            print(f"[content_detail] 카운터 증가 전: {counter.episode_play_count}")
            counter.episode_play_count += 1
            counter.save()
            print(f"[content_detail] 카운터 증가 후: {counter.episode_play_count}")

            if counter.episode_play_count % 3 == 0:
                ad = Advertisement.objects.filter(
                    placement='episode',
                    ad_type='audio',
                    is_active=True,
                ).order_by('?').first()

                if ad:
                    next_uuid = content.public_uuid if content  else None
                    redirect_url = reverse('book:ad_audio', kwargs={'uuid': ad.public_uuid})
                    if next_uuid:
                        redirect_url += f'?next={next_uuid}'
                    return redirect(redirect_url)
        else:
            print(f"[content_detail] skip_count 있음 → 카운터 증가 안 함")
        print(f"{'='*50}\n")
        # ────────────────────────────────────────────────

    context = {
        "content": content,
        "book": book,
        "prev_content": prev_content,
        "next_content": next_content,
        "last_position": last_position,
        "announcements": announcements,
    }
    return render(request, "book/content_detail.html", context)

# 청취 시간 기록
@login_required
@require_POST
def save_listening_history(request, content_uuid):
    from book.models import Content, ListeningHistory
    from django.utils import timezone
    import json

    try:
        data = json.loads(request.body)
        listened_seconds = int(data.get('listened_seconds', 0))
        last_position = float(data.get('last_position', 0))

        # 청취 시간이 0이어도 재생 위치가 있으면 저장
        if listened_seconds <= 0 and last_position <= 0:
            return JsonResponse({'success': False, 'error': '청취 시간 또는 재생 위치가 필요합니다.'})

        content = get_object_or_404(Content, public_uuid=content_uuid)
        book = content.book

        # 청취 기록 생성 또는 업데이트
        listening_history, created = ListeningHistory.objects.get_or_create(
            user=request.user,
            book = content.book,
            content=content,
            defaults={
                'listened_seconds': max(listened_seconds, 0),
                'last_position': last_position,
                'last_listened_at': timezone.now()
            }
        )

        if not created:
            # 이미 존재하면 청취 시간 누적 및 재생 위치 업데이트
            if listened_seconds > 0:
                listening_history.listened_seconds += listened_seconds
            listening_history.last_position = last_position
            listening_history.last_listened_at = timezone.now()
            listening_history.save()

        return JsonResponse({
            'success': True,
            'message': '청취 시간이 기록되었습니다.',
            'total_seconds': listening_history.listened_seconds,
            'last_position': listening_history.last_position
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# 앱용 청취 위치 업데이트 API (api_key 인증)
# POST body에서 API key를 받으므로 @require_api_key_secure 사용 안 함
@require_POST
@csrf_exempt
def update_listening_position_api(request):
    from book.models import Content, ListeningHistory
    from register.models import Users
    from django.utils import timezone
    import json

    try:
        data = json.loads(request.body)
        # 헤더 우선, body 폴백 (Flutter는 헤더로 전송)
        api_key = request.headers.get('X-API-Key') or data.get('api_key')
        book_id = data.get('book_id') or data.get('public_uuid')  # Flutter는 'book_id'로 전송
        content_id = data.get('content_id')
        last_position = float(data.get('last_position', 0))
        listened_seconds = int(data.get('listened_seconds', 0))

        # API 키로 사용자 인증
        if not api_key:
            return JsonResponse({'success': False, 'error': 'API 키가 필요합니다.'}, status=401)

        try:
            api_key_obj = APIKey.objects.get(key=api_key, is_active=True)
            user = api_key_obj.user
        except APIKey.DoesNotExist:
            return JsonResponse({'success': False, 'error': '유효하지 않은 API 키입니다.'}, status=401)

        # Content 확인 (UUID 또는 정수 ID 모두 지원)
        try:
            # UUID로 먼저 시도
            from uuid import UUID
            content_uuid = UUID(str(content_id))
            content = get_object_or_404(Content, public_uuid=content_uuid)
        except (ValueError, AttributeError):
            # 정수 ID로 폴백
            content = get_object_or_404(Content, id=content_id)

        # Book 확인 (UUID 또는 정수 ID 모두 지원)
        try:
            from uuid import UUID as UUID2
            book_uuid = UUID2(str(book_id))
            book = get_object_or_404(Books, public_uuid=book_uuid)
        except (ValueError, AttributeError):
            book = get_object_or_404(Books, id=book_id)

        # 청취 기록 생성 또는 업데이트
        listening_history, created = ListeningHistory.objects.get_or_create(
            user=user,
            book=book,
            content=content,
            defaults={
                'listened_seconds': max(listened_seconds, 0),
                'last_position': last_position,
                'last_listened_at': timezone.now()
            }
        )

        if not created:
            # 이미 존재하면 청취 시간 누적 및 재생 위치 업데이트
            if listened_seconds > 0:
                listening_history.listened_seconds += listened_seconds
            listening_history.last_position = last_position
            listening_history.last_listened_at = timezone.now()
            listening_history.save()

        return JsonResponse({
            'success': True,
            'message': '청취 위치가 저장되었습니다.',
            'total_seconds': listening_history.listened_seconds,
            'last_position': listening_history.last_position
        })
    except Exception as e:
        print(f"❌ 청취 위치 업데이트 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# 책 리뷰 작성/수정
@login_required
@require_POST
def submit_review(request, book_uuid):
    from book.models import BookReview
    from django.db.models import Avg

    try:
        book = get_object_or_404(Books, public_uuid=book_uuid)
        rating = int(request.POST.get('rating', 5))
        review_text = request.POST.get('review_text', '').strip()

        print(f"📝 리뷰 제출: 사용자={request.user.nickname}, 책={book.name}, 평점={rating}")

        # 리뷰 생성 또는 업데이트
        review, created = BookReview.objects.update_or_create(
            user=request.user,
            book=book,
            defaults={'rating': rating, 'review_text': review_text}
        )

        print(f"✅ 리뷰 {'생성' if created else '수정'} 완료: ID={review.id}")

        # 책 평균 평점 업데이트
        avg_rating = book.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        book.book_score = round(avg_rating, 1)
        book.save()

        print(f"📊 평균 평점 업데이트: {book.book_score} (총 {book.reviews.count()}개 리뷰)")

        referer = request.META.get('HTTP_REFERER', '/')
        return redirect(referer)
    except Exception as e:
        print(f"❌ 리뷰 제출 오류: {str(e)}")
        referer = request.META.get('HTTP_REFERER', '/')
        return redirect(referer)


# 책 댓글 작성
@login_required
@require_POST
def submit_book_comment(request, book_uuid):
    from book.models import BookComment

    book = get_object_or_404(Books, public_uuid=book_uuid)
    comment_text = (request.POST.get('content') or request.POST.get('comment', '')).strip()
    parent_id = request.POST.get('parent_id', None)

    referer = request.META.get('HTTP_REFERER', '/')
    if not comment_text:
        return redirect(referer)

    parent = None
    if parent_id:
        try:
            parent = BookComment.objects.get(id=parent_id)
        except BookComment.DoesNotExist:
            pass

    BookComment.objects.create(
        user=request.user,
        book=book,
        comment=comment_text,
        parent=parent
    )

    return redirect(referer)


# 미리듣기 페이지
@login_required_to_main
def preview_page(request):
    book_uuid = request.GET.get("public_uuid")
    book = get_object_or_404(Books, public_uuid=book_uuid) if book_uuid else None

    if not book:
        return redirect("book:book_profile")

    from book.models import Content
    latest_episode = Content.objects.filter(book=book, is_deleted=False).order_by('-number').first()
    latest_episode_number = latest_episode.number if latest_episode else 0

    # 🔥 이미지 업로드는 AJAX로 처리하므로 POST 처리 제거
    # 이미지는 IndexedDB에 저장되어 에피소드 발행 시 함께 전송됨

    context = {
        "book": book,
        "latest_episode_number": latest_episode_number,
    }
    return render(request, "book/preview.html", context)


# 미리듣기용 임시 오디오 생성
def generate_preview_audio(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 가능합니다."}, status=405)

    try:
        # 오디오 파일 수집
        audio_files = []
        for key in request.FILES.keys():
            if key.startswith('audio_'):
                audio_files.append(request.FILES[key])

        # 배경음 정보 수집
        background_tracks_count = int(request.POST.get('background_tracks_count', 0))
        background_tracks = []

        from book.utils import merge_audio_files, mix_audio_with_background
        from pydub import AudioSegment
        import tempfile

        if not audio_files:
            return JsonResponse({"success": False, "error": "오디오 파일이 없습니다."}, status=400)

        # 대사 오디오 합치기 (타임스탬프 정보도 함께 반환)
        merged_audio_path, dialogue_durations = merge_audio_files(audio_files)

        if not merged_audio_path or not os.path.exists(merged_audio_path):
            return JsonResponse({"success": False, "error": "오디오 합치기 실패"}, status=500)

        # 배경음 처리
        if background_tracks_count > 0 and dialogue_durations:

       # 배경음 파일 수집
            for i in range(background_tracks_count):
                bg_audio_key = f'background_audio_{i}'
                if bg_audio_key in request.FILES:
                    bg_file = request.FILES[bg_audio_key]
                    start_page = int(request.POST.get(f'background_start_{i}', 0))
                    end_page = int(request.POST.get(f'background_end_{i}', 0))
                    music_name = request.POST.get(f'background_name_{i}', '')

                    # 📌 프론트에서 보낸 volume(0~1)
                    volume_ratio = float(request.POST.get(f'background_volume_{i}', 1))

                    # 📌 dB 변환 (오디오 볼륨 조절은 dB 단위여야 함)
                    import math
                    volume_db = 20 * math.log10(volume_ratio) if volume_ratio > 0 else -60

                    # 임시 파일 저장
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_bg:
                        for chunk in bg_file.chunks():
                            temp_bg.write(chunk)
                        temp_bg_path = temp_bg.name

                    # 시작/종료 시간 계산 (간단한 방식: 이전 대사 끝 = 현재 대사 시작)
                    start_time = 0 if start_page == 0 else dialogue_durations[start_page - 1]['endTime']
                    end_time = dialogue_durations[end_page]['endTime'] if end_page < len(dialogue_durations) else dialogue_durations[-1]['endTime']

                    background_tracks.append({
                        'audioPath': temp_bg_path,
                        'startTime': start_time,
                        'endTime': end_time,
                        'volume': volume_db,  
                        'name': music_name
                    })


            # 배경음 믹싱
            if background_tracks:
                mixed_audio_path = mix_audio_with_background(merged_audio_path, background_tracks)

                # 임시 배경음 파일 삭제
                for track in background_tracks:
                    if os.path.exists(track['audioPath']):
                        os.remove(track['audioPath'])

                # 원본 대사 오디오 삭제
                if mixed_audio_path != merged_audio_path and os.path.exists(merged_audio_path):
                    os.remove(merged_audio_path)

                merged_audio_path = mixed_audio_path

        # 파일 읽어서 반환
        with open(merged_audio_path, "rb") as f:
            audio_data = f.read()

        # 임시 파일 삭제
        os.remove(merged_audio_path)

        return HttpResponse(audio_data, content_type="audio/mpeg")

    except Exception as e:
        print("❌ 미리듣기 오디오 생성 오류:", e)
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# 비동기 미리듣기 오디오 생성 (Celery 사용)
def generate_preview_audio_async(request):
    """
    미리듣기 오디오를 비동기로 생성 (Celery task 사용)
    - 100개 이상의 대사도 타임아웃 없이 처리 가능
    """
    # 디버깅용 로그 파일
    import datetime
    import os
    debug_log_path = os.path.join(settings.BASE_DIR, "debug_async.log")

    try:
        with open(debug_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{'='*50}\n")
            f.write(f"[{datetime.datetime.now()}] 요청 시작\n")
            f.write(f"Method: {request.method}\n")
            f.write(f"Content-Length: {request.META.get('CONTENT_LENGTH', 'N/A')}\n")
            f.write(f"Content-Type: {request.META.get('CONTENT_TYPE', 'N/A')}\n")
            f.write(f"FILES keys: {list(request.FILES.keys())[:5]}...\n")  # 처음 5개만
            f.write(f"POST keys: {list(request.POST.keys())[:10]}...\n")  # 처음 10개만
    except Exception as log_error:
        print(f"로그 작성 실패: {log_error}")

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 가능합니다."}, status=405)

    try:
        import tempfile
        from book.tasks import merge_audio_task

        # 오디오 파일 수집 및 임시 파일로 저장
        audio_file_paths = []
        temp_files = []

        # 오디오 파일을 숫자 순서대로 정렬 (audio_0, audio_1, audio_2, ...)
        audio_keys = [key for key in request.FILES.keys() if key.startswith('audio_')]
        audio_keys.sort(key=lambda x: int(x.split('_')[1]))

        for key in audio_keys:
            audio_file = request.FILES[key]

            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                for chunk in audio_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
                audio_file_paths.append(temp_file_path)
                temp_files.append(temp_file_path)

        if not audio_file_paths:
            return JsonResponse({"success": False, "error": "오디오 파일이 없습니다."}, status=400)

        # 페이지 텍스트 수집
        pages_text = []
        page_index = 0
        while f'page_text_{page_index}' in request.POST:
            pages_text.append(request.POST.get(f'page_text_{page_index}', ''))
            page_index += 1

        # 배경음 정보 수집
        background_tracks_count = int(request.POST.get('background_tracks_count', 0))
        background_tracks_data = []

        if background_tracks_count > 0:
            for i in range(background_tracks_count):
                bg_audio_key = f'background_audio_{i}'
                if bg_audio_key in request.FILES:
                    bg_file = request.FILES[bg_audio_key]

                    # 임시 파일로 저장
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_bg:
                        for chunk in bg_file.chunks():
                            temp_bg.write(chunk)
                        temp_bg_path = temp_bg.name

                    start_page = int(request.POST.get(f'background_start_{i}', 0))
                    end_page = int(request.POST.get(f'background_end_{i}', 0))
                    music_name = request.POST.get(f'background_name_{i}', '')
                    volume_ratio = float(request.POST.get(f'background_volume_{i}', 1))

                    # dB 변환
                    import math
                    volume_db = 20 * math.log10(volume_ratio) if volume_ratio > 0 else -60

                    background_tracks_data.append({
                        'audioPath': temp_bg_path,
                        'startPage': start_page,
                        'endPage': end_page,
                        'volume': volume_db,
                        'name': music_name
                    })

        # Celery task 실행
        task = merge_audio_task.apply_async(
            args=[audio_file_paths, background_tracks_data, pages_text]
        )

        return JsonResponse({
            "success": True,
            "task_id": task.id,
            "message": "오디오 병합 작업이 시작되었습니다."
        })

    except Exception as e:
        print("❌ 비동기 미리듣기 오디오 생성 오류:", e)
        import traceback
        traceback.print_exc()

        # 에러 로그 파일에도 기록
        try:
            with open(debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"❌ 에러 발생: {str(e)}\n")
                f.write(traceback.format_exc())
        except:
            pass

        return JsonResponse({"success": False, "error": str(e)}, status=500)


# Task 상태 확인 엔드포인트
def preview_task_status(request, task_id):
    """
    Celery task의 진행 상황을 확인
    """
    from celery.result import AsyncResult

    task = AsyncResult(task_id)

    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': '작업 대기 중...',
            'progress': 0
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'status': task.info.get('status', ''),
            'progress': task.info.get('progress', 0)
        }
    elif task.state == 'SUCCESS':
        result = task.result
        print(f"✅ Task 결과: {result}")

        if result and result.get('success'):
            # 파일 읽어서 반환
            merged_audio_path = result.get('merged_audio_path')
            print(f"📂 파일 경로: {merged_audio_path}")
            print(f"📂 파일 존재: {os.path.exists(merged_audio_path) if merged_audio_path else False}")

            if merged_audio_path and os.path.exists(merged_audio_path):
                with open(merged_audio_path, 'rb') as f:
                    audio_data = f.read()
                print(f"✅ 파일 크기: {len(audio_data)} bytes")

                # 임시 파일 삭제
                try:
                    os.remove(merged_audio_path)
                except Exception as e:
                    print(f"⚠️ 파일 삭제 실패: {e}")

                # 오디오 파일을 base64로 인코딩하여 전송
                import base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')

                response = {
                    'state': task.state,
                    'status': '완료!',
                    'progress': 100,
                    'audio_data': audio_base64,
                    'timestamps': result.get('timestamps', [])
                }
            else:
                print(f"❌ 파일 없음: {merged_audio_path}")
                response = {
                    'state': 'FAILURE',
                    'status': '오디오 파일을 찾을 수 없습니다.',
                    'error': f'파일 없음: {merged_audio_path}'
                }
        else:
            response = {
                'state': 'FAILURE',
                'status': result.get('error', '알 수 없는 오류'),
                'error': result.get('error')
            }
    else:
        # FAILURE 등 기타 상태
        response = {
            'state': task.state,
            'status': str(task.info),
            'error': str(task.info)
        }

    return JsonResponse(response)


# book/views.py

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import BookSnap, BookSnapComment
from django.core.paginator import Paginator
import random

# 북 스냅 리스트 페이지
@login_required_to_main
def book_snap_list(request):
    # 첫 번째 스냅으로 리디렉션 (유튜브 쇼츠 스타일)
    first_snap = BookSnap.objects.first()
    if first_snap:
        return redirect('book:book_snap_detail', snap_uuid=first_snap.public_uuid)

    # 스냅이 없으면 빈 페이지
    return render(request, "book/snap/snap_detail.html", {"no_snaps": True})

# 개인 북 스냅 리스트 페이지
@login_required_to_main
def my_book_snap_list(request):
    if not request.user.is_authenticated:
        return render(request, "book/snap/my_snap.html", {"error": "로그인이 필요합니다."})
    
    snap_list = BookSnap.objects.filter(user=request.user).order_by('-created_at')

    context = {
        "book_snap_list": snap_list,
    }

    return render(request, "book/snap/my_snap.html", context)

import re  # 정규식으로 id 추출
@login_required_to_main
def create_book_snap(request):
    if not request.user.is_authenticated:
        return render(request, "book/snap/create_snap.html", {"error": "로그인이 필요합니다."})

    user = request.user

    # ─────────────────────────────
    # 선택지 (GET/POST 공통)
    # ─────────────────────────────
    my_book_options = [
        (f"/book/detail/{book.public_uuid}/", book.name)
        for book in Books.objects.filter(user=user)
    ]

    my_story_options = [
        (f"/character/story/intro/{story.public_uuid}/", story.title)
        for story in Story.objects.filter(user=user)
    ]

    if request.method == "POST":
        snap_title       = request.POST.get("title", "").strip()
        snap_description = request.POST.get("description", "").strip()
        is_adult         = request.POST.get("adult_choice") == "on"
        thumbnail_image  = request.FILES.get("image")
        snap_video       = request.FILES.get("video")

        selected_book_url  = request.POST.get("selected_book_url", "").strip()
        selected_story_url = request.POST.get("selected_story_url", "").strip()
        custom_url         = request.POST.get("custom_url", "").strip()

        # 우선순위
        final_url = selected_book_url or selected_story_url or custom_url

        # ─────────────────────────────
        # 파일 검증
        # ─────────────────────────────
        try:
            if thumbnail_image:
                validate_image_file(thumbnail_image)
            if snap_video:
                validate_video_file(snap_video)
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        if not snap_title or not snap_description or not thumbnail_image:
            return render(request, "book/snap/create_snap.html", {
                "error": "제목, 설명, 썸네일은 필수입니다.",
                "my_book_options": my_book_options,
                "my_story_options": my_story_options,
            })

        # ─────────────────────────────
        # 🔥 핵심: 연결 대상 판별
        # ─────────────────────────────
        connected_book = None
        connected_story = None
        book_link = None
        story_link = None

        if final_url:
            book_match = re.search(r'/book/detail/([a-f0-9\-]+)/?$', final_url)
            story_match = re.search(r'/character/story/intro/([a-f0-9\-]+)/?$', final_url)

            if book_match:
                try:
                    connected_book = Books.objects.get(public_uuid=book_match.group(1))
                    book_link = final_url
                except Books.DoesNotExist:
                    pass

            elif story_match:
                try:
                    connected_story = Story.objects.get(public_uuid=story_match.group(1))
                    story_link = final_url
                except Story.DoesNotExist:
                    pass

        # ─────────────────────────────
        # 생성
        # ─────────────────────────────
        BookSnap.objects.create(
            user=user,
            snap_title=snap_title,
            book_comment=snap_description,
            thumbnail=thumbnail_image,
            snap_video=snap_video,
            book=connected_book,
            story=connected_story,
            book_link=book_link,
            story_link=story_link,
            adult_choice=is_adult,
        )

        return redirect("book:my_book_snap_list")

    # GET
    return render(request, "book/snap/create_snap.html", {
        "my_book_options": my_book_options,
        "my_story_options": my_story_options,
    })



# 북 스냅 수정
@login_required
@login_required_to_main
def edit_snap(request, snap_uuid):
    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)

    if snap.user != request.user:
        return redirect("book:my_book_snap_list")

    user = request.user

    my_book_options = [
        (f"/book/detail/{book.public_uuid}/", book.name)
        for book in Books.objects.filter(user=user)
    ]

    my_story_options = [
        (f"/character/story/intro/{story.public_uuid}/", story.title)
        for story in Story.objects.filter(user=user)
    ]

    if request.method == "POST":
        snap_title       = request.POST.get("title", "").strip()
        snap_description = request.POST.get("description", "").strip()
        is_adult         = request.POST.get("adult_choice") == "on"
        thumbnail_new    = request.FILES.get("image")
        video_new        = request.FILES.get("video")

        selected_book_url  = request.POST.get("selected_book_url", "").strip()
        selected_story_url = request.POST.get("selected_story_url", "").strip()
        custom_url         = request.POST.get("custom_url", "").strip()

        final_url = selected_book_url or selected_story_url or custom_url

        if not snap_title or not snap_description:
            return render(request, "book/snap/edit_snap.html", {
                "error": "제목과 설명은 필수입니다.",
                "snap": snap,
                "my_book_options": my_book_options,
                "my_story_options": my_story_options,
            })

        # ─────────────────────────────
        # 연결 재설정 (중요)
        # ─────────────────────────────
        connected_book = None
        connected_story = None
        book_link = None
        story_link = None

        if final_url:
            book_match = re.search(r'/book/detail/([a-f0-9\-]+)/?$', final_url)
            story_match = re.search(r'/character/story/intro/([a-f0-9\-]+)/?$', final_url)

            if book_match:
                try:
                    connected_book = Books.objects.get(public_uuid=book_match.group(1))
                    book_link = final_url
                except Books.DoesNotExist:
                    pass

            elif story_match:
                try:
                    connected_story = Story.objects.get(public_uuid=story_match.group(1))
                    story_link = final_url
                except Story.DoesNotExist:
                    pass

        # ─────────────────────────────
        # 업데이트
        # ─────────────────────────────
        snap.snap_title   = snap_title
        snap.book_comment = snap_description
        snap.adult_choice = is_adult

        snap.book  = connected_book
        snap.story = connected_story
        snap.book_link  = book_link
        snap.story_link = story_link

        if thumbnail_new:
            snap.thumbnail = thumbnail_new
        if video_new:
            snap.snap_video = video_new

        snap.save()

        return redirect("book:my_book_snap_list")

    return render(request, "book/snap/edit_snap.html", {
        "snap": snap,
        "my_book_options": my_book_options,
        "my_story_options": my_story_options,
    })


# 북 스냅 삭제
@login_required
@login_required_to_main
def delete_snap(request, snap_uuid):
    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)

    # 작성자만 삭제 가능
    if snap.user != request.user:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    snap.delete()
    return redirect("book:my_book_snap_list")


# 북 스냅 상세 페이지 (유튜브 쇼츠 스타일)
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
import uuid  # 필요 시
import random

@login_required_to_main
def book_snap_detail(request, snap_uuid):
    from advertisment.models import Advertisement, AdImpression

    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)
    print(f"요청된 snap_uuid (str): {snap_uuid}")

    # 성인 콘텐츠 처리
    is_adult_content = snap.adult_choice
    is_authorized = request.user.is_authenticated and request.user.is_adult()
    show_blur = is_adult_content and not is_authorized

    # ── 광고 (20% 확률, 광고에서 돌아온 경우 skip) ──────────────
    skip_ad = request.GET.get('skip_ad')
    if not skip_ad and request.user.is_authenticated:
        if random.random() < 0.2:
            ad = Advertisement.objects.filter(
                placement='snap',
                ad_type='video',
                is_active=True,
            ).order_by('?').first()
            if ad:
                redirect_url = reverse('book:ad_video', kwargs={'uuid': ad.public_uuid})
                redirect_url += f'?next={snap_uuid}'
                return redirect(redirect_url)
    # ────────────────────────────────────────────────────────────

    # UUID 전체 목록
    all_snap_uuids = list(
        BookSnap.objects
        .order_by('-created_at')
        .values_list('public_uuid', flat=True)
    )
    all_snap_uuids = [str(u) for u in all_snap_uuids]
    current_str_uuid = str(snap.public_uuid)

    print(f"[DEBUG] 전체 스냅 개수: {len(all_snap_uuids)}")

    try:
        current_index = all_snap_uuids.index(current_str_uuid)
        print(f"[DEBUG] 현재 인덱스: {current_index}")
    except ValueError:
        print(f"[ERROR] UUID 매칭 실패")
        current_index = 0

    prev_snap_uuid = (
        all_snap_uuids[current_index - 1]
        if current_index > 0 else None
    )
    next_snap_uuid = (
        all_snap_uuids[current_index + 1]
        if current_index < len(all_snap_uuids) - 1 else None
    )

    # 끝이면 랜덤 선택
    if next_snap_uuid is None and len(all_snap_uuids) > 1:
        candidates = [u for u in all_snap_uuids if u != current_str_uuid]
        if candidates:
            next_snap_uuid = random.choice(candidates)

    if prev_snap_uuid is None and len(all_snap_uuids) > 1:
        candidates = [u for u in all_snap_uuids if u != current_str_uuid]
        if candidates:
            prev_snap_uuid = random.choice(candidates)

    print(f"[DEBUG] prev_snap_uuid: {prev_snap_uuid}")
    print(f"[DEBUG] next_snap_uuid: {next_snap_uuid}")

    comments = snap.comments.filter(parent=None).order_by('-created_at')

    context = {
        "snap": snap,
        "prev_snap_uuid": prev_snap_uuid,
        "next_snap_uuid": next_snap_uuid,
        "comments": comments,
        "total_snaps": len(all_snap_uuids),
        "current_position": current_index + 1,
        "show_blur": show_blur,
    }

    return render(request, "book/snap/snap_detail.html", context)



def video_view(request, uuid):
    from book.models import Content, BookSnap
    ad = get_object_or_404(Advertisement, public_uuid=uuid, ad_type='video', is_active=True)

    AdImpression.objects.create(
        ad=ad,
        user=request.user if request.user.is_authenticated else None,
        placement=ad.placement,
    )

    next_uuid = request.GET.get('next', None)

    # snap에서 온 경우 vs content에서 온 경우 구분
    next_content = None
    next_snap = None
    if next_uuid:
        next_content = Content.objects.filter(public_uuid=next_uuid, is_deleted=False).first()
        if not next_content:
            next_snap = BookSnap.objects.filter(public_uuid=next_uuid).first()

    return render(request, "book/snap/video.html", {
        'ad': ad,
        'next_content': next_content,
        'next_snap': next_snap,
    })

# 좋아요 API
@require_POST
@login_required
def book_snap_like(request, snap_uuid):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    print(snap_uuid)

    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)
    user = request.user

    if user in snap.booksnap_like.all():
        snap.booksnap_like.remove(user)
        liked = False
    else:
        snap.booksnap_like.add(user)
        liked = True

    return JsonResponse({"likes": snap.booksnap_like.count(), "liked": liked})


# 조회수 증가 API
@require_POST
@login_required
def book_snap_view_count(request, snap_uuid):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)
    user = request.user
    print(snap_uuid)

    # 조회수 중복 방지
    if user not in snap.viewed_users.all():
        snap.views += 1
        snap.viewed_users.add(user)
        snap.save()

    return JsonResponse({"views": snap.views})


# 댓글 작성 API
@require_POST
@login_required
def book_snap_comment(request, snap_uuid):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    content = request.POST.get("content")
    parent_id = request.POST.get("parent_id")

    if not content:
        return JsonResponse({"error": "댓글 내용 없음"}, status=400)

    snap = get_object_or_404(BookSnap, public_uuid=snap_uuid)

    comment = BookSnapComment.objects.create(
        snap=snap,
        user=request.user,
        content=content,
        parent_id=parent_id if parent_id else None
    )

    return JsonResponse({
        "id": comment.id,
        "content": comment.content,
        "user": str(comment.user),
        "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M"),
    })

from book.utils import chat_with_character
def test(request):
    books = Books.objects.all()
    context = {
        "books": books,
    }



    return render(request, "book/test.html", context)
def chat_api(request):
    """Ajax로 들어오는 메시지 처리 API"""
    if request.method == "POST":
        book_uuid = request.POST.get("public_uuid")
        user_msg = request.POST.get("message")

        if not book_uuid or not user_msg:
            return JsonResponse({"error": "필수 데이터 누락"}, status=400)

        # 책 존재 확인
        try:
            book = Books.objects.get(public_uuid=book_uuid)
        except Books.DoesNotExist:
            return JsonResponse({"error": "책을 찾을 수 없음"}, status=404)

        # AI 함수 호출 (현재 MOCK)
        try:
            result = chat_with_character(book_id=book.id, message=user_msg)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

        return JsonResponse({
            "text": result.get("text", ""),
            "audio": result.get("audio", None),
            "debug": result.get("debug", {})
        })

    return JsonResponse({"error": "POST 요청만 허용"}, status=405)



from collections import Counter
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg
from datetime import datetime, timedelta
from book.models import ReadingProgress, ListeningHistory, Books
import json


# ------------------------------------------------------
# 🔥 연령 → 연령대 변환 함수
# ------------------------------------------------------
def normalize_age(age):
    try:
        age = int(age)
    except:
        return "기타"
    if age <10 :
        return "어린이"

    if 10 <= age < 20:
        return "10대"
    if 20 <= age < 30:
        return "20대"
    if 30 <= age < 40:
        return "30대"
    if 40 <= age < 50:
        return "40대"
    if age >= 50:
        return "50대 이상"
    return "기타"



from django.db.models import Count, Sum, Q
from django.db.models.functions import Coalesce

@login_required
@login_required_to_main
def author_dashboard(request):
    import json
    from django.db.models import Count, Sum, Avg, Prefetch
    from datetime import datetime, timedelta
    from book.models import ReadingProgress, ListeningHistory, Books, Follow, Content

    # 로그인한 작가의 책들 (삭제되지 않은 에피소드만 포함)
    user_books = Books.objects.filter(user=request.user).prefetch_related(
        Prefetch('contents', queryset=Content.objects.filter(is_deleted=False))
    ).order_by("-created_at")

    # 기본 통계 (삭제되지 않은 에피소드만 카운트)
    total_books = user_books.count()
    total_contents = sum(book.contents.filter(is_deleted=False).count() for book in user_books)
    total_audio_duration = request.user.get_total_audiobook_duration_formatted()

    # 팔로워 수
    total_followers = Follow.objects.filter(following=request.user).count()

    # 전체 독자 수
    total_readers = (
        ReadingProgress.objects
        .filter(book__in=user_books)
        .values('user')
        .distinct()
        .count()
    )

    book_stats = []
    book_stats_json = []

    for book in user_books:

        readers = ReadingProgress.objects.filter(book=book)
        reader_count = readers.values('user').distinct().count()

        # ------------------------------
        # 📌 성별 통계 (Users 테이블에서 직접 조회)
        # ------------------------------
        from register.models import Users

        # ReadingProgress에서 user_id만 추출
        reader_user_ids = readers.values_list('user_id', flat=True).distinct()



        # ------------------------------
        # 📌 청취 시간 총합 (초)
        # ------------------------------
        total_listening_seconds = (
            ListeningHistory.objects
            .filter(content__book=book)
            .aggregate(total=Sum('listened_seconds'))['total'] or 0
        )

        def format_time(seconds):
            if seconds == 0:
                return "0분"
            h = seconds // 3600
            m = (seconds % 3600) // 60
            if h > 0:
                return f"{h}시간 {m}분"
            if m > 0:
                return f"{m}분"
            return f"{seconds}초"

        total_listening_formatted = format_time(total_listening_seconds)

        # ------------------------------
        # 📌 평균 진행률
        # ------------------------------
        avg_progress = readers.aggregate(avg=Avg('last_read_content_number'))['avg'] or 0
        total_ep = book.contents.filter(is_deleted=False).count()  # 삭제되지 않은 에피소드만 카운트
        avg_progress_percent = round((avg_progress / total_ep * 100) if total_ep else 0, 1)

        # ------------------------------
        # 📌 템플릿용 데이터
        # ------------------------------
        book_stats.append({
            "book": book,
            "reader_count": reader_count,
            "total_listening_seconds": total_listening_seconds,
            "total_listening_formatted": total_listening_formatted,
            "avg_progress_percent": avg_progress_percent,
            "book_duration": book.get_total_duration_formatted(),
        })

        # JS에서 쓰기 위한 JSON
        book_stats_json.append({
            "book_id": book.id,
            "book_name": book.name,
            "reader_count": reader_count,

            "total_listening_seconds": total_listening_seconds,
            "avg_progress_percent": avg_progress_percent,
        })

    # 최근 30일 활동
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_readers = (
        ReadingProgress.objects
        .filter(book__in=user_books, last_read_at__gte=thirty_days_ago)
        .count()
    )



    #__________________________
    # AI 통계 
    user = request.user
    ai_stats = (
        LLM.objects
        .filter(user=request.user)
        .select_related('story')  # story.title 같은 거 쓸 때
        .annotate(
            # 👥 AI 당 대화 유저 수
            reader_count=Count(
                'conversation__user',
                distinct=True
            ),

            # ❤️ 좋아요 수
            like_count=Count(
                'llmlike',
                distinct=True
            ),

            # 🎧 TTS 오디오 총 duration
            total_tts_duration=Coalesce(
                Sum(
                    'conversation__messages__audio_duration',
                    filter=Q(
                        conversation__messages__audio_duration__isnull=False
                    )
                ),
                0.0
            )
        )
        .order_by('-reader_count')
    )

    ai_summary = (
        LLM.objects
        .filter(user=request.user)
        .aggregate(
            # 🤖 총 LLM 수
            total_llms=Count('id', distinct=True),

            # 👥 전체 AI 독자 수 (중복 제거)
            total_ai_readers=Count(
                'conversation__user',
                distinct=True
            ),

            # ❤️ 전체 LLM 좋아요 수
            total_llm_likes=Count(
                'llmlike',
                distinct=True
            ),

            # 🎧 전체 TTS 오디오 길이
            total_ai_tts_duration=Coalesce(
                Sum(
                    'conversation__messages__audio_duration',
                    filter=Q(
                        conversation__messages__audio_duration__isnull=False
                    )
                ),
                0.0
            )
        )
    )


    context = {
        "total_books": total_books,
        "total_contents": total_contents,
        "total_audio_duration": total_audio_duration,
        "total_followers": total_followers,
        "total_readers": total_readers,
        "recent_readers": recent_readers,
        "book_stats": book_stats,
        "book_stats_json": json.dumps(book_stats_json),
        "ai_stats": ai_stats,
        "ai_summary": ai_summary,
    }

    return render(request, "book/author_dashboard.html", context)



@require_POST
@login_required
def toggle_status(request, book_uuid):
    if request.method == "POST":
        book = get_object_or_404(Books, public_uuid=book_uuid)
        import json
        data = json.loads(request.body)
        new_status = data.get("status")

        if new_status not in ["ongoing", "paused", "ended"]:
            return JsonResponse({"error": "Invalid status"}, status=400)

        # 상태 저장
        book.status = new_status
        book.save()

        return JsonResponse({"status": book.status})

    return JsonResponse({"error": "Invalid method"}, status=405)

# 공지사항 생성
@login_required
def create_announcement(request, book_uuid):
    from book.models import AuthorAnnouncement
    book = get_object_or_404(Books, public_uuid=book_uuid)

    # 작가만 공지사항 생성 가능
    if request.user != book.user:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    if request.method == "POST":
        title = request.POST.get("title", "공지사항")
        content = request.POST.get("content", "")
        is_pinned = request.POST.get("is_pinned") == "on"

        if not content:
            return JsonResponse({"success": False, "error": "내용을 입력해주세요."}, status=400)

        announcement = AuthorAnnouncement.objects.create(
            book=book,
            author=request.user,
            title=title,
            content=content,
            is_pinned=is_pinned
        )

        return redirect("book:book_detail", book_uuid=book.public_uuid)

    return redirect("book:book_detail", book_uuid=book.public_uuid)


# 공지사항 수정
@login_required
def update_announcement(request, announcement_id):
    from book.models import AuthorAnnouncement
    announcement = get_object_or_404(AuthorAnnouncement, id=announcement_id)

    # 작가만 수정 가능
    if request.user != announcement.author:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    if request.method == "POST":
        announcement.title = request.POST.get("title", announcement.title)
        announcement.content = request.POST.get("content", announcement.content)
        announcement.is_pinned = request.POST.get("is_pinned") == "on"
        announcement.save()

        return redirect("book:book_detail", book_uuid=announcement.book.public_uuid)

    return redirect("book:book_detail", book_uuid=announcement.book.public_uuid)


# 공지사항 삭제
@login_required
def delete_announcement(request, announcement_id):
    from book.models import AuthorAnnouncement
    announcement = get_object_or_404(AuthorAnnouncement, id=announcement_id)

    # 작가만 삭제 가능
    if request.user != announcement.author:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    book_uuid = announcement.book.public_uuid
    announcement.delete()

    return redirect("book:book_detail", book_uuid=book_uuid)


# 에피소드 삭제 (작가만) - Soft Delete
@login_required
def delete_content(request, content_uuid):
    from book.models import Content
    from django.utils import timezone

    content = get_object_or_404(Content, public_uuid=content_uuid, is_deleted=False)
    book = content.book

    # 작가만 삭제 가능
    if request.user != book.user:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    if request.method == "POST":
        # Soft Delete: 실제로 삭제하지 않고 플래그만 설정
        content.is_deleted = True
        content.deleted_at = timezone.now()
        content.save()

        # 회차 번호 재정렬 (삭제되지 않은 에피소드만)
        remaining_contents = book.contents.filter(is_deleted=False).order_by('number')
        for idx, c in enumerate(remaining_contents, start=1):
            c.number = idx
            c.save()

        return redirect("book:book_detail", book_uuid=book.public_uuid)

    return redirect("book:book_detail", book_uuid=book.public_uuid)


# 에피소드 순서 변경
@login_required
@require_POST
def reorder_content(request, book_uuid):
    from book.models import Content
    import json

    try:
        book = get_object_or_404(Books, public_uuid=book_uuid)

        # 작가만 순서 변경 가능
        if request.user != book.user:
            return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

        data = json.loads(request.body)
        content_ids = data.get('content_ids', [])

        if not content_ids:
            return JsonResponse({"success": False, "error": "에피소드 ID가 없습니다."}, status=400)

        # 새로운 순서대로 회차 번호 업데이트 (삭제되지 않은 것만)
        for new_number, content_id in enumerate(content_ids, start=1):
            content = Content.objects.filter(id=content_id, book=book, is_deleted=False).first()
            if content:
                content.number = new_number
                content.save()

        return JsonResponse({"success": True, "message": "순서가 변경되었습니다."})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# 북마크/메모 생성/수정
@login_required
@require_POST
def save_bookmark(request, content_uuid):
    from book.models import ContentBookmark, Content
    import json

    try:
        data = json.loads(request.body)
        position = float(data.get('position', 0))
        memo = data.get('memo', '').strip()

        if position < 0:
            return JsonResponse({'success': False, 'error': '위치가 올바르지 않습니다.'}, status=400)

        content = get_object_or_404(Content, public_uuid=content_uuid)

        # 같은 위치에 북마크가 있는지 확인 (±1초 범위)
        existing = ContentBookmark.objects.filter(
            user=request.user,
            content=content,
            position__gte=position-1,
            position__lte=position+1
        ).first()

        if existing:
            # 기존 북마크 업데이트
            existing.position = position
            existing.memo = memo
            existing.save()
            bookmark_id = existing.id
        else:
            # 새 북마크 생성
            bookmark = ContentBookmark.objects.create(
                user=request.user,
                content=content,
                position=position,
                memo=memo
            )
            bookmark_id = bookmark.id

        return JsonResponse({
            'success': True,
            'bookmark_id': bookmark_id,
            'message': '북마크가 저장되었습니다.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# 북마크 목록 조회
@login_required
@login_required_to_main
def get_bookmarks(request, content_uuid):
    from book.models import ContentBookmark

    try:
        content = get_object_or_404(Content, public_uuid=content_uuid)
        bookmarks = ContentBookmark.objects.filter(
            user=request.user,
            content=content
        ).order_by('position')

        bookmarks_data = [{
            'id': b.id,
            'position': b.position,
            'position_formatted': b.get_position_formatted(),
            'memo': b.memo,
            'created_at': b.created_at.strftime('%Y-%m-%d %H:%M')
        } for b in bookmarks]

        return JsonResponse({'success': True, 'bookmarks': bookmarks_data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# 북마크 삭제
@login_required
@require_POST
def delete_bookmark(request, bookmark_id):
    from book.models import ContentBookmark

    try:
        bookmark = get_object_or_404(ContentBookmark, id=bookmark_id, user=request.user)
        bookmark.delete()

        return JsonResponse({
            'success': True,
            'message': '북마크가 삭제되었습니다.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




# 검색 페이지
def search_page(request):
    query = request.GET.get('q', '')
    return render(request, 'book/search.html', {'query': query})



# ==================== 북마크 기능 ====================

@login_required
def toggle_bookmark(request, book_uuid):
    """
    북마크 토글 (추가/제거)
    """
    print(f"🔖 북마크 토글 요청 - 사용자: {request.user}, 책 UUID: {book_uuid}")

    if request.method != 'POST':
        print(f"❌ 잘못된 메서드: {request.method}")
        return JsonResponse({'error': '잘못된 요청입니다'}, status=400)

    from book.models import BookmarkBook

    try:
        book = Books.objects.get(public_uuid=book_uuid)
        print(f"📖 책 찾음: {book.name}")
    except Books.DoesNotExist:
        print(f"❌ 책을 찾을 수 없음: {book_uuid}")
        return JsonResponse({'error': '책을 찾을 수 없습니다'}, status=404)

    # 북마크 토글
    try:
        bookmark, created = BookmarkBook.objects.get_or_create(
            user=request.user,
            book=book
        )
        print(f"✅ 북마크 객체: created={created}, bookmark_id={bookmark.id if bookmark else None}")
    except Exception as e:
        print(f"❌ 북마크 생성/조회 오류: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'데이터베이스 오류: {str(e)}'}, status=500)

    if not created:
        # 이미 북마크되어 있으면 제거
        bookmark.delete()
        is_bookmarked = False
        message = '북마크에서 제거되었습니다'
        print(f"🗑️ 북마크 제거됨")
    else:
        is_bookmarked = True
        message = '북마크에 추가되었습니다'
        print(f"➕ 북마크 추가됨")

    response_data = {
        'success': True,
        'is_bookmarked': is_bookmarked,
        'message': message
    }
    print(f"📤 응답: {response_data}")
    return JsonResponse(response_data)


@login_required
@login_required_to_main
def my_bookmarks(request):
    """
    내 북마크 목록 페이지 (책 + AI 스토리)
    """
    from book.models import BookmarkBook
    from character.models import StoryBookmark, Story
    from django.core.paginator import Paginator

    all_bookmarks = BookmarkBook.objects.filter(
        user=request.user
    ).select_related('book', 'book__user').prefetch_related(
        'book__genres', 'book__tags'
    ).order_by('-created_at')

    # 오디오북 / 웹소설 분리
    audiobook_bms = [bm for bm in all_bookmarks if getattr(bm.book, 'book_type', 'audiobook') == 'audiobook']
    webnovel_bms  = [bm for bm in all_bookmarks if getattr(bm.book, 'book_type', 'audiobook') == 'webnovel']

    paginator = Paginator(audiobook_bms, 20)
    page = request.GET.get('page')
    bookmarks_page = paginator.get_page(page)

    # AI 스토리 북마크
    story_bookmarks = StoryBookmark.objects.filter(
        user=request.user
    ).select_related('story', 'story__user').prefetch_related(
        'story__genres', 'story__characters'
    ).order_by('-created_at')

    context = {
        'bookmarks': bookmarks_page,
        'webnovel_bookmarks': webnovel_bms,
        'story_bookmarks': story_bookmarks,
    }

    return render(request, 'book/my_bookmarks.html', context)


# ==================== 팔로우 기능 (웹용) ====================
@login_required
@require_POST
def toggle_follow(request, user_id):
    """
    웹에서 사용하는 팔로우/언팔로우 토글
    POST /book/follow/<user_id>/toggle/
    """
    from register.models import Users
    from book.models import Follow

    try:
        target_user = get_object_or_404(Users, user_id=user_id)

        # 자기 자신은 팔로우 불가
        if request.user.user_id == target_user.user_id:
            return JsonResponse({'success': False, 'error': '자기 자신을 팔로우할 수 없습니다'}, status=400)

        # 팔로우 토글
        follow, created = Follow.objects.get_or_create(
            follower=request.user,
            following=target_user
        )

        if not created:
            # 이미 팔로우 중이면 언팔로우
            follow.delete()
            is_following = False
        else:
            is_following = True

        # 팔로워 수 계산
        follower_count = Follow.objects.filter(following=target_user).count()

        return JsonResponse({
            'success': True,
            'is_following': is_following,
            'follower_count': follower_count
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from book.models import Books, Content, MyVoiceList
from register.decorator import login_required_to_main
from voxliber.security import validate_image_file
from django.core.exceptions import ValidationError


@login_required
@login_required_to_main
def book_serilazation_fast_view(request, book_uuid):
    book = get_object_or_404(Books, public_uuid=book_uuid, user=request.user)

    # 🔥 POST: 이미지 저장
    if request.method == 'POST':
        episode_image = request.FILES.get('episode_image')
        episode_number = request.POST.get('episode_number')
        
        if episode_image and episode_number:
            try:
                # 이미지 검증
                validate_image_file(episode_image)
                
                # 에피소드 찾기
                content = Content.objects.filter(
                    book=book, 
                    number=int(episode_number),
                    is_deleted=False
                ).first()
                
                if content:
                    content.episode_image = episode_image
                    content.save()
                    return JsonResponse({
                        'success': True, 
                        'image_url': content.episode_image.url
                    })
                else:
                    return JsonResponse({
                        'success': False, 
                        'error': '에피소드를 찾을 수 없습니다'
                    }, status=404)
                    
            except ValidationError as e:
                return JsonResponse({
                    'success': False, 
                    'error': str(e)
                }, status=400)
            except Exception as e:
                return JsonResponse({
                    'success': False, 
                    'error': str(e)
                }, status=500)

    # GET: 기존 그대로
    voice_list = MyVoiceList.objects.filter(user=request.user)
    
    last_episode = Content.objects.filter(
        book=book,
        is_deleted=False  # 🔥 삭제되지 않은 것만
    ).aggregate(Max('number'))
    
    next_episode_number = (last_episode['number__max'] or 0) + 1
    
    # 초보자 가이드 (fast 카테고리)
    from book.models import AudioBookGuide
    guides = AudioBookGuide.objects.filter(category='fast', is_active=True).order_by('order_num')

    import json as _json
    context = {
        'book': book,
        'voice_list': voice_list,
        'next_episode_number': next_episode_number,
        'guides': guides,
        'voice_config_json': _json.dumps(book.voice_config or {}),
        'draft_text_json': _json.dumps(book.draft_text or ''),
        'draft_episode_title_json': _json.dumps(book.draft_episode_title or ''),
    }
    return render(request, 'book/book_serialization_fast.html', context)


@login_required
@require_POST
def save_voice_config(request, book_uuid):
    """캐릭터 보이스 설정 + 소설 텍스트 임시저장"""
    import json as _json
    book = get_object_or_404(Books, public_uuid=book_uuid, user=request.user)
    try:
        data = _json.loads(request.body)
        update_fields = []
        if 'voice_config' in data:
            book.voice_config = data['voice_config']
            update_fields.append('voice_config')
        if 'draft_text' in data:
            book.draft_text = data['draft_text']
            update_fields.append('draft_text')
        if 'draft_episode_title' in data:
            book.draft_episode_title = data['draft_episode_title']
            update_fields.append('draft_episode_title')
        if update_fields:
            book.save(update_fields=update_fields)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ==================== AI 오디오북 분석 (Grok) ====================
import json as json_module
from book.utils import grok_client, generate_tts, merge_audio_files, sound_effect, background_music, mix_audio_with_background

@login_required
@require_POST
def ai_analyze_audiobook(request):
    """
    Grok AI로 텍스트 분석 → 감정태그, BGM, SFX 자동 추가
    입력: batch JSON (create_episode step with pages)
    출력: 강화된 batch JSON
    """
    try:
        data = json_module.loads(request.body)
    except json_module.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

    # 에피소드 step 찾기
    steps = data.get('steps', [])
    episode_step = None
    for step in steps:
        if step.get('action') == 'create_episode':
            episode_step = step
            break

    if not episode_step or not episode_step.get('pages'):
        return JsonResponse({'error': 'create_episode step이 없습니다'}, status=400)

    pages = episode_step['pages']

    # 텍스트 목록 생성 (일반 페이지, N인 대화, 무음 모두 처리)
    text_list = []
    for i, page in enumerate(pages):
        if 'text' in page:
            text = page['text']
        elif 'voices' in page:
            # N인 대화: 각 목소리 텍스트를 " / "로 연결
            text = ' / '.join(v.get('text', '') for v in page['voices'] if v.get('text', '').strip())
        elif 'silence_seconds' in page:
            text = f'[무음 {page["silence_seconds"]}초]'
        else:
            text = ''
        text_list.append(f"[{i+1}] {text}")
    all_text = "\n".join(text_list)

    # Grok API 호출
    prompt = f"""당신은 한국어 오디오북 제작 AI입니다. 아래 소설 텍스트를 분석해서 JSON으로 응답하세요.

=== 소설 텍스트 (페이지별) ===
{all_text}

=== 분석 요청 ===

1. **감정 태그 (emotions)**: 각 페이지에 어울리는 감정 태그를 1~3개 선택하세요.
   사용 가능한 태그: calm, excited, sad, angry, scared, whisper, laughing, crying, thinking, curious, serious, trembling, cold, warm, desperate, confused, confident, shy, romantic, mysterious

2. **배경음악 (bgm)**: 에피소드 전체 분위기에 맞는 배경음악 1개만 제안하세요.
   - name: 한국어 이름
   - description: 영어로 된 음악 설명 (장르, 분위기, 악기 등)
   - start_page: 시작 페이지 번호 (1부터)
   - end_page: 끝 페이지 번호

3. **효과음 (sfx)**: 특정 장면·상황에 꼭 필요한 효과음만 제안하세요 (0~3개).
   반드시 실제 소리가 날 법한 장면(문 소리, 발소리, 전화 등)에만 배치하고, 각각 다른 페이지에 분산 배치하세요.
   - name: 한국어 이름
   - description: 영어로 된 효과음 설명
   - page: 적용할 페이지 번호 (1부터 시작, 각 sfx는 서로 다른 페이지에 배치)

=== 응답 형식 (JSON만, 설명 없이) ===
{{
  "emotions": [["calm"], ["excited", "curious"], ...],
  "bgm": [
    {{"name": "긴장감 있는 밤", "description": "Dark ambient with low strings", "start_page": 1, "end_page": 10}}
  ],
  "sfx": [
    {{"name": "문 여는 소리", "description": "wooden door creaking open", "page": 3}}
  ]
}}"""

    try:
        response = grok_client.chat.completions.create(
            model="grok-3-mini",
            messages=[
                {"role": "system", "content": "JSON만 응답하세요. 설명이나 마크다운 코드블록 없이 순수 JSON만 출력하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )

        ai_text = response.choices[0].message.content.strip()

        # 마크다운 코드블록 제거
        if ai_text.startswith('```'):
            ai_text = ai_text.split('\n', 1)[1] if '\n' in ai_text else ai_text[3:]
        if ai_text.endswith('```'):
            ai_text = ai_text[:-3]
        ai_text = ai_text.strip()

        ai_result = json_module.loads(ai_text)

    except json_module.JSONDecodeError:
        return JsonResponse({'error': 'AI 응답 파싱 실패', 'raw': ai_text[:500]}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Grok API 오류: {str(e)}'}, status=500)

    # 강화된 JSON 생성
    enhanced_steps = []

    # BGM steps
    bgm_list = ai_result.get('bgm', [])
    for bgm in bgm_list:
        enhanced_steps.append({
            "action": "create_bgm",
            "music_name": bgm.get('name', 'BGM'),
            "music_description": bgm.get('description', ''),
            "duration_seconds": 120
        })

    # SFX steps
    sfx_list = ai_result.get('sfx', [])
    for sfx_item in sfx_list:
        enhanced_steps.append({
            "action": "create_sfx",
            "effect_name": sfx_item.get('name', 'SFX'),
            "effect_description": sfx_item.get('description', '')
        })

    # 감정 태그만 적용한 에피소드
    emotions = ai_result.get('emotions', [])

    enhanced_pages = []
    for i, page in enumerate(pages):
        new_page = dict(page)

        # 감정 태그 추가 (일반 텍스트 페이지만 / N인 대화·무음은 건너뜀)
        if i < len(emotions) and emotions[i] and 'text' in new_page:
            tags = ''.join([f'[{e}]' for e in emotions[i]])
            if not new_page['text'].startswith('['):
                new_page['text'] = f"{tags} {new_page['text']}"

        enhanced_pages.append(new_page)

    enhanced_steps.append({
        "action": "create_episode",
        "book_uuid": data.get('book_uuid', ''),
        "episode_number": episode_step.get('episode_number', 1),
        "episode_title": episode_step.get('episode_title', ''),
        "pages": enhanced_pages
    })

    # 믹싱 step (BGM/SFX가 있을 때)
    if bgm_list or sfx_list:
        mix_step = {
            "action": "mix_bgm",
            "book_uuid": data.get('book_uuid', ''),
            "episode_number": episode_step.get('episode_number', 1),
            "background_tracks": [],
            "sound_effects": []
        }

        for idx, bgm in enumerate(bgm_list):
            mix_step["background_tracks"].append({
                "music_id": f"$bgm_{idx + 1}",
                "start_page": (bgm.get('start_page', 1) - 1),
                "end_page": min(bgm.get('end_page', len(pages)) - 1, len(pages) - 1),
                "volume": 0.25,
                "loop": True
            })

        for idx, sfx_item in enumerate(sfx_list):
            mix_step["sound_effects"].append({
                "effect_id": f"$sfx_{idx + 1}",
                "page_number": sfx_item.get('page', 1),
                "volume": 0.7
            })

        enhanced_steps.append(mix_step)

    enhanced_data = {
        "action": "batch",
        "book_uuid": data.get('book_uuid', ''),
        "steps": enhanced_steps
    }

    return JsonResponse(enhanced_data)


# ==================== AI 화자 자동 분류 (OpenAI GPT) ====================
@login_required
@require_POST
def ai_assign_speakers(request):
    """
    자연어 소설 텍스트를 받아서 GPT로 화자 분류 후 N: 텍스트 형식으로 반환.

    POST /book/json/ai-speakers/
    Body: { "text": "소설 원문...", "characters": { "0": "나레이션", "1": "지우", "2": "도현" } }
    Response: { "formatted_text": "0: [calm] 비 오는 밤이었다.\n1: [sad] \"넌 항상 늦어.\"\n..." }
    """
    try:
        data = json_module.loads(request.body)
    except json_module.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

    text = data.get('text', '').strip()
    characters = data.get('characters', {})

    if not text:
        return JsonResponse({'error': '텍스트가 비어있습니다.'}, status=400)
    if not characters:
        return JsonResponse({'error': '캐릭터가 등록되지 않았습니다.'}, status=400)

    # 캐릭터 목록 문자열 생성
    sorted_chars = sorted(characters.items(), key=lambda x: int(x[0]))
    char_lines = []
    for num, name in sorted_chars:
        char_lines.append(f"{num}: {name}")
    char_list_str = "\n".join(char_lines)

    # 등록된 번호 목록 (AI에게 명시적으로 전달)
    valid_nums = [str(num) for num, _ in sorted_chars]
    valid_nums_str = ", ".join(valid_nums)

    # 동시 발화 예시: 등록된 캐릭터 중 0 제외 첫 두 명으로 동적 생성
    non_narr = [str(num) for num, _ in sorted_chars if int(num) != 0]
    if len(non_narr) >= 2:
        duet_example = f"{non_narr[0]},{non_narr[1]}: \"같이 외쳤다!\""
    elif len(non_narr) == 1:
        duet_example = f"0,{non_narr[0]}: \"같이 외쳤다!\""
    else:
        duet_example = ""  # 캐릭터 1명뿐이면 동시 발화 예시 없음

    duet_section = ""
    if duet_example:
        duet_section = f"""
=== 동시 발화(2인 대화) 규칙 ===
- 두 캐릭터가 동시에 같은 말을 외치는 장면에만 사용
- 반드시 등록된 번호({valid_nums_str})만 쉼표로 나열: 예) {duet_example}
- 동시 발화가 아닌 일반 대화는 반드시 각자 별도 줄로 처리
"""

    prompt = f"""당신은 한국어 소설/오디오북의 화자 분류 전문가입니다.
아래 소설 텍스트를 읽고, 각 줄에 적절한 캐릭터 번호를 매겨주세요.

=== 등록된 캐릭터 (이 번호들만 사용 가능) ===
{char_list_str}

⚠️ 절대 규칙: 위 번호({valid_nums_str}) 이외의 번호는 절대 사용 금지!
등록되지 않은 번호를 출력하면 시스템이 오작동합니다.

=== 소설 텍스트 ===
{text}

=== 핵심 규칙: 줄바꿈 기준 분류 ===
- 입력 텍스트의 각 줄(줄바꿈으로 구분된 단위)을 하나의 단위로 취급하세요
- 각 줄을 통째로 하나의 캐릭터 번호에 배정하세요
- 빈 줄은 무시하세요
- 절대로 한 줄을 여러 줄로 쪼개지 마세요 (줄 수를 유지!)

=== 화자 판단 규칙 ===
1. 서술/묘사/나레이션만 있는 줄 → 0번
2. "대사"가 포함된 줄 → 해당 캐릭터 번호
3. 나레이션+대사가 섞인 줄 → 대사의 화자 번호로 배정
4. 대사 앞뒤 문맥(누가 말했는지)으로 화자 판단
5. 각 줄 앞에 감정 태그 1~2개 추가
6. 나레이션은 해라체/문어체 유지
7. 대사는 쌍따옴표로 감싸기{duet_section}
=== 출력 형식 (등록된 번호만 사용!) ===
각 줄 형식: {{번호}}: {{텍스트}}
사용 가능한 번호: {valid_nums_str}

- 원본 텍스트의 위치와 띄어쓰기, 문장을 변경하지 마세요. 오직 앞에 번호만 붙이세요.
(문장은 여러개이지만 같은 캐릭터일 경우 하나의 번호만 지정하세요. 나레이션이 말할거 같은 텍스트는 무조건 0으로 번호를 지정하세요.
입력과 같은 줄 수 유지, 다른 설명 없이 결과만 출력)"""

    try:
        from book.utils import openai_client
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "소설 텍스트의 화자를 분류하고 번호를 매기는 전문가입니다. 지시된 형식으로만 출력하세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=8000
        )

        result_text = response.choices[0].message.content.strip()

        # 마크다운 코드블록 제거
        if result_text.startswith('```'):
            result_text = result_text.split('\n', 1)[1] if '\n' in result_text else result_text[3:]
        if result_text.endswith('```'):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        return JsonResponse({'formatted_text': result_text})

    except Exception as e:
        return JsonResponse({'error': f'GPT API 오류: {str(e)}'}, status=500)


# ==================== 배치 JSON 실행 (Celery 비동기) ====================
@login_required
@require_POST
def process_json_audiobook(request):
    """
    배치 JSON을 Celery로 비동기 실행.
    즉시 task_id를 반환하고, 프론트에서 폴링으로 진행률 확인.
    """
    try:
        data = json_module.loads(request.body)
    except json_module.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

    steps = data.get('steps', [])
    if not steps:
        return JsonResponse({'error': 'steps가 비어있습니다'}, status=400)

    book_uuid = data.get('book_uuid', '')
    if book_uuid:
        book = Books.objects.filter(public_uuid=book_uuid, user=request.user).first()
        if not book:
            return JsonResponse({'error': f'책을 찾을 수 없습니다: {book_uuid}'}, status=404)

    # Celery 태스크 시작
    from book.tasks import process_batch_audiobook
    task = process_batch_audiobook.delay(data, request.user.user_id)

    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'message': '오디오북 생성이 시작되었습니다'
    })


# ==================== 태스크 상태 조회 ====================
@login_required
def audiobook_task_status(request, task_id):
    """Celery 태스크 진행률 조회 (프론트 폴링용)"""
    from celery.result import AsyncResult

    result = AsyncResult(task_id)

    if result.state == 'PENDING':
        response = {
            'state': 'PENDING',
            'status': '대기 중...',
            'progress': 0
        }
    elif result.state == 'PROGRESS':
        info = result.info or {}
        response = {
            'state': 'PROGRESS',
            'status': info.get('status', '처리 중...'),
            'progress': info.get('progress', 0),
            'current_step': info.get('current_step', 0),
            'total_steps': info.get('total_steps', 0)
        }
    elif result.state == 'SUCCESS':
        info = result.result or {}
        response = {
            'state': 'SUCCESS',
            'success': info.get('success', False),
            'progress': 100
        }
        if info.get('success'):
            response['redirect_url'] = info.get('redirect_url', '')
            response['episode'] = info.get('episode', {})
            response['steps_completed'] = info.get('steps_completed', 0)
        else:
            response['error'] = info.get('error', '알 수 없는 오류')
    elif result.state == 'FAILURE':
        response = {
            'state': 'FAILURE',
            'error': str(result.info) if result.info else '태스크 실패',
            'progress': 0
        }
    else:
        response = {
            'state': result.state,
            'status': '처리 중...',
            'progress': 0
        }

    return JsonResponse(response)




from advertisment.models import Advertisement, AdImpression



def audio_view(request, uuid):
    from book.models import Content
    ad = get_object_or_404(Advertisement, public_uuid=uuid, ad_type='audio', is_active=True)

    AdImpression.objects.create(
        ad=ad,
        user=request.user if request.user.is_authenticated else None,
        placement=ad.placement,
    )

    next_content_uuid = request.GET.get('next', None)
    next_content = None
    if next_content_uuid:
        next_content = Content.objects.filter(public_uuid=next_content_uuid, is_deleted=False).first()

    # 🔍 디버그
    print(f"\n{'='*50}")
    print(f"[audio_view] 광고 페이지 진입")
    print(f"[audio_view] next_content_uuid: {next_content_uuid}")
    print(f"[audio_view] next_content: {next_content.number if next_content else None}화")
    print(f"[audio_view] 전체 URL: {request.get_full_path()}")
    print(f"{'='*50}\n")

    return render(request, "book/audio.html", {
        'ad': ad,
        'next_content': next_content,
    })


# 클릭 기록 API
@require_POST
def ad_skip(request, uuid):
    ad = get_object_or_404(Advertisement, public_uuid=uuid)
    data = json.loads(request.body)
    watched_seconds = data.get('watched_seconds', 0)

    AdImpression.objects.filter(
        ad=ad,
        user=request.user if request.user.is_authenticated else None,
    ).order_by('-created_at').update(
        is_skipped=True,
        watched_seconds=watched_seconds
    )
    return JsonResponse({'status': 'ok'})


@require_POST  
def ad_click(request, uuid):
    ad = get_object_or_404(Advertisement, public_uuid=uuid)

    AdImpression.objects.filter(
        ad=ad,
        user=request.user if request.user.is_authenticated else None,
    ).order_by('-created_at').update(
        is_clicked=True,
        clicked_at=timezone.now()
    )
    return JsonResponse({'status': 'ok', 'redirect_url': ad.link_url})


def content_youtube_thumbnail(request, content_uuid):
    from book.models import Content

    content = get_object_or_404(Content, public_uuid=content_uuid, is_deleted=False)
    book = content.book

    context = {
        "content": content,
        "book": book,
    }
    return render(request, "book/content_youtube_thumbnail.html", context)