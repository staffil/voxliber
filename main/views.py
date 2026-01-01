# main/views.py
from django.shortcuts import render,redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import requests
import json
import os
from uuid import uuid4
from django.conf import settings
from main.models import SnapBtn, Advertisment, Event
from book.models import Books,ReadingProgress, BookSnap, Content, Poem_list, BookTag, Tags, BookSnippet
from book.service.recommendation import recommend_books
from django.db.models import Max
import random

# Colab API URL
COLAB_TTS_URL = "https://dolabriform-intense-jameson.ngrok-free.dev"




def main(request):
    """메인 페이지"""
    from book.models import Genres
    from register.models import Users
    from django.db.models import Count, Max, Sum
    from django.utils import timezone
    from datetime import timedelta

    # 뉴스/배너
    news_list = SnapBtn.objects.all()[:5]
    advertisment_list = Advertisment.objects.all()
    

    # 📌 신작 (최근 30일 이내 생성된 책, 최신 콘텐츠 기준 정렬)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_books = Books.objects.filter(
        created_at__gte=thirty_days_ago
    ).annotate(
        last_content_time=Max('contents__created_at')
    ).select_related('user').prefetch_related('genres').order_by('-last_content_time')[:20]

    # 🔥 인기 작품 (평점과 에피소드 수를 고려한 종합 점수)
    popular_books = (
        Books.objects
        .select_related('user')
        .prefetch_related('genres')
        .annotate(
            total_listened=Sum('listening_stats__listened_seconds'),
            listener_count=Count('listening_stats__user', distinct=True),
        )
        .order_by('-listener_count', '-total_listened')[:12]
    )
    # 🏆 최고 평점 작품 (리뷰가 최소 1개 이상)
    top_rated_books = Books.objects.filter(
        book_score__gt=0
    ).select_related('user').prefetch_related('genres').order_by('-book_score')[:8]

    # ⚡ 트렌딩 작품 (최근 인기작 - 평점과 에피소드 수 기준)
    seven_days_ago = timezone.now() - timedelta(days=7)
    trending_books = Books.objects.filter(
        created_at__lte=seven_days_ago  # 신작 제외
    ).select_related('user').prefetch_related('genres').annotate(
        episode_count=Count('contents')
    ).order_by('-book_score', '-episode_count')[:8]

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
            genres=genre
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
                recommended_books = Books.objects.filter(
                    genres__in=user_genres
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
    audio_list = Books.objects.all()

    # 에피소드 없데이트 바로 한 책 
    latest_episodes = Content.objects.select_related('book').order_by('-created_at')[:20]


    # ai 추천
    ai_recommended_books = []
    if request.user.is_authenticated:
        ai_recommended_books = recommend_books(request.user, limit=9)


    snap_list = BookSnap.objects.all().order_by("?")[:10]


    poem_list = Poem_list.objects.filter(status="winner").order_by("?")[:10]


    snippet_list = BookSnippet.objects.all().order_by("?")[:10]


    context = {
        "news_list": news_list,
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
        "poem_list":poem_list,
        "snippet_list":snippet_list
    }
    return render(request, "main/main.html", context)


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
            'books': [],
            'authors': [],
            'query': '',
            'books_count': 0,     
        'authors_count': 0,    
            
        })

    # 📚 책 검색 (제목, 설명, 태그로 검색)
    books = Books.objects.filter(
        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(tags__name__icontains=query)
    ).select_related('user').prefetch_related('genres', 'tags').distinct()[:20]

    books_data = []
    for book in books:
        books_data.append({
            'id': book.id,
            'name': book.name,
            'cover_img': book.cover_img.url if book.cover_img else None,
            'author': book.user.nickname,
            'author_id': book.user.user_id,
            'description': book.description[:100] if book.description else '',
            'genres': [{'name': g.name, 'color': g.genres_color} for g in book.genres.all()],
            'tags': [{'name': t.name} for t in book.tags.all()],
            'contents_count': book.contents.count(),
            'score': float(book.book_score),
        })

    # 👤 작가 검색 (닉네임으로 검색)
    authors = Users.objects.filter(
        nickname__icontains=query
    ).annotate(
        books_count=Count('books')
    ).filter(books_count__gt=0)[:20]

    authors_data = []
    for author in authors:
        # 작가의 대표 작품 3개
        representative_books = Books.objects.filter(user=author).order_by('-book_score', '-created_at')[:5]

        authors_data.append({
            'id': author.user_id,
            'nickname': author.nickname,
            'profile_img': author.user_img.url if author.user_img else None,
            'bio': author.bio if hasattr(author, 'bio') else '',
            'books_count': author.books_count,
            'representative_books': [
                {
                    'id': book.id,
                    'name': book.name,
                    'cover_img': book.cover_img.url if book.cover_img else None,
                } for book in representative_books
            ]
        })

    return render(request, "main/search_result.html", {
        'books': books_data,
        'authors': authors_data,
        'query': query,
        'books_count': len(books_data),
        'authors_count': len(authors_data),
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



def poem_winner(request):
    poem_ids = list(Poem_list.objects.values_list('id', flat=True))
    selected_ids = random.sample(poem_ids, min(10, len(poem_ids)))
    poem_list = Poem_list.objects.filter(id__in=selected_ids)

    content = {
        "poem_list":poem_list
    }


    return render(request, "main/poem_winner.html", content)


# 스니펫 리스트

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
    faqs = FAQ.objects.filter(is_active=True).order_by('category', 'id')
    context = {
        'faqs': faqs
    }
    return render(request, "main/other/FAQ.html", context)


# 3️⃣ 문의하기 (목록 조회)
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
            return redirect('contact/')  # 제출 후 감사 페이지
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


from book.service.recommendation import generate_ai_reason, get_user_preference
# AI 가 추천하는 책 뷰
from django.shortcuts import render
from book.service.recommendation import generate_ai_reason

def ai_recommended(request):
    user = request.user

    books = recommend_books(user, limit=5)

    chat_messages = [
        {
            "type": "intro",
            "text": "당신의 취향 데이터를 분석해서 책을 추천했어요 📊"
        }
    ]

    for book in books:
        chat_messages.append({
            "type": "book",
            "book": book,
            "reason": generate_ai_reason(book)
        })

    return render(request, "main/ai_recommended.html", {
        "chat_messages": chat_messages
    })
