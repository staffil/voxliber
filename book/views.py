from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse,HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from book.models import Genres, Books, Tags, VoiceList, BookSnap, MyVoiceList, Content, APIKey
import os
from django.conf import settings

COLAB_TTS_URL = os.getenv('COLAB_TTS_URL', 'https://xxxx.ngrok-free.app')

# 작품 등록 이용약관

def book_tos(request):
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
def book_profile(request):
    genres_list = Genres.objects.all()
    tag_list = Tags.objects.all()
    voice_list = VoiceList.objects.all()
    book_id = request.GET.get("book_id")
    book = Books.objects.filter(id=book_id).first() if book_id else None

    if request.method == "POST":
        novel_title = request.POST.get("novel_title", "").strip()
        novel_description = request.POST.get("novel_description", "").strip()
        genre_ids = request.POST.getlist("genres")
        episode_interval_weeks = request.POST.get("episode_interval_weeks", "1")

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
            # 커버 이미지 업데이트
            if "cover-image" in request.FILES:
                book.cover_img = request.FILES["cover-image"]
            book.save()
        else:
            # 중복 제목 체크
            existing = Books.objects.filter(name=novel_title).first()
            if existing:
                # 이미 존재하면 업데이트
                book = existing
                book.description = novel_description
                book.episode_interval_weeks = int(episode_interval_weeks)
                if "cover-image" in request.FILES:
                    book.cover_img = request.FILES["cover-image"]
                book.save()
            else:
                # 새 책 생성
                book = Books.objects.create(
                    user=request.user,
                    name=novel_title,
                    description=novel_description,
                    episode_interval_weeks=int(episode_interval_weeks)
                )
                if "cover-image" in request.FILES:
                    book.cover_img = request.FILES["cover-image"]
                    book.save()

        # 장르 처리 (ManyToMany)
        if genre_ids:
            genres = Genres.objects.filter(id__in=genre_ids)
            book.genres.set(genres)
        else:
            book.genres.clear()

        # 태그 처리
        tag_ids = request.POST.getlist("tags")
        if tag_ids:
            tags = Tags.objects.filter(id__in=tag_ids)
            book.tags.set(tags)
        else:
            book.tags.clear()

        return redirect(f"/book/book_serialization/?book_id={book.id}")

    context = {
        "genres_list": genres_list,
        "tag_list": tag_list,
        "book": book,
        "voice_list": voice_list,
    }
    return render(request, "book/book_profile.html", context)

from uuid import uuid4
# 작품 연재 등록 (집필 페이지)
def book_serialization(request):
    import json
    from book.models import Content, AudioBookGuide
    from django.core import serializers

    book_id = request.GET.get("book_id") or request.POST.get("book_id")
    book = Books.objects.filter(id=book_id).first()

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

        # 각 페이지의 텍스트 정보 수집
        pages_text = []
        page_index = 0
        while True:
            page_text = request.POST.get(f'page_text_{page_index}')
            if page_text is None:
                break
            pages_text.append(page_text)
            page_index += 1

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
                content.episode_image = episode_image
                content.save()
                print(f"📷 에피소드 이미지 저장 완료: {content.episode_image.url}")

            from book.utils import merge_audio_files, generate_tts, mix_audio_with_background
            from django.core.files import File
            import tempfile

            # 🔥 미리듣기에서 생성된 최종 merge된 오디오가 있는지 확인
            merged_audio_file = request.FILES.get('merged_audio')

            if merged_audio_file:
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

                # 🔥 타임스탬프 정보 생성 (하이라이트 기능용)
                # 각 페이지 개수 수집 (사운드 이팩트 제외)
                page_count = 0
                page_index = 0
                while True:
                    page_text = request.POST.get(f'page_text_{page_index}')
                    if page_text is None:
                        break
                    if page_text.strip():  # 빈 텍스트가 아닌 경우만 카운트 (사운드 이팩트 제외)
                        page_count += 1
                    page_index += 1

                print(f"📝 타임스탬프 생성 대상: {page_count}개 대사")

                # 오디오 길이 계산 (pydub 사용)
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_file(temp_path)
                total_duration_ms = len(audio_segment)
                content.duration_seconds = int(total_duration_ms / 1000)

                # 타임스탬프 생성 (대사 텍스트 포함, 사운드 이팩트는 제외) - 간단한 방식
                if page_count > 0:
                    dialogue_durations = []
                    segment_duration = total_duration_ms / page_count
                    dialogue_index = 0

                    # pages_text를 순회하며 텍스트가 있는 것만 타임스탬프 생성
                    for page_index, page_text in enumerate(pages_text):
                        if page_text.strip():  # 텍스트가 있는 경우만 (사운드 이팩트 제외)
                            # 시작 시간과 끝 시간 계산
                            start_time = int(dialogue_index * segment_duration)
                            end_time = int((dialogue_index + 1) * segment_duration)

                            dialogue_durations.append({
                                'pageIndex': dialogue_index,
                                'startTime': start_time,  # 시작 시간
                                'endTime': end_time,  # 끝 시간
                                'text': page_text  # 대사 텍스트 포함
                            })
                            dialogue_index += 1

                    content.audio_timestamps = dialogue_durations
                    print(f"⏱️ {len(dialogue_durations)}개 대사의 타임스탬프 생성 완료 (startTime, endTime 포함)")

                content.save()
                print(f"⏱️ 총 길이: {content.duration_seconds}초")

                # 임시 파일 삭제
                os.remove(temp_path)
                print("🗑️ 임시 파일 삭제 완료")
                print("✅ 미리듣기 오디오를 사용하여 빠르게 발행 완료!")

            else:
                # ⚠️ 미리듣기를 하지 않은 경우 - 기존 방식으로 merge 수행
                print("⚠️ 미리듣기 오디오가 없음 - 개별 파일 merge 수행")

                # 업로드된 오디오 파일들 수집
                audio_files = []
                for key in request.FILES.keys():
                    if key.startswith('audio_'):
                        audio_files.append(request.FILES[key])
                        print(f"📎 오디오 파일 수신: {key}")

                # 배경음 정보 수집
                background_tracks_count = int(request.POST.get('background_tracks_count', 0))
                background_tracks = []
                print(f"🎼 배경음 트랙 개수: {background_tracks_count}")

                # 오디오 파일이 있으면 합치기, 없으면 TTS 생성
                if audio_files:
                    print(f"🎵 {len(audio_files)}개의 오디오 파일 합치기 시작...")

                    # merge_audio_files는 이제 타임스탬프 정보도 함께 반환
                    merged_audio_path, dialogue_durations = merge_audio_files(audio_files, pages_text)

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
                        audio_path = generate_tts(content_text, voice_id, language_code, speed_value)
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
                    audio_path = generate_tts(content_text, voice_id, language_code, speed_value)
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
                "redirect_url": f"/book/detail/{book.id}/"
            })
        except Exception as e:
            print(f"❌ 에피소드 저장 오류: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                "success": False,
                "error": f"에피소드 저장 중 오류가 발생했습니다: {str(e)}"
            }, status=500)

    # 최신 에피소드 번호 가져오기
    latest_episode = Content.objects.filter(book=book).order_by('-number').first()
    latest_episode_number = latest_episode.number if latest_episode else 0

    # 음성 목록 가져오기
    book_id = request.GET.get("book_id")

    voice_list = MyVoiceList.objects.filter(user=request.user)

    if book_id:
        voice_list = voice_list.filter(book_id=book_id)  # 선택한 책 기준 필터링

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

        # speed_value는 숫자로 변환
        try:
            speed_value = float(speed_value)
        except:
            speed_value = 1

        if isinstance(text, dict):
            text = text.get("content", "")
        elif not isinstance(text, str):
            text = str(text)

        text = text.strip()
        if not text:
            return JsonResponse({"success": False, "error": "텍스트가 없습니다."}, status=400)

        # 🔥 여기 speed_value 추가
        audio_path = generate_tts(text, voice_id, language_code, speed_value)
        if not audio_path:
            return JsonResponse({"success": False, "error": "TTS 생성 실패"}, status=500)

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        return HttpResponse(audio_data, content_type="audio/mpeg")

    except Exception as e:
        print("❌ 오류:", e)
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

        # 사운드 이팩트 생성
        audio_stream = sound_effect(effect_name, effect_description, duration_seconds)

        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
            for chunk in audio_stream:
                temp_file.write(chunk)

        print(f"✅ 사운드 이팩트 생성 완료: {temp_path}")

        # 라이브러리에 저장
        if save_to_library and request.user.is_authenticated:
            with open(temp_path, 'rb') as f:
                effect = SoundEffectLibrary.objects.create(
                    effect_name=effect_name,
                    effect_description=effect_description,
                    user=request.user
                )
                effect.audio_file.save(f"effect_{effect.id}.mp3", File(f), save=True)
            print(f"💾 사운드 이팩트 라이브러리에 저장 완료: {effect.id}")

        # 파일 읽어서 반환
        with open(temp_path, "rb") as f:
            audio_data = f.read()

        # 임시 파일 삭제
        os.remove(temp_path)

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

        # 배경음 생성
        audio_stream = background_music(music_name, music_description, duration_seconds)

        if not audio_stream:
            return JsonResponse({"success": False, "error": "배경음 생성 API 호출에 실패했습니다."}, status=500)

        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
            for chunk in audio_stream:
                if chunk:  # chunk가 None이 아닌지 확인
                    temp_file.write(chunk)

        print(f"✅ 배경음 생성 완료: {temp_path}")

        # 라이브러리에 저장
        if save_to_library and request.user.is_authenticated:
            with open(temp_path, 'rb') as f:
                music = BackgroundMusicLibrary.objects.create(
                    music_name=music_name,
                    music_description=music_description,
                    duration_seconds=duration_seconds,
                    user=request.user
                )
                music.audio_file.save(f"music_{music.id}.mp3", File(f), save=True)
            print(f"💾 배경음 라이브러리에 저장 완료: {music.id}")

        # 파일 읽어서 반환
        with open(temp_path, "rb") as f:
            audio_data = f.read()

        # 임시 파일 삭제
        os.remove(temp_path)

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


# 책 상세보기
def book_detail(request, book_id):
    from book.models import BookReview, BookComment, ReadingProgress, AuthorAnnouncement
    from django.db.models import Avg, Prefetch
    from django.core.paginator import Paginator

    # ✅ 쿼리 최적화: select_related, prefetch_related 적용
    book = get_object_or_404(
        Books.objects.select_related('user').prefetch_related(
            'genres',
            'tags',
            Prefetch('contents', queryset=Content.objects.all().order_by('-number'))
        ),
        id=book_id
    )

    # 컨텐츠 가져오기
    contents = book.contents.all().order_by('-number')

    paginator = Paginator(contents, 10)
    page = request.GET.get('page')
    contents_page = paginator.get_page(page)

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

    context = {
        "book": book,
        "contents": contents_page,
        "avg_rating": round(avg_rating, 1),
        "review_count": review_count,
        "user_review": user_review,
        "recent_reviews": recent_reviews,
        "comments": comments,
        "reading_progress": reading_progress,
        "announcements": announcements,
    }

    return render(request, "book/book_detail.html", context)


# 내 작품 관리
@login_required
def my_books(request):
    # ✅ 쿼리 최적화: prefetch_related 적용
    books = Books.objects.filter(user=request.user).prefetch_related(
        'genres',
        'tags'
    ).order_by('-created_at')

    context = {
        "books": books,
    }
    return render(request, "book/my_books.html", context)


# 책 삭제
@login_required
@require_POST
def delete_book(request, book_id):
    book = get_object_or_404(Books, id=book_id, user=request.user)
    book.delete()
    return JsonResponse({"success": True})


# 에피소드 상세보기
def content_detail(request, content_id):
    from book.models import Content, ReadingProgress, ListeningHistory, AuthorAnnouncement
    from django.utils import timezone

    content = get_object_or_404(Content, id=content_id)
    book = content.book

    # 이전/다음 에피소드
    prev_content = Content.objects.filter(book=book, number__lt=content.number).order_by('-number').first()
    next_content = Content.objects.filter(book=book, number__gt=content.number).order_by('number').first()

    # 마지막 재생 위치 가져오기
    last_position = 0
    if request.user.is_authenticated:
        listening_history = ListeningHistory.objects.filter(
            user=request.user,
            content=content
        ).first()

        if listening_history:
            last_position = listening_history.last_position

    # 작가 공지사항 가져오기
    announcements = AuthorAnnouncement.objects.filter(book=book).select_related('author')[:3]

    # 로그인한 사용자의 독서 진행 상황 자동 업데이트
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

        # 현재 콘텐츠가 이미 읽은 것보다 뒤에 있거나 같으면 업데이트
        if content.number >= progress.last_read_content_number:
            progress.last_read_content_number = content.number
            progress.current_content = content
            progress.last_read_at = timezone.now()  # 마지막 읽은 시간 업데이트

            # 마지막 에피소드를 읽으면 완독 처리
            total_contents = book.contents.count()
            if content.number >= total_contents:
                progress.status = 'completed'
                progress.completed_at = timezone.now()
            else:
                # 완독이 아니면 읽는 중으로 상태 변경
                progress.status = 'reading'

            progress.save()

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
def save_listening_history(request, content_id):
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

        content = get_object_or_404(Content, id=content_id)
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
@csrf_exempt
@require_POST
def update_listening_position_api(request):
    from book.models import Content, ListeningHistory
    from register.models import Users
    from django.utils import timezone
    import json

    try:
        data = json.loads(request.body)
        api_key = data.get('api_key')
        book_id = data.get('book_id')
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

        # Content 확인
        content = get_object_or_404(Content, id=content_id)

        # 청취 기록 생성 또는 업데이트
        listening_history, created = ListeningHistory.objects.get_or_create(
            user=user,
            book_id=book_id,
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
def submit_review(request, book_id):
    from book.models import BookReview
    from django.db.models import Avg

    try:
        book = get_object_or_404(Books, id=book_id)
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

        return JsonResponse({
            'success': True,
            'message': '리뷰가 등록되었습니다.' if created else '리뷰가 수정되었습니다.',
            'avg_rating': float(book.book_score),
            'review_count': book.reviews.count()
        })
    except Exception as e:
        print(f"❌ 리뷰 제출 오류: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# 책 댓글 작성
@login_required
@require_POST
def submit_book_comment(request, book_id):
    from book.models import BookComment

    book = get_object_or_404(Books, id=book_id)
    comment_text = request.POST.get('comment', '').strip()
    parent_id = request.POST.get('parent_id', None)

    if not comment_text:
        return JsonResponse({'error': '댓글 내용을 입력해주세요.'}, status=400)

    parent = None
    if parent_id:
        parent = BookComment.objects.get(id=parent_id)

    comment = BookComment.objects.create(
        user=request.user,
        book=book,
        comment=comment_text,
        parent=parent
    )

    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'user': comment.user.nickname,
            'comment': comment.comment,
            'created_at': comment.created_at.strftime('%Y.%m.%d %H:%M'),
            'is_reply': parent is not None
        }
    })


# 미리듣기 페이지
def preview_page(request):
    book_id = request.GET.get("book_id")
    book = get_object_or_404(Books, id=book_id) if book_id else None

    if not book:
        return redirect("book:book_profile")

    from book.models import Content
    latest_episode = Content.objects.filter(book=book).order_by('-number').first()
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


# book/views.py

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import BookSnap, BookSnapComment
from django.core.paginator import Paginator
import random

# 북 스냅 리스트 페이지
def book_snap_list(request):
    # 첫 번째 스냅으로 리디렉션 (유튜브 쇼츠 스타일)
    first_snap = BookSnap.objects.first()
    if first_snap:
        return redirect('book:book_snap_detail', snap_id=first_snap.id)

    # 스냅이 없으면 빈 페이지
    return render(request, "book/snap/snap.html", {"no_snaps": True})

# 개인 북 스냅 리스트 페이지
def my_book_snap_list(request):
    if not request.user.is_authenticated:
        return render(request, "book/snap/my_snap.html", {"error": "로그인이 필요합니다."})
    
    snap_list = BookSnap.objects.filter(user=request.user).order_by('-created_at')

    context = {
        "book_snap_list": snap_list,
    }

    return render(request, "book/snap/my_snap.html", context)

import re  # 정규식으로 id 추출

def create_book_snap(request):
    if not request.user.is_authenticated:
        return render(request, "book/snap/create_snap.html", {"error": "로그인이 필요합니다."})

    user = request.user
    # (URL, 책 이름) 튜플 리스트 - 그대로 유지
    select_link = [
        (f"/book/detail/{book.id}/", book.name)
        for book in Books.objects.filter(user=user)
    ]

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        image = request.FILES.get("image")
        video = request.FILES.get("video")

        # select에서 선택한 책 링크 (URL)
        selected_link = request.POST.get("book_link", "").strip()
        # 직접 입력한 URL
        custom_link = request.POST.get("link", "").strip()

        final_link = selected_link or custom_link

        # book 객체 찾기
        book_obj = None
        if final_link:
            # URL에서 book.id 추출 (예: /book/detail/123/ → 123)
            match = re.search(r'/book/detail/(\d+)/?', final_link)
            if match:
                book_id = match.group(1)
                try:
                    book_obj = Books.objects.get(id=book_id)
                except Books.DoesNotExist:
                    pass  # 없으면 None

        if not title or not description or not image:
            context = {
                "error": "모든 필드를 입력해주세요.",
                "select_link": select_link
            }
            return render(request, "book/snap/create_snap.html", context)

        # 스냅 생성
        snap = BookSnap.objects.create(
            user=user,
            snap_title=title,
            book_comment=description,
            thumbnail=image,
            snap_video=video,
            book=book_obj,          # ← 여기! book 객체 저장
            book_link=final_link    # URL은 그대로 저장
        )

        return redirect("book:my_book_snap_list")

    return render(request, "book/snap/create_snap.html", {"select_link": select_link})

# 북 스냅 수정
import re  

@login_required
def edit_snap(request, snap_id):
    snap = get_object_or_404(BookSnap, id=snap_id)

    # 작성자만 수정 가능
    if snap.user != request.user:
        return redirect("book:my_book_snap_list")

    user = request.user
    # (URL, 책 이름) 튜플 리스트 - 그대로 유지
    select_link = [
        (f"/book/detail/{book.id}/", book.name)
        for book in Books.objects.filter(user=user)
    ]

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        image = request.FILES.get("image")
        video = request.FILES.get("video")
        selected_link = request.POST.get("book_link", "").strip()
        custom_link = request.POST.get("link", "").strip()

        final_link = selected_link or custom_link

        if not title or not description:
            context = {
                "error": "제목과 설명을 입력해주세요.",
                "select_link": select_link,
                "snap": snap
            }
            return render(request, "book/snap/edit_snap.html", context)

        # book 객체 찾기
        book_obj = None
        if final_link:
            # URL에서 book.id 추출 (예: /book/detail/123/ → 123)
            match = re.search(r'/book/detail/(\d+)/?', final_link)
            if match:
                book_id = match.group(1)
                try:
                    book_obj = Books.objects.get(id=book_id)
                except Books.DoesNotExist:
                    pass  # 없으면 None

        # 업데이트
        snap.snap_title = title
        snap.book_comment = description
        snap.book_link = final_link
        snap.book = book_obj  # ← 핵심! book 객체 저장

        if image:
            snap.thumbnail = image
        if video:
            snap.snap_video = video

        snap.save()

        return redirect("book:my_book_snap_list")

    context = {
        "snap": snap,
        "select_link": select_link
    }
    return render(request, "book/snap/edit_snap.html", context)


# 북 스냅 삭제
@login_required
def delete_snap(request, snap_id):
    snap = get_object_or_404(BookSnap, id=snap_id)

    # 작성자만 삭제 가능
    if snap.user != request.user:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    snap.delete()
    return redirect("book:my_book_snap_list")


# 북 스냅 상세 페이지 (유튜브 쇼츠 스타일)
def book_snap_detail(request, snap_id):
    snap = get_object_or_404(BookSnap, id=snap_id)

    # 모든 스냅 ID 리스트 가져오기
    all_snap_ids = list(BookSnap.objects.values_list('id', flat=True).order_by('id'))

    # 현재 스냅의 인덱스 찾기
    try:
        current_index = all_snap_ids.index(snap_id)
    except ValueError:
        current_index = 0

    # 이전/다음 스냅 ID 찾기
    prev_snap_id = all_snap_ids[current_index - 1] if current_index > 0 else None
    next_snap_id = all_snap_ids[current_index + 1] if current_index < len(all_snap_ids) - 1 else None

    # 댓글 가져오기
    comments = snap.comments.filter(parent=None).order_by('-created_at')

    context = {
        "snap": snap,
        "prev_snap_id": prev_snap_id,
        "next_snap_id": next_snap_id,
        "comments": comments,
        "total_snaps": len(all_snap_ids),
        "current_position": current_index + 1,
    }
    return render(request, "book/snap/snap_detail.html", context)


# 좋아요 API
@csrf_exempt
def book_snap_like(request, snap_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    
    snap = get_object_or_404(BookSnap, id=snap_id)
    user = request.user

    if user in snap.booksnap_like.all():
        snap.booksnap_like.remove(user)
        liked = False
    else:
        snap.booksnap_like.add(user)
        liked = True

    return JsonResponse({"likes": snap.booksnap_like.count(), "liked": liked})


# 조회수 증가 API
@csrf_exempt
def book_snap_view_count(request, snap_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    snap = get_object_or_404(BookSnap, id=snap_id)
    user = request.user

    # 조회수 중복 방지
    if user not in snap.viewed_users.all():
        snap.views += 1
        snap.viewed_users.add(user.id)
        snap.save()

    return JsonResponse({"views": snap.views})


# 댓글 작성 API
@csrf_exempt
def book_snap_comment(request, snap_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    content = request.POST.get("content")
    parent_id = request.POST.get("parent_id")

    if not content:
        return JsonResponse({"error": "댓글 내용 없음"}, status=400)

    snap = get_object_or_404(BookSnap, id=snap_id)

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
        book_id = request.POST.get("book_id")
        user_msg = request.POST.get("message")

        if not book_id or not user_msg:
            return JsonResponse({"error": "필수 데이터 누락"}, status=400)

        # 책 존재 확인
        try:
            Books.objects.get(id=book_id)
        except Books.DoesNotExist:
            return JsonResponse({"error": "책을 찾을 수 없음"}, status=404)

        # AI 함수 호출 (현재 MOCK)
        try:
            result = chat_with_character(book_id=book_id, message=user_msg)
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

@login_required
def author_dashboard(request):
    import json
    from django.db.models import Count, Sum, Avg
    from datetime import datetime, timedelta
    from book.models import ReadingProgress, ListeningHistory, Books

    # 로그인한 작가의 책들
    user_books = Books.objects.filter(user=request.user).prefetch_related('contents').order_by("-created_at")

    # 기본 통계
    total_books = user_books.count()
    total_contents = sum(book.contents.count() for book in user_books)
    total_audio_duration = request.user.get_total_audiobook_duration_formatted()

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
        total_ep = book.contents.count()
        avg_progress_percent = round((avg_progress / total_ep * 100) if total_ep else 0, 1)

        # ------------------------------
        # 📌 템플릿용 데이터
        # ------------------------------
        book_stats.append({
            "book": book,
            "reader_count": reader_count,
            "gender_data": gender_data,
            "age_data": age_data,
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
            "gender_data": gender_data,
            "age_data": age_data,
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

    context = {
        "total_books": total_books,
        "total_contents": total_contents,
        "total_audio_duration": total_audio_duration,
        "total_readers": total_readers,
        "recent_readers": recent_readers,
        "book_stats": book_stats,
        "book_stats_json": json.dumps(book_stats_json),
    }

    return render(request, "book/author_dashboard.html", context)



@csrf_exempt
def toggle_status(request, book_id):
    if request.method == "POST":
        book = get_object_or_404(Books, id=book_id)
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
def create_announcement(request, book_id):
    from book.models import AuthorAnnouncement
    book = get_object_or_404(Books, id=book_id)

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

        return redirect("book:book_detail", book_id=book.id)

    return redirect("book:book_detail", book_id=book.id)


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

        return redirect("book:book_detail", book_id=announcement.book.id)

    return redirect("book:book_detail", book_id=announcement.book.id)


# 공지사항 삭제
@login_required
def delete_announcement(request, announcement_id):
    from book.models import AuthorAnnouncement
    announcement = get_object_or_404(AuthorAnnouncement, id=announcement_id)

    # 작가만 삭제 가능
    if request.user != announcement.author:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    book_id = announcement.book.id
    announcement.delete()

    return redirect("book:book_detail", book_id=book_id)


# 에피소드 삭제 (작가만)
@login_required
def delete_content(request, content_id):
    from book.models import Content
    content = get_object_or_404(Content, id=content_id)
    book = content.book

    # 작가만 삭제 가능
    if request.user != book.user:
        return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

    if request.method == "POST":
        content.delete()

        # 회차 번호 재정렬
        remaining_contents = book.contents.all().order_by('number')
        for idx, c in enumerate(remaining_contents, start=1):
            c.number = idx
            c.save()

        return redirect("book:book_detail", book_id=book.id)

    return redirect("book:book_detail", book_id=book.id)


# 에피소드 순서 변경
@login_required
@require_POST
def reorder_content(request, book_id):
    from book.models import Content
    import json

    try:
        book = get_object_or_404(Books, id=book_id)

        # 작가만 순서 변경 가능
        if request.user != book.user:
            return JsonResponse({"success": False, "error": "권한이 없습니다."}, status=403)

        data = json.loads(request.body)
        content_ids = data.get('content_ids', [])

        if not content_ids:
            return JsonResponse({"success": False, "error": "에피소드 ID가 없습니다."}, status=400)

        # 새로운 순서대로 회차 번호 업데이트
        for new_number, content_id in enumerate(content_ids, start=1):
            content = Content.objects.filter(id=content_id, book=book).first()
            if content:
                content.number = new_number
                content.save()

        return JsonResponse({"success": True, "message": "순서가 변경되었습니다."})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# 북마크/메모 생성/수정
@login_required
@require_POST
def save_bookmark(request, content_id):
    from book.models import ContentBookmark, Content
    import json

    try:
        data = json.loads(request.body)
        position = float(data.get('position', 0))
        memo = data.get('memo', '').strip()

        if position < 0:
            return JsonResponse({'success': False, 'error': '위치가 올바르지 않습니다.'}, status=400)

        content = get_object_or_404(Content, id=content_id)

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
def get_bookmarks(request, content_id):
    from book.models import ContentBookmark

    try:
        bookmarks = ContentBookmark.objects.filter(
            user=request.user,
            content_id=content_id
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

