from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from book.models import Books, ReadingProgress, Content, MyVoiceList, BackgroundMusicLibrary, VoiceList, ListeningHistory
from book.utils import generate_tts, merge_audio_files, mix_audio_with_background
from django.conf import settings
import re
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth, TruncWeek, TruncDate, TruncYear
from datetime import datetime, timedelta
import json
from register.decorator import login_required_to_main
from register.models import Users

@login_required
@login_required_to_main
def my_profile(request):
    user = request.user
    books = Books.objects.filter(user=user, is_deleted=False).order_by('-created_at')
    books_count = books.count()

    # =====================================================
    # 활동 통계 차트 데이터 (일/월/연도별)
    # =====================================================
    now = datetime.now()

    # ── 일별 (최근 30일) ──────────────────────────────
    thirty_days_ago = now - timedelta(days=30)

    tts_daily = (
        Content.objects
        .filter(book__user=user, created_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('duration_seconds'))
        .order_by('day')
    )
    listening_daily = (
        ListeningHistory.objects
        .filter(user=user, listened_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('listened_at'))
        .values('day')
        .annotate(total=Sum('listened_seconds'))
        .order_by('day')
    )

    # ── 월별 (최근 12개월) ────────────────────────────
    twelve_months_ago = now - timedelta(days=365)

    tts_monthly = (
        Content.objects
        .filter(book__user=user, created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('duration_seconds'))
        .order_by('month')
    )
    listening_monthly = (
        ListeningHistory.objects
        .filter(user=user, listened_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('listened_at'))
        .values('month')
        .annotate(total=Sum('listened_seconds'))
        .order_by('month')
    )

    # ── 연도별 (전체) ─────────────────────────────────
    tts_yearly = (
        Content.objects
        .filter(book__user=user)
        .annotate(year=TruncYear('created_at'))
        .values('year')
        .annotate(total=Sum('duration_seconds'))
        .order_by('year')
    )
    listening_yearly = (
        ListeningHistory.objects
        .filter(user=user)
        .annotate(year=TruncYear('listened_at'))
        .values('year')
        .annotate(total=Sum('listened_seconds'))
        .order_by('year')
    )

    # ── JSON 직렬화 ───────────────────────────────────
    chart_data = json.dumps({
        'daily': {
            'tts': {
                'labels': [x['day'].strftime('%m/%d') for x in tts_daily],
                'data':   [round((x['total'] or 0) / 60, 1) for x in tts_daily],
            },
            'listening': {
                'labels': [x['day'].strftime('%m/%d') for x in listening_daily],
                'data':   [round((x['total'] or 0) / 60, 1) for x in listening_daily],
            },
        },
        'monthly': {
            'tts': {
                'labels': [x['month'].strftime('%y.%m') for x in tts_monthly],
                'data':   [round((x['total'] or 0) / 60, 1) for x in tts_monthly],
            },
            'listening': {
                'labels': [x['month'].strftime('%y.%m') for x in listening_monthly],
                'data':   [round((x['total'] or 0) / 3600, 1) for x in listening_monthly],
            },
        },
        'yearly': {
            'tts': {
                'labels': [str(x['year'].year) for x in tts_yearly],
                'data':   [round((x['total'] or 0) / 3600, 1) for x in tts_yearly],
            },
            'listening': {
                'labels': [str(x['year'].year) for x in listening_yearly],
                'data':   [round((x['total'] or 0) / 3600, 1) for x in listening_yearly],
            },
        },
    })

    # =====================================================
    # POST: 프로필 업데이트
    # =====================================================
    def _render(extra=None):
        return render(request, "mypage/my_profile.html", {
            "books_count": books_count,
            "books": books,
            "chart_data": chart_data,
        })

    if request.method == "POST":
        nickname = request.POST.get("nickname", "").strip()
        username = request.POST.get("username", "").strip()
        gender = request.POST.get("gender", "O")
        birthdate = request.POST.get("birthdate") or None
        age = request.POST.get("age")
        remove_avatar = request.POST.get("remove_avatar") == "true"
        remove_cover = request.POST.get("remove_cover") == "true"

        if not nickname:
            messages.error(request, "닉네임을 입력해주세요.")
            return _render()

        if Users.objects.filter(nickname=nickname).exclude(pk=user.pk).exists():
            messages.error(request, "현재 있는 닉네임입니다. 다른걸 선택해 주세요")
            return _render()

        user.nickname = nickname

        if username:
            user.username = username
        if gender in ["M", "F", "O"]:
            user.gender = gender

        user.birthdate = birthdate

        if age:
            try:
                user.age = int(age)
            except ValueError:
                pass

        if remove_avatar:
            user.user_img = None
        if "user_img" in request.FILES:
            user.user_img = request.FILES["user_img"]

        if remove_cover:
            user.cover_img = None
        if "cover_img" in request.FILES:
            user.cover_img = request.FILES["cover_img"]

        user.save()
        messages.success(request, "프로필이 성공적으로 업데이트되었습니다.")
        return redirect("mypage:my_profile")

    # =====================================================
    # GET
    # =====================================================
    from register.models import PaymentHistory, Subscription
    recent_payments = PaymentHistory.objects.filter(user=request.user)[:3]
    try:
        subscription = request.user.subscription
    except Subscription.DoesNotExist:
        subscription = None

    context = {
        "books_count": books_count,
        "books": books,
        "chart_data": chart_data,
        "recent_payments": recent_payments,
        "subscription": subscription,
    }
    return render(request, "mypage/my_profile.html", context)


@login_required_to_main
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
@login_required_to_main
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

    # API Key로 사용자 인증 (헤더 우선, GET 파라미터 폴백)
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
    if not api_key:
        return JsonResponse({'error': 'API key is required'}, status=401)

    try:
        api_key_obj = APIKey.objects.get(key=api_key, is_active=True)
        user = api_key_obj.user
    except APIKey.DoesNotExist:
        return JsonResponse({'error': 'Invalid API key'}, status=401)

    filter_status = request.GET.get('status', 'all')

    # 모든 읽기 진행 상황 가져오기 (오디오북 + 웹소설)
    all_progress = ReadingProgress.objects.filter(
        user=user
    ).select_related(
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
            'id': book.public_uuid,
            'name': book.name,
            'description': book.description,
            'cover_img': request.build_absolute_uri(book.cover_img.url) if book.cover_img else None,
            'author': {
                'id': book.user.user_id,
                'nickname': book.user.nickname,
                'email': book.user.email,
            } if book.user else None,
            'book_type': book.book_type,
            'genres': [{'id': g.id, 'name': g.name, 'color': g.genres_color} for g in book.genres.all()],
            'created_at': book.created_at.isoformat() if book.created_at else None,
            'reading_progress': {
                'status': progress.get_reading_status(),
                'last_read_content_number': progress.last_read_content_number,
                'progress_percentage': progress.get_progress_percentage(),
                'is_favorite': progress.is_favorite,
                'current_content_uuid': str(progress.current_content.public_uuid) if progress.current_content else None,
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




# views.py
from django.shortcuts import get_object_or_404, redirect, render
from book.models import BookSnippet
import time
@login_required_to_main
def book_snippet_form(request, book_uuid):
    book = get_object_or_404(Books, public_uuid=book_uuid)
    
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
                link=f"http://127.0.0.1:8000/book/detail/{book.public_uuid}/"
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

@login_required
def delete_account(request):
    """
    회원 탈퇴 (Soft Delete)
    계정을 비활성화하고 로그아웃합니다. 데이터는 보관됩니다.
    """
    if request.method == 'POST':
        user = request.user
        
        # 계정 비활성화 (Soft Delete)
        user.is_active = False
        user.save()
        
        # 로그아웃
        from django.contrib.auth import logout
        logout(request)
        
        # 메시지와 함께 홈으로 리다이렉트
        from django.contrib import messages
        messages.success(request, '회원 탈퇴가 완료되었습니다. 계정 복구를 원하시면 고객센터로 문의해주세요.')
        return redirect('main:main')
    
    # GET 요청은 확인 페이지로
    return render(request, 'mypage/delete_account_confirm.html')





@login_required_to_main
def my_book_list(request):
    user = request.user
    books = Books.objects.filter(user=user, is_deleted=False).order_by('-created_at')
    books_count = books.count()

    content ={
        "books_count": books_count,
        "books": books,
    }
    return render (request, "mypage/my_book_list.html", content)
