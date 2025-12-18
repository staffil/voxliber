from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse,HttpResponse,HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from book.models import Books, ReadingProgress, Content, MyVoiceList, Books
from book.utils import generate_tts
from django.conf import settings


@login_required
def my_profile(request):
    user = request.user
    books = Books.objects.filter(user=user).order_by('-created_at')
    books_count = books.count()

    if request.method == "POST":
        nickname = request.POST.get("nickname", "").strip()
        username = request.POST.get("username", "").strip()
        gender = request.POST.get("gender", "O")
        birthdate = request.POST.get("birthdate") or None
        age = request.POST.get("age")
        remove_avatar = request.POST.get("remove_avatar") == "true"
        remove_cover = request.POST.get("remove_cover") == "true"

        # 닉네임 업데이트 (필수)
        if nickname:
            user.nickname = nickname
        else:
            messages.error(request, "닉네임을 입력해주세요.")
            context = {"books_count": books_count}
            return render(request, "mypage/my_profile.html", context)

        # 사용자명 업데이트
        if username:
            user.username = username

        # 성별 업데이트
        if gender in ["M", "F", "O"]:
            user.gender = gender

        # 생년월일 업데이트
        user.birthdate = birthdate

        # 나이 업데이트
        if age:
            try:
                user.age = int(age)
            except ValueError:
                pass

        # 프로필 이미지 삭제
        if remove_avatar:
            user.user_img = None

        # 프로필 이미지 업데이트
        if "user_img" in request.FILES:
            user.user_img = request.FILES["user_img"]

        # 커버 이미지 삭제
        if remove_cover:
            user.cover_img = None

        # 커버 이미지 업데이트
        if "cover_img" in request.FILES:
            user.cover_img = request.FILES["cover_img"]

        user.save()
        messages.success(request, "프로필이 성공적으로 업데이트되었습니다.")
        return redirect("mypage:my_profile")

    context = {
        "books_count": books_count,
        "books": books,
    }
    return render(request, "mypage/my_profile.html", context)


@login_required
def my_profile_update(request):
    user = request.user

    if request.method == "POST":
        nickname = request.POST.get("nickname", "").strip()
        username = request.POST.get("username", "").strip()
        gender = request.POST.get("gender", "O")
        birthdate = request.POST.get("birthdate") or None
        age = request.POST.get("age")
        remove_avatar = request.POST.get("remove_avatar") == "true"
        remove_cover = request.POST.get("remove_cover") == "true"

        # 닉네임 업데이트 (필수)
        if nickname:
            user.nickname = nickname
        else:
            messages.error(request, "닉네임을 입력해주세요.")
            return render(request, "mypage/my_profile_update.html")

        # 사용자명 업데이트
        if username:
            user.username = username

        # 성별 업데이트
        if gender in ["M", "F", "O"]:
            user.gender = gender

        # 생년월일 업데이트
        user.birthdate = birthdate

        # 나이 업데이트
        if age:
            try:
                user.age = int(age)
            except ValueError:
                pass

        # 프로필 이미지 삭제
        if remove_avatar:
            user.user_img = None

        # 프로필 이미지 업데이트
        if "user_img" in request.FILES:
            user.user_img = request.FILES["user_img"]

        # 커버 이미지 삭제
        if remove_cover:
            user.cover_img = None

        # 커버 이미지 업데이트
        if "cover_img" in request.FILES:
            user.cover_img = request.FILES["cover_img"]

        user.save()
        messages.success(request, "프로필이 성공적으로 업데이트되었습니다.")
        return redirect("mypage:my_profile")

    return render(request, "mypage/my_profile_update.html")


@login_required
def my_library(request):
    user = request.user

    filter_status = request.GET.get('status', 'all')

    # 모든 읽기 진행 상황 가져오기
    all_progress = ReadingProgress.objects.filter(user=user).select_related(
        'book', 'current_content'
    ).prefetch_related('book__contents', 'book__genres').order_by('-last_read_at')

    # current_content가 None이면 첫 번째 콘텐츠로 채워주기
    for p in all_progress:
        if not p.current_content:
            p.current_content = p.book.contents.first()

    # 동적 상태 기반 필터링
    if filter_status == 'reading':
        reading_progress_list = [p for p in all_progress if p.get_reading_status() == 'reading']
    elif filter_status == 'completed':
        reading_progress_list = [p for p in all_progress if p.get_reading_status() == 'completed']
    elif filter_status == 'favorite':
        reading_progress_list = [p for p in all_progress if p.is_favorite]
    else:
        reading_progress_list = list(all_progress)

    # 동적 상태 기반 통계 계산
    reading_count = sum(1 for p in all_progress if p.get_reading_status() == 'reading')
    completed_count = sum(1 for p in all_progress if p.get_reading_status() == 'completed')

    stats = {
        'total': all_progress.count(),
        'reading': reading_count,
        'completed': completed_count,
        'favorite': all_progress.filter(is_favorite=True).count(),
    }

    context = {
        'reading_progress_list': reading_progress_list,
        'filter_status': filter_status,
        'stats': stats,
    }

    return render(request, "mypage/my_library.html", context)


# API: 내 서재 데이터 (JSON)
@require_GET
def api_my_library(request):
    from book.models import APIKey

    # API Key로 사용자 인증
    api_key = request.GET.get('api_key')
    if not api_key:
        return JsonResponse({'error': 'API key is required'}, status=401)

    try:
        api_key_obj = APIKey.objects.get(key=api_key, is_active=True)
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return JsonResponse({'error': 'Invalid API key'}, status=401)

    filter_status = request.GET.get('status', 'all')

    # 모든 읽기 진행 상황 가져오기
    all_progress = ReadingProgress.objects.filter(user=user).select_related(
        'book', 'current_content'
    ).prefetch_related('book__contents', 'book__genres', 'book__user').order_by('-last_read_at')

    # current_content가 None이면 첫 번째 콘텐츠로 채워주기
    for p in all_progress:
        if not p.current_content:
            p.current_content = p.book.contents.first()

    # 동적 상태 기반 필터링
    if filter_status == 'reading':
        reading_progress_list = [p for p in all_progress if p.get_reading_status() == 'reading']
    elif filter_status == 'completed':
        reading_progress_list = [p for p in all_progress if p.get_reading_status() == 'completed']
    elif filter_status == 'favorite':
        reading_progress_list = [p for p in all_progress if p.is_favorite]
    else:
        reading_progress_list = list(all_progress)

    # 동적 상태 기반 통계 계산
    reading_count = sum(1 for p in all_progress if p.get_reading_status() == 'reading')
    completed_count = sum(1 for p in all_progress if p.get_reading_status() == 'completed')

    # JSON 응답 데이터
    books_data = []
    for progress in reading_progress_list:
        book = progress.book
        books_data.append({
            'id': book.id,
            'name': book.name,
            'description': book.description,
            'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
            'author': book.user.nickname if book.user else '',
            'author_id': book.user.user_id if book.user else None,
            'genres': [{'id': g.id, 'name': g.name} for g in book.genres.all()],
            'created_at': book.created_at.isoformat() if book.created_at else None,
            'reading_progress': {
                'status': progress.get_reading_status(),
                'last_read_content_number': progress.last_read_content_number,
                'progress_percentage': progress.get_progress_percentage(),
                'is_favorite': progress.is_favorite,
                'last_read_at': progress.last_read_at.isoformat() if progress.last_read_at else None,
                'started_at': progress.started_at.isoformat() if progress.started_at else None,
                'completed_at': progress.completed_at.isoformat() if progress.completed_at else None,
            },
        })

    return JsonResponse({
        'books': books_data,
        'stats': {
            'total': all_progress.count(),
            'reading': reading_count,
            'completed': completed_count,
            'favorite': all_progress.filter(is_favorite=True).count(),
        },
        'filter_status': filter_status,
    })



@login_required
@require_POST
def update_reading_progress(request):
    try:
        book_id = request.POST.get('book_id')
        content_number = request.POST.get('content_number')
        status = request.POST.get('status', 'reading')
        is_favorite = request.POST.get('is_favorite') == 'true'

        if not book_id:
            return JsonResponse({'success': False, 'error': '책 ID가 필요합니다.'}, status=400)

        book = get_object_or_404(Books, id=book_id)

        progress, created = ReadingProgress.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={
                'status': status,
                'is_favorite': is_favorite,
            }
        )

        if content_number:
            progress.last_read_content_number = int(content_number)
            try:
                current_content = Content.objects.get(book=book, number=content_number)
                progress.current_content = current_content
            except Content.DoesNotExist:
                pass

        progress.status = status
        progress.is_favorite = is_favorite

        if status == 'completed':
            progress.completed_at = timezone.now()
            total_contents = book.contents.count()
            progress.last_read_content_number = total_contents

        progress.save()

        return JsonResponse({
            'success': True,
            'progress_percentage': progress.get_progress_percentage(),
            'message': '독서 진행 상황이 업데이트되었습니다.'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    



@login_required
@require_POST
def delete_my_voice(request, pk):
    item = get_object_or_404(MyVoiceList, id=pk, user=request.user)
    item.delete()

    # AJAX 요청이면 JSON 반환
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': '목소리가 삭제되었습니다.'})

    return redirect("voice:voice_list")



@login_required
@require_POST
def toggle_favorite(request, pk):
    voice = get_object_or_404(MyVoiceList, pk=pk, user=request.user)
    voice.is_favorite = not voice.is_favorite  # 토글
    voice.save()

    # AJAX 요청이면 JSON 반환
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_favorite': voice.is_favorite,
            'message': '즐겨찾기가 업데이트되었습니다.'
        })

    return redirect("voice:voice_list")


@login_required
@require_POST
def select_book(request, pk):
    voice = get_object_or_404(MyVoiceList, id=pk, user=request.user)

    book_id = request.POST.get("book_id")
    if book_id:
        book = get_object_or_404(Books, id=book_id, user=request.user)
        voice.book = book
        book_name = book.name
    else:
        voice.book = None
        book_name = "전체 작품"
    voice.save()

    # AJAX 요청이면 JSON 반환
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'book_name': book_name,
            'message': '책이 선택되었습니다.'
        })

    return redirect("voice:voice_list")



import os
from book.models import Poem_list
# 시 리스트
def poem_list(request):
    user = request.user
    poem_list = Poem_list.objects.filter(user=user).order_by("-created_at")

    context  ={
        "poem_list":poem_list
    }
    return render(request,"mypage/poem/poem_list.html", context)

from django.core.files.base import ContentFile


def poem_create(request):
    my_voice_list = MyVoiceList.objects.filter(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        title = request.POST.get("title")
        content = request.POST.get("content")
        voice_id = request.POST.get("voice")
        poem_img = request.FILES.get('cover_image')


        # ✨ 시 제출하기
        if action == "submit_poem":
            # TTS 생성 → 파일 경로 리턴
            audio_path = generate_tts(
                novel_text=content,
                voice_id=voice_id,
                language_code="ko",
                speed_value=1.0
            )

            poem = Poem_list.objects.create(
                user=request.user,
                title=title,
                content=content,
                is_public=True,
                status="submitted",
                image= poem_img
            )
            if audio_path and os.path.exists(audio_path):
                with open(audio_path, 'rb') as f:
                    poem.poem_audio.save(
                        f"poem_{request.user.user_id}_{int(timezone.now().timestamp())}.mp3",
                        ContentFile(f.read()),
                        save=True
                    )

            return redirect("mypage:poem_list")

    return render(request, "mypage/poem/poem_create.html", {
        "my_voice_list": my_voice_list
    })



def poem_detail(request, pk):
    poem = get_object_or_404(Poem_list, pk=pk, user=request.user)

    if request.method == "POST":
        poem.title = request.POST.get("title", poem.title)
        poem.content = request.POST.get("content", poem.content)
        poem.save()
        return redirect("mypage:poem_detail", pk=pk)

    return render(request, "mypage/poem/poem_detail.html", {"poem": poem})


def poem_update(request, pk):
    poem = get_object_or_404(Poem_list, pk=pk, user=request.user)

    if request.method == "POST":
        form = Poem_list(request.POST, instance=poem)
        if form.is_valid():
            form.save()
            return redirect("mypage:poem_detail", pk=pk)
    else:
        form = Poem_list(instance=poem)

    return render(request, "mypage/poem/poem_update.html", {"form": form, "poem": poem})


def poem_delete(request, pk):
    poem = get_object_or_404(Poem_list, pk=pk, user=request.user)
    poem.delete()
    return redirect("mypage:poem_list")


# views.py
from django.shortcuts import get_object_or_404, redirect, render
from book.models import BookSnippet
import time
def book_snippet_form(request, book_id):
    book = get_object_or_404(Books, id=book_id)
    
    # 이미 스니펫이 있으면 수정 모드
    snippet = BookSnippet.objects.filter(book=book).first()
    my_voice_list = MyVoiceList.objects.filter(user=request.user)

    if request.method == 'POST':
        action = request.POST.get("action")
        sentence = request.POST.get('sentence', '').strip()
        voice_id = request.POST.get("voice")

        audio_file = None

        # TTS 생성
        if action == "submit_poem" and sentence:
            tts_path = generate_tts(
                novel_text=sentence,
                voice_id=voice_id,
                language_code="ko",
                speed_value=1.0
            )

            if tts_path and os.path.exists(tts_path):
                # ContentFile로 읽어서 FileField에 저장 가능하게 변환
                with open(tts_path, 'rb') as f:
                    audio_file = ContentFile(
                        f.read(),
                        name=f"snippet_{book.id}_{int(time.time())}.mp3"
                    )

        # 기존 스니펫 수정
        if snippet:
            snippet.sentence = sentence
            snippet.save()  # 일단 sentence 저장
            if audio_file:
                snippet.audio_file.save(audio_file.name, audio_file, save=True)
        else:
            # 새 스니펫 생성
            snippet = BookSnippet.objects.create(
                book=book,
                sentence=sentence,
                link=f"http://127.0.0.1:8000/book/detail/{book_id}/"
            )
            if audio_file:
                snippet.audio_file.save(audio_file.name, audio_file, save=True)

        return redirect('mypage:my_profile')  # 작성/수정 후 이동

    # GET 요청 → 작성 또는 수정 화면 렌더
    context = {
        'book': book,
        'snippet': snippet,
        'my_voice_list': my_voice_list
    }
    return render(request, 'mypage/snippet/snippet_detail.html', context)