# main/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import requests
import json
import os
from uuid import uuid4
from django.conf import settings
from main.models import SnapBtn, Advertisment, Event
from book.models import Books,ReadingProgress, BookSnap, Content, BookTag, Tags, BookSnippet, ListeningHistory, GenrePlaylist
from voice.models import VoiceProfile
from book.service.recommendation import recommend_books
from django.db.models import Max
import random
from register.decorator import login_required_to_main
from rest_framework.decorators import api_view, permission_classes
from book.api_utils import require_api_key, paginate, api_response, require_api_key_secure
from book.models import Genres
from register.models import Users
from django.db.models import Count, Max, Sum
from django.utils import timezone
from datetime import timedelta



# Colab API URL
COLAB_TTS_URL = "https://dolabriform-intense-jameson.ngrok-free.dev"




def main(request):
    """메인 페이지"""

    # 뉴스/배너
    news_list = SnapBtn.objects.all()[:5]
    advertisment_list = Advertisment.objects.all()

   

    

    # 배너용 책 (최신 4권, 날짜 제한 없음)
    banner_books = list(Books.objects.filter(
        book_type='audiobook', is_deleted=False
    ).select_related('user').prefetch_related('genres').order_by('-created_at')[:4])

    # 📌 신작 (최근 30일 이내 생성된 책, 최신 콘텐츠 기준 정렬)
    # 최신 에피소드 업데이트 기준 정렬 (책 생성일 무관)
    new_books = list(Books.objects.filter(
        book_type='audiobook', is_deleted=False
    ).annotate(
        last_content_time=Max('contents__created_at')
    ).filter(last_content_time__isnull=False).select_related('user').prefetch_related('genres').order_by('-last_content_time')[:20])

    # 🔥 인기 작품 (평점과 에피소드 수를 고려한 종합 점수)
    _popular_pool = list(Books.objects.filter(
        book_type='audiobook', is_deleted=False
    ).select_related('user').prefetch_related('genres').annotate(
        total_listened=Sum('listening_stats__listened_seconds'),
        listener_count=Count('listening_stats__user', distinct=True),
    ).order_by('-listener_count', '-total_listened')[:40])
    random.shuffle(_popular_pool)
    popular_books = _popular_pool[:12]

    # 🏆 최고 평점 작품 (리뷰가 최소 1개 이상)
    _top_pool = list(Books.objects.filter(
        book_type='audiobook', is_deleted=False, book_score__gt=0
    ).select_related('user').prefetch_related('genres').order_by('-book_score')[:30])
    random.shuffle(_top_pool)
    top_rated_books = _top_pool[:8]

    # ⚡ 트렌딩 작품 (최근 인기작 - 평점과 에피소드 수 기준)
    seven_days_ago = timezone.now() - timedelta(days=7)
    _trending_pool = list(Books.objects.filter(
        book_type='audiobook', is_deleted=False, created_at__lte=seven_days_ago
    ).select_related('user').prefetch_related('genres').annotate(
        episode_count=Count('contents')
    ).order_by('-book_score', '-episode_count')[:30])
    random.shuffle(_trending_pool)
    trending_books = _trending_pool[:8]

    # 👑 인기 작가 (작품 수와 평균 평점 고려)
    popular_authors = Users.objects.annotate(
        book_count=Count('books'),
        avg_score=Sum('books__book_score') / Count('books')
    ).filter(book_count__gt=0).order_by('-avg_score', '-book_count')[:8]

    # 📚 장르별 큐레이션 (각 장르당 상위 6개 작품)
    genres_with_books = []
    all_genres = Genres.objects.order_by('?')[:6]  # 상위 6개 장르만

    for genre in all_genres:
        genre_books = Books.objects.filter(
            book_type='audiobook',
            genres=genre, 
            is_deleted =False
        ).select_related('user').prefetch_related('genres').order_by('-book_score', '-created_at')[:6]

        if genre_books.exists():
            genres_with_books.append({
                'genre': genre,
                'books': genre_books
            })

    # 🎯 추천 시스템 (로그인 유저 기반)
    recommended_books = []
    if request.user.is_authenticated:
        # 사용자가 본 책의 장르 수집
        from book.models import ListeningHistory

        # 사용자가 본 책들 가져오기 (리스트로 변환)
        listened_books = list(ListeningHistory.objects.filter(
            user=request.user
        ).values_list('book_id', flat=True).distinct())

        if listened_books:
            # 해당 책들의 장르 가져오기 (리스트로 변환)
            user_genres = list(Genres.objects.filter(
                books__id__in=listened_books
            ).distinct()[:3])

            if user_genres:
                # 해당 장르의 책 중 아직 보지 않은 책 추천
                recommended_books = Books.objects.filter(book_type='audiobook',
                    genres__in=user_genres,             is_deleted =False

                ).exclude(
                    id__in=listened_books
                ).select_related('user').prefetch_related('genres').distinct().order_by('-book_score')[:9]

    from book.models import ListeningHistory

    if request.user.is_authenticated:
        qs = ListeningHistory.objects.filter(
            user=request.user,
            last_position__gt=0
        ).select_related('book', 'content').order_by('-last_listened_at')

        seen_books = set()
        recent_listening = []
        for lh in qs:
            if lh.book_id not in seen_books:
                recent_listening.append(lh)
                seen_books.add(lh.book_id)
            if len(recent_listening) >= 5:
                break
    else:
        recent_listening = []


    # 모든 장르 (필터용)
    genres_list = Genres.objects.all()[:10]

    # 오디오 리스트
    audio_list = Books.objects.filter(book_type='audiobook').all()

    # 에피소드 없데이트 바로 한 책 
    latest_episodes = Content.objects.select_related('book').order_by('-created_at')[:20]

    # 장르 플레이리스트 (활성화된 전체)
    genre_playlists = GenrePlaylist.objects.filter(
        is_active=True
    ).select_related('genre').prefetch_related(
        'items__content__book'
    ).order_by('genre__name', 'playlist_type')[:10]

    # ai 추천
    ai_recommended_books = []
    if request.user.is_authenticated:
        ai_recommended_books = recommend_books(request.user, limit=9)


    snap_list = BookSnap.objects.all().order_by("?")[:10]

    snippet_list = BookSnippet.objects.all().order_by("?")[:10]

    # 🎙 보이스 라이브러리 (완성된 보이스 프로필)
    voice_profiles = VoiceProfile.objects.filter(
        status='completed', is_activate=True
    ).select_related('user').order_by('-id')[:12]


    # 🎧 홈 데모 플레이어 — 랜덤 에피소드
    demo_episode = None
    try:
        demo_content = (
            Content.objects
            .filter(audio_file__isnull=False,is_deleted=False)
            .exclude(audio_file='')
            .select_related('book')
            .order_by('?')
            .first()
        )
        if demo_content and demo_content.audio_file:
            demo_book = demo_content.book
            demo_episode = {
                'book_name': demo_book.name,
                'ep_num': demo_content.number,
                'ep_title': demo_content.title,
                'audio_url': demo_content.audio_file.url,
                'cover_url': demo_book.cover_img.url if demo_book.cover_img else '',
                'content_uuid': demo_content.public_uuid,
                'book_uuid': demo_book.public_uuid,
            }
    except Exception:
        pass

    webnovel_list = list(Books.objects.filter(book_type='webnovel', is_deleted=False).prefetch_related('genres').order_by('-id')[:40])
    random.shuffle(webnovel_list)

    # 인기 웹소설
    from book.models import Genres as _Genres
    _popular_wn_pool = list(Books.objects.filter(
        book_type='webnovel', is_deleted=False
    ).select_related('user').prefetch_related('genres').order_by('-book_score', '-created_at')[:40])
    random.shuffle(_popular_wn_pool)
    popular_webnovels = _popular_wn_pool[:12]

    # 장르별 웹소설
    genre_webnovels = []
    for g in _Genres.objects.filter(books__book_type='webnovel', books__is_deleted=False).distinct()[:8]:
        g_novels = list(Books.objects.filter(
            book_type='webnovel', is_deleted=False, genres=g
        ).select_related('user').prefetch_related('genres').order_by('-created_at')[:20])
        random.shuffle(g_novels)
        if g_novels:
            genre_webnovels.append({'genre': g, 'books': g_novels[:8]})

    is_minor = not (request.user.is_authenticated and request.user.is_adult())

    context = {
        "is_minor": is_minor,
        "ai_chat_stories": [],
        "webnovel_list": webnovel_list,
        "popular_webnovels": popular_webnovels,
        "genre_webnovels": genre_webnovels,
        "news_list": news_list,
        "banner_books": banner_books,
        "new_books": new_books,
        "popular_books": popular_books,
        "top_rated_books": top_rated_books,
        "trending_books": trending_books,
        "popular_authors": popular_authors,
        "genres_list": genres_list,
        "genres_with_books": genres_with_books,
        "recommended_books": recommended_books,
        "recent_books": recent_listening,
        "recent_listening": recent_listening,
        "audio_list": audio_list,
        "advertisment_list":advertisment_list,
        "ai_recommended_books":ai_recommended_books,
        "snap_list":snap_list,
        "latest_episode":latest_episodes,
        "snippet_list":snippet_list,
        "genre_playlists": genre_playlists,
        "voice_profiles": voice_profiles,
        "demo_episode": demo_episode,
    }
    return render(request, "main/main.html", context)


def delete_listening_history(request, book_uuid):

    book = get_object_or_404(Books, public_uuid = book_uuid, user=request.user)
    ListeningHistory.objects.filter(user=request.user, book =book).delete()

    return redirect('main:main')



# ── AI 맞춤 추천 전체 보기 ──
def ai_recommended_page(request):
    ai_books = []
    if request.user.is_authenticated:
        ai_books = recommend_books(request.user, limit=30)
    recommended_books = []
    if request.user.is_authenticated:
        from book.models import ReadingProgress as RP
        read_genres = Genres.objects.filter(
            books__readingprogress__user=request.user
        ).distinct()[:3]
        if read_genres.exists():
            from django.db.models import Q
            qs = Books.objects.filter(
                book_type='audiobook', genres__in=read_genres, is_activate=True
            ).exclude(
                readingprogress__user=request.user
            ).distinct().order_by('-book_score')[:20]
            recommended_books = list(qs)
    return render(request, 'main/ai_recommended.html', {
        'ai_books': ai_books,
        'recommended_books': recommended_books,
    })


# ── 장르 전체 탐색 ──
def genres_all(request):
    from django.db.models import Count, Q
    genres = Genres.objects.annotate(
        book_count=Count('books', filter=Q(books__is_activate=True))
    ).order_by('name')
    return render(request, 'main/genres_all.html', {'genres': genres})


# ── 플레이리스트 목록 ──
def playlist_list(request):
    playlists = GenrePlaylist.objects.filter(
        is_active=True
    ).select_related('genre').prefetch_related(
        'items__content__book'
    ).order_by('genre__name', 'playlist_type')
    return render(request, 'main/playlist_list.html', {'playlists': playlists})


from rest_framework import status
from rest_framework.response import Response
@require_api_key_secure
@api_view(['DELETE'])
def api_delete_listening_history(request, book_uuid):


    book = get_object_or_404(Books, public_uuid = book_uuid)
    ListeningHistory.objects.filter( book =book).delete()


    return Response(
        {"success": True},
        status=status.HTTP_204_NO_CONTENT
    )


def health_check(request):
    """Colab API 상태 확인"""
    try:
        response = requests.get(f"{COLAB_TTS_URL}/", timeout=5)
        
        if response.status_code == 200:
            return JsonResponse({
                'status': 'healthy',
                'colab': 'connected',
                'url': COLAB_TTS_URL
            })
        else:
            return JsonResponse({
                'status': 'unhealthy',
                'colab': 'error',
                'code': response.status_code
            }, status=503)
    except requests.RequestException as e:
        return JsonResponse({
            'status': 'error',
            'colab': 'unreachable',
            'error': str(e)
        }, status=503)


def test_colab(request):
    """Colab API 연결 테스트"""
    try:
        response = requests.get(f"{COLAB_TTS_URL}/", timeout=5)
        
        if response.status_code == 200:
            return JsonResponse({
                'status': 'success',
                'message': 'Colab 연결 성공!',
                'colab_response': response.json()
            })
        else:
            return JsonResponse({
                'status': 'error',
                'code': response.status_code
            }, status=500)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_POST
@login_required
def calculate(request):
    """Colab API로 계산 요청"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST만 가능'}, status=405)
    
    try:
        data = json.loads(request.body)
        a = data.get('a', 0)
        b = data.get('b', 0)
        
        print(f"📤 Colab으로 전송: a={a}, b={b}")
        
        response = requests.post(
            f"{COLAB_TTS_URL}/add",
            json={"a": a, "b": b},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"📥 Colab 응답: {result}")
            return JsonResponse({'status': 'success', 'result': result})
        else:
            return JsonResponse({'status': 'error', 'code': response.status_code}, status=500)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



def filter_books_by_genre(request):
    """장르별 책 필터링 API"""
    genre_id = request.GET.get('genre_id', None)

    if genre_id:
        books = Books.objects.filter(genres__id=genre_id).select_related('user').prefetch_related('genres').order_by('?')[:20]
    else:
        books = Books.objects.select_related('user').prefetch_related('genres').order_by('?')[:20]

    books_data = []
    for book in books:
        first_episode = book.contents.first()
        books_data.append({
            'id': book.id,
            'name': book.name,
            'cover_img': book.cover_img.url if book.cover_img else None,
            'author': book.user.nickname,
            'genres': [{'name': g.name, 'color': g.genres_color} for g in book.genres.all()],
            'contents_count': book.contents.count(),
            'score': float(book.book_score),
            'audio_file': first_episode.audio_file.url if first_episode and first_episode.audio_file else None,
        })

    return JsonResponse({'books': books_data})


def search_books(request):
    """책 및 작가 검색"""
    from django.db.models import Q, Count
    from register.models import Users

    query = request.GET.get('q', '').strip()

    if not query:
        return render(request, "main/search_result.html", {
            'audiobooks': [],
            'webnovels': [],
            'authors': [],
            'snap_result': [],
            'query': '',
            'audiobooks_count': 0,
            'webnovels_count': 0,
            'authors_count': 0,
            'snap_result_count': 0,
            'books': [],
        })

    # 📚 책 검색 (제목, 설명, 태그로 검색)
    book_qs = Books.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(tags__name__icontains=query)
    ).select_related('user').prefetch_related('genres', 'tags').filter(is_deleted=False).distinct()

    def _book_dict(book):
        return {
            'id': book.id,
            'public_uuid': str(book.public_uuid),
            'name': book.name,
            'cover_img': book.cover_img.url if book.cover_img else None,
            'author': book.user.nickname,
            'author_id': book.user.user_id,
            'description': book.description[:100] if book.description else '',
            'genres': [{'name': g.name, 'color': g.genres_color} for g in book.genres.all()],
            'tags': [{'name': t.name} for t in book.tags.all()],
            'contents_count': book.contents.count(),
            'score': float(book.book_score),
            'book_type': book.book_type,
        }

    audiobooks_data = [_book_dict(b) for b in book_qs.filter(book_type='audiobook')[:20]]

    # 👤 작가 검색 (닉네임으로 검색)
    authors = Users.objects.filter(
        nickname__icontains=query
    ).annotate(
        books_count=Count('books')
    ).filter(books_count__gt=0)[:20]

    authors_data = []
    for author in authors:
        # 작가의 대표 작품 5개
        representative_books = Books.objects.filter(user=author).order_by('-book_score', '-created_at')[:5]

        authors_data.append({
            'id': author.user_id,
            'public_uuid': str(author.public_uuid) if author.public_uuid else '',
            'nickname': author.nickname,
            'profile_img': author.user_img.url if author.user_img else None,
            'bio': author.bio if hasattr(author, 'bio') else '',
            'books_count': author.books_count,
            'representative_books': [
                {
                    'id': book.id,
                    'name': book.name,
                    'cover_img': book.cover_img.url if book.cover_img else None,
                    'public_uuid': str(book.public_uuid),

                } for book in representative_books
            ]
        })

    # snap 검색
    snaps = BookSnap.objects.filter(
        Q(snap_title__icontains=query),
    ).select_related('user').distinct()[:20]

    snap_result = []
    for s in snaps:
        snap_result.append({
            'public_uuid': str(s.public_uuid),
            'snap_title': s.snap_title,
            'thumbnail': s.thumbnail.url if s.thumbnail else None,

        })



    return render(request, "main/search_result.html", {
        'audiobooks': audiobooks_data,
        'webnovels': [],
        'authors': authors_data,
        'snap_result': snap_result,
        'query': query,
        'audiobooks_count': len(audiobooks_data),
        'webnovels_count': 0,
        'authors_count': len(authors_data),
        'snap_result_count': len(snap_result),
        'books': audiobooks_data,
    })




@require_POST
@login_required
def generate_simple_tts(request):
    """
    간단한 TTS 생성 (별도 엔드포인트)

    POST /simple-tts/
    Body: {"text": "안녕하세요"}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST만 가능'}, status=405)
    
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        
        if not text:
            return JsonResponse({'error': '텍스트가 비어있습니다'}, status=400)
        
        print(f"\n{'='*60}")
        print(f"🔊 Simple TTS 생성 요청")
        print(f"📝 텍스트: {text[:100]}...")
        print(f"{'='*60}\n")
        
        # Colab API 호출
        response = requests.post(
            f"{COLAB_TTS_URL}/simple-tts",
            json={"text": text},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ TTS 생성 완료!\n")
            
            return HttpResponse(
                response.content,
                content_type='audio/mp3',
                headers={
                    'Content-Disposition': 'attachment; filename="tts_output.mp3"'
                }
            )
        else:
            return JsonResponse({
                'error': 'TTS 생성 실패',
                'detail': response.text
            }, status=500)
    
    except Exception as e:
        print(f"❌ 오류: {str(e)}\n")
        return JsonResponse({'error': str(e)}, status=500)
    


from django.core.paginator import Paginator

def new_books(request):
    book_list = Books.objects.all().order_by("-created_at")

    # 페이지네이션: 한 페이지에 12개 책 표시
    paginator = Paginator(book_list, 35)
    page_number = request.GET.get('page')  # URL ?page=1 등
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,  # 템플릿에서 for book in page_obj
    }

    return render(request, "main/new_books.html", context)

from django.shortcuts import render, get_object_or_404
from book.models import Genres

def genres_books(request, genres_id):
    # 선택한 장르 가져오기
    genre = get_object_or_404(Genres, id=genres_id)

    # 해당 장르의 책 모두 가져오기
    books_qs = Books.objects.filter(genres=genre).order_by('-created_at')  # 최신순 정렬

    # 페이지네이션 (1페이지당 12권)
    paginator = Paginator(books_qs, 16)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "genre": genre,
        "books": page_obj,
        "page_obj": page_obj,
    }

    return render(request, "main/genres_books.html", context)


# 스니펫 리스트
@login_required_to_main
def snippet_all(request):
    snippet_ids = list(BookSnippet.objects.values_list('id', flat=True))
    selected_ids = random.sample(snippet_ids, min(10, len(snippet_ids)))
    snippet_list = BookSnippet.objects.filter(id__in=selected_ids)

    context ={
        "snippet_list":snippet_list

    }

    return render(request, "main/snippet_list.html", context)



# 이벤트
def event(request):
    event_list = Event.objects.all()
    context = {
        "event_list":event_list

    }

    return render(request, "main/event.html", context)



from django.shortcuts import render, get_object_or_404
from main.models import Notice, FAQ, Contact, Terms, Policy
from register.models import Users

# 1️⃣ 공지사항
def notice(request):
    notices = Notice.objects.filter(is_active=True).order_by('-created_at')
    context = {
        'notices': notices
    }
    return render(request, "main/other/notice.html", context)


# 2️⃣ FAQ
def faq(request):
    faqs = FAQ.objects.filter(is_active=True)

    for faq in faqs:
        faq.category_display = faq.get_category_display()   
    context = {
        'faqs': faqs
    }
    return render(request, "main/other/FAQ.html", context)


# 3️⃣ 문의하기 (목록 조회)
@login_required_to_main
def contact_list(request):
    contacts = Contact.objects.all().order_by('-created_at')
    context = {
        'contacts': contacts
    }
    return render(request, "main/other/contact.html", context)

# 문의하기 쓰기
def contact_write(request):
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        email = request.POST.get("email", "").strip()
        
        if subject and message and email:
            Contact.objects.create(
                user=request.user,
                subject=subject,
                message=message,
                email=email,
                status="pending"
            )
            return redirect('/contact/')  # 제출 후 감사 페이지
        else:
            error = "모든 필드를 채워주세요."
    else:
        error = None

    context = {
        "error": error
    }
    return render(request, "main/other/contact_write.html", context)


from django.contrib.admin.views.decorators import staff_member_required

from django.http import HttpResponseForbidden

@login_required_to_main
def contact_detail(request, contact_id):
    contact = get_object_or_404(Contact, id=contact_id)

    if not (
        request.user.is_staff or
        (contact.user and contact.user == request.user)
    ):
        return redirect("main:contact")  # 👈 문의 목록

    return render(request, "main/other/contact_detail.html", {
        "contact": contact
    })

# 4️⃣ 이용약관
def terms_of_service(request):
    latest_terms = Terms.objects.order_by('-created_at').first()
    context = {
        'terms': latest_terms
    }
    return render(request, "main/other/terms_of_service.html", context)


# 5️⃣ 개인정보처리방침
def privacy_policy(request):
    privacy = Policy.objects.filter(policy_type='privacy').order_by('-created_at').first()
    context = {
        'policy': privacy
    }
    return render(request, "main/other/privacy_policy.html", context)


# 6️⃣ 저작권 정책
def copyright_policy(request):
    copyright_p = Policy.objects.filter(policy_type='copyright').order_by('-created_at').first()
    context = {
        'policy': copyright_p
    }
    return render(request, "main/other/copyright_policy.html", context)


# 7️⃣ 청소년 보호정책
def youth_protection(request):
    youth = Policy.objects.filter(policy_type='youth').order_by('-created_at').first()
    context = {
        'policy': youth
    }
    return render(request, "main/other/youth_protection.html", context)


# 웹소설 페이지
def webnovel(request):
    from book.models import Books
    novels = list(Books.objects.filter(book_type='webnovel', is_deleted=False).order_by('-id')[:40])
    random.shuffle(novels)
    return render(request, "main/webnovel.html", {"novels": novels})


# snap list
def snap_list(request):
    snap_list = BookSnap.objects.order_by("?")[:15]  # 랜덤 15개

    content = {
        "snap_list": snap_list
    }
    return render(request, "main/snap_list.html", content)

from book.models import Books, Follow
# user 정보
def user_info(request, user_uuid):

    # URL의 user_uuid로 해당 유저 조회
    target_user = get_object_or_404(Users, public_uuid=user_uuid)

    book_list = Books.objects.filter(user=target_user)

    # 해당 유저의 스냅
    snap_list = BookSnap.objects.filter(user=target_user).order_by('-created_at')

    # 팔로워/팔로잉 수
    follower_count = Follow.objects.filter(following=target_user).count()
    following_count = Follow.objects.filter(follower=target_user).count()

    # 로그인한 유저가 이 유저를 팔로우 중인지
    is_following = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(
            follower=request.user,
            following=target_user
        ).exists()

    context = {
        "target_user": target_user,
        "book_list": book_list,
        "snap_list": snap_list,
        "follower_count": follower_count,
        "following_count": following_count,
        "is_following": is_following,
        "is_own_profile": request.user == target_user,
    }
    
    return render(request, "main/user_intro.html", context)




def playlist_detail(request, playlist_id):
    playlist = get_object_or_404(
        GenrePlaylist.objects.select_related('genre').prefetch_related(
            'items__content__book'
        ),
        id=playlist_id,
        is_active=True
    )
    return render(request, 'main/playlist_detail.html', {'playlist': playlist})


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('main:main')

    from datetime import timedelta
    from register.models import Users, Subscription, AuthorApplication, AuthorInquiry
    from book.models import Books, Content, BookReview, ListeningHistory, BookSnap

    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    active_subs = Subscription.objects.filter(
        status='active', expires_at__gt=now
    )
    stats = {
        'total_users': Users.objects.count(),
        'new_users_week': Users.objects.filter(created_at__gte=week_ago).count(),
        'new_users_month': Users.objects.filter(created_at__gte=month_ago).count(),
        'total_books': Books.objects.filter(is_deleted=False).count(),
        'audiobooks': Books.objects.filter(book_type='audiobook', is_deleted=False).count(),
        'webnovels': Books.objects.filter(book_type='webnovel', is_deleted=False).count(),
        'total_episodes': Content.objects.filter(is_deleted=False).count(),
        'active_subs': active_subs.count(),
        'total_snaps': BookSnap.objects.count(),
        # 'total_reviews': BookReview.objects.filter(is_deleted=False).count(),
        'pending_author_apps': AuthorApplication.objects.filter(status='pending').count(),
        'pending_inquiries': AuthorInquiry.objects.filter(status='pending').count(),
    }

    # 최근 청취 통계 (7일)
    listening = ListeningHistory.objects.filter(last_listened_at__gte=week_ago).aggregate(
        sessions=Count('id'),
        unique_listeners=Count('user', distinct=True),
        total_seconds=Sum('listened_seconds'),
    )
    stats['listening_sessions'] = listening['sessions'] or 0
    stats['listening_users'] = listening['unique_listeners'] or 0
    stats['listening_hours'] = round((listening['total_seconds'] or 0) / 3600, 1)

    # 최근 가입 유저 10명
    recent_users = Users.objects.order_by('-created_at')[:10]

    # 최근 등록 책 10개
    recent_books = Books.objects.filter(is_deleted=False).select_related('user').prefetch_related('genres').order_by('-created_at')[:10]

    # 구독 현황
    sub_monthly = active_subs.filter(plan='monthly').count()
    sub_yearly = active_subs.filter(plan='yearly').count()

    # 인기 책 Top 10 (이번 주 청취 기준)
    top_books = (
        ListeningHistory.objects.filter(last_listened_at__gte=week_ago)
        .values('book__name', 'book__public_uuid', 'book__id')
        .annotate(listeners=Count('user', distinct=True))
        .order_by('-listeners')[:10]
    )

    # 전체 구독자 목록 (active + expired 포함, 최근 50명)
    all_subs = Subscription.objects.select_related('user').order_by('-created_at')[:60]

    # 무료 이용자 수 (subscription 없거나 expired/cancelled)
    sub_free = Users.objects.count() - Subscription.objects.filter(status='active', expires_at__gt=now).count()

    # 미답변 작가 문의 (pending)
    from register.models import AuthorInquiry
    pending_inquiries = AuthorInquiry.objects.filter(
        status='pending', parent__isnull=True
    ).select_related('user', 'book').order_by('-created_at')[:30]

    # 전체 작가 문의
    all_author_inquiries = AuthorInquiry.objects.filter(
        parent__isnull=True
    ).select_related('user', 'book').order_by('-created_at')[:50]

    # 일반 문의 (Contact)
    from main.models import Contact
    pending_contacts = Contact.objects.filter(status='pending').count()
    contact_inquiries = Contact.objects.select_related('user').order_by('-created_at')[:50]

    # 작가 신청
    pending_apps = AuthorApplication.objects.filter(status='pending').count()
    author_apps = AuthorApplication.objects.select_related('user').order_by('-applied_at')[:50]

    # 작가 목록
    authors = Users.objects.filter(is_author=True).order_by('-created_at')[:50]

    # 정산 내역
    from register.models import SettlementRecord
    settle_records = SettlementRecord.objects.select_related('user').order_by('-period')[:50]

    context = {
        'stats': stats,
        'recent_users': recent_users,
        'recent_books': recent_books,
        'top_books': top_books,
        'sub_monthly': sub_monthly,
        'sub_yearly': sub_yearly,
        'sub_free': max(sub_free, 0),
        'all_subs': all_subs,
        'now': now,
        'pending_inquiries': pending_inquiries,
        'all_author_inquiries': all_author_inquiries,
        'contact_inquiries': contact_inquiries,
        'pending_contacts': pending_contacts,
        'author_apps': author_apps,
        'pending_apps': pending_apps,
        'authors': authors,
        'settle_records': settle_records,
    }
    return render(request, 'main/admin_dashboard.html', context)


@login_required
@require_POST
def admin_approve_author(request, app_id):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': '권한 없음'}, status=403)
    from register.models import AuthorApplication
    try:
        app = get_object_or_404(AuthorApplication, id=app_id)
        app.status = 'approved'
        app.reviewed_at = timezone.now()
        app.save()
        app.user.is_author = True
        app.user.save(update_fields=['is_author'])
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def admin_reject_author(request, app_id):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': '권한 없음'}, status=403)
    from register.models import AuthorApplication
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        app = get_object_or_404(AuthorApplication, id=app_id)
        app.status = 'rejected'
        app.reject_reason = reason
        app.reviewed_at = timezone.now()
        app.save()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def admin_subscription_change(request, user_id):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': '권한 없음'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    import json as _json
    from datetime import timedelta
    from register.models import Users, Subscription

    try:
        data = _json.loads(request.body)
        plan = data.get('plan')  # 'monthly', 'yearly', 'free'
        user = get_object_or_404(Users, id=user_id)

        if plan == 'free':
            try:
                sub = user.subscription
                sub.status = 'cancelled'
                sub.expires_at = timezone.now()
                sub.save()
            except Subscription.DoesNotExist:
                pass
        elif plan in ('monthly', 'yearly'):
            delta = timedelta(days=365 if plan == 'yearly' else 30)
            sub, created = Subscription.objects.get_or_create(
                user=user,
                defaults={
                    'plan': plan, 'status': 'active',
                    'started_at': timezone.now(),
                    'expires_at': timezone.now() + delta,
                }
            )
            if not created:
                sub.plan = plan
                sub.status = 'active'
                sub.expires_at = timezone.now() + delta
                sub.save()
        else:
            return JsonResponse({'ok': False, 'error': '올바르지 않은 플랜'}, status=400)

        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def admin_inquiry_reply(request, inquiry_id):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': '권한 없음'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    import json as _json
    from register.models import AuthorInquiry
    try:
        data   = _json.loads(request.body)
        answer = data.get('answer', '').strip()
        status = data.get('status', 'answered')
        inq    = get_object_or_404(AuthorInquiry, id=inquiry_id)
        inq.answer = answer
        inq.status = status if status in ('answered', 'closed') else 'answered'
        inq.save()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# 에러
def bad_request(request, exception):
    return render(request, "error/400.html", status=400)

def permission_denied(request, exception):
    return render(request, "error/403.html", status=403)

def page_not_found(request, exception):
    return render(request, "error/404.html", status=404)

def server_error(request):
    return render(request, "error/500.html", status=500)


