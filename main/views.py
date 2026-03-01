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
from main.models import SnapBtn, Advertisment, Event, ScreenAI
from book.models import Books,ReadingProgress, BookSnap, Content, Poem_list, BookTag, Tags, BookSnippet, ListeningHistory, GenrePlaylist
from character.models import Story, CharacterMemory, LLM, LoreEntry, ConversationMessage, Conversation,LastWard, UserLastWard, ConversationState
from book.service.recommendation import recommend_books
from django.db.models import Max
import random
from register.decorator import login_required_to_main
from rest_framework.decorators import api_view, permission_classes
from book.api_utils import require_api_key, paginate, api_response, require_api_key_secure



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
    story_list = Story.objects.all()



    

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

    # 장르당 인기 많은 수록 책들
    popular_genres = GenrePlaylist.objects.filter(
        playlist_type='popular',
        is_active=True
    ).select_related('genre').prefetch_related(
        'items__content__book'
    )[:6]

    # ai 추천
    ai_recommended_books = []
    if request.user.is_authenticated:
        ai_recommended_books = recommend_books(request.user, limit=9)


    snap_list = BookSnap.objects.all().order_by("?")[:10]


    poem_list = Poem_list.objects.filter(status="winner").order_by("?")[:10]


    snippet_list = BookSnippet.objects.all().order_by("?")[:10]

    ai_advertismemt_img = ScreenAI.objects.all()

    # AI 소설 탭 - 공유된 대화 목록
    user_share_list = Conversation.objects.filter(
        is_public=True
    ).select_related('llm', 'user').order_by('-shared_at')[:30]

    # 🎧 홈 데모 플레이어 — 랜덤 에피소드
    demo_episode = None
    try:
        demo_content = (
            Content.objects
            .filter(audio_file__isnull=False)
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
        "snippet_list":snippet_list,
        "ai_stories":story_list,
        "ai_advertismemt_img":ai_advertismemt_img,
        "user_share_list":user_share_list,
        "popular_genres":popular_genres,
        "demo_episode": demo_episode,
    }
    return render(request, "main/main.html", context)


def delete_listening_history(request, book_uuid):

    book = get_object_or_404(Books, public_uuid = book_uuid, user=request.user)
    ListeningHistory.objects.filter(user=request.user, book =book).delete()

    return redirect('main:main')



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
            'books': [],
            'authors': [],
            'ai_stories': [],
            'query': '',
            'books_count': 0,
            'authors_count': 0,
            'ai_stories_count': 0,
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
                    'public_uuid': str(book.public_uuid),

                } for book in representative_books
            ]
        })

    # 🤖 AI 스토리 검색
    from character.models import Story
    ai_stories = Story.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(genres__name__icontains=query) |
        Q(tags__name__icontains=query),
        is_public=True
    ).select_related('user').prefetch_related('genres', 'characters').distinct()[:20]

    ai_stories_data = []
    for story in ai_stories:
        ai_stories_data.append({
            'id': story.id,
            'public_uuid': str(story.public_uuid),
            'title': story.title,
            'cover_image': story.cover_image.url if story.cover_image else None,
            'author': story.user.nickname if story.user else '알 수 없음',
            'description': story.description[:100] if story.description else '',
            'genres': [{'name': g.name, 'color': g.genres_color} for g in story.genres.all()],
            'character_count': story.characters.count(),
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
        'books': books_data,
        'authors': authors_data,
        'ai_stories': ai_stories_data,
        'snap_result':snap_result,
        'query': query,
        'books_count': len(books_data),
        'authors_count': len(authors_data),
        'ai_stories_count': len(ai_stories_data),
        'snap_result_count': len(snap_result)
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


@login_required_to_main
def poem_winner(request):
    poem_ids = list(Poem_list.objects.values_list('id', flat=True))
    selected_ids = random.sample(poem_ids, min(10, len(poem_ids)))
    poem_list = Poem_list.objects.filter(id__in=selected_ids)

    content = {
        "poem_list":poem_list
    }


    return render(request, "main/poem_winner.html", content)


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


from book.service.recommendation import generate_ai_reason, get_user_preference
# AI 가 추천하는 책 뷰
from django.shortcuts import render
from book.service.recommendation import generate_ai_reason
@login_required_to_main
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




# AI 소설 페이지
def ai_novel_main(request):
    # 1. 랜덤 스토리 (성능 위해 10개만)
    story_list = Story.objects.all().order_by('?')  # 10개로 제한 추천

    # 2. ScreenAI 전체 (필요하면 필터링)
    screen_list = ScreenAI.objects.all()[:20]  # 너무 많으면 제한

    # 3. 공개된 대화 목록 (최근 20개)
    user_share_list = Conversation.objects.filter(
        is_public=True
    ).select_related('llm', 'user').order_by('-shared_at')

    # 4. 본인 대화도 포함하고 싶다면 (선택)
    if request.user.is_authenticated:
        my_conversations = Conversation.objects.filter(
            user=request.user,
            is_public=True
        ).select_related('llm').order_by('-shared_at')[:10]
    else:
        my_conversations = []

    content = {
        "ai_stories": story_list,
        "screen_list": screen_list,
        "user_share_list": user_share_list,
        "my_conversations": my_conversations,  # 본인 공개 대화 (선택)
        "is_authenticated": request.user.is_authenticated,
    }

    return render(request, "main/ai_novel_main.html", content)


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

    # 해당 유저의 책과 스토리
    book_list = Books.objects.filter(user=target_user)
    story_list = Story.objects.filter(user=target_user)


     # 3. 공개된 대화 목록 (최근 20개)
    user_share_list = Conversation.objects.filter(
        is_public=True
    ).select_related('llm', 'user').order_by('-shared_at')


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
        "story_list": story_list,
        "snap_list": snap_list,
        "follower_count": follower_count,
        "following_count": following_count,
        "is_following": is_following,
        "is_own_profile": request.user == target_user,
        "user_share_list":user_share_list
    }
    
    return render(request, "main/user_intro.html", context)

from django.utils import timezone
from character.models import HPImageMapping


def shared_novel(request, conv_id):
    """
    공개된 대화(Conversation)를 공유용으로 보여주는 뷰
    - 로그인 없이도 접근 가능
    - is_public=True인 대화만 허용
    """
    # conv_id로 대화 직접 조회 (본인 여부 상관없이)
    conversation = get_object_or_404(Conversation, id=conv_id)

    # 공개되지 않은 대화면 접근 차단
    if not conversation.is_public:
        return render(request, 'novel/private_novel.html', {
            'message': '이 소설은 현재 비공개 상태입니다.'
        })

    llm = conversation.llm

    # HP 매핑 로드
    hp_mappings = list(
        HPImageMapping.objects.filter(llm=llm, sub_image__isnull=False)
        .select_related('sub_image')
        .order_by('min_hp')
    )

    # 메시지 불러오기
    messages = conversation.messages.order_by('created_at')

    novel = {
        'title': f"{llm.name}과의 이야기",
        'prologue': f"*그날, {llm.name}과의 대화는 조용히 시작되었다.*",
        'chapters': [],
        'epilogue': f"*HP {messages.last().hp_after_message if messages.exists() else 0}에 도달했다.*",
    }

    current_chapter = None
    current_range = None

    for msg in messages:
        msg_range = (msg.hp_range_min, msg.hp_range_max)

        if msg_range != current_range:
            current_range = msg_range
            matched_mapping = next(
                (m for m in hp_mappings if (m.min_hp or 0) == (msg.hp_range_min or 0)),
                None
            )

            current_chapter = {
                'title': matched_mapping.note if matched_mapping else f"HP {msg.hp_range_min or 0} ~ {msg.hp_range_max or 100}",
                'image': matched_mapping.sub_image if matched_mapping else None,
                'hp_range': msg_range,
                'messages': [],
            }
            novel['chapters'].append(current_chapter)
            print(f"[SHARED CHAPTER] 새 구간: {current_chapter['title']}, img={matched_mapping.sub_image.id if matched_mapping else '없음'}")

        if current_chapter:
            current_chapter['messages'].append({
                'role': msg.role,
                'speaker': llm.name if msg.role == 'assistant' else '너',
                'content': msg.content,
                'audio': msg.audio.url if msg.audio else None,
            })
    last_wards = []

    conv_state = ConversationState.objects.get(conversation=conversation)

    current_hp = conv_state.character_stats.get('hp', 100)

    if current_hp >= 100:
        last_wards = LastWard.objects.filter(llm= conversation.llm).order_by('order')

    user_share_list = Conversation.objects.filter(
        is_public=True,
        llm=conversation.llm

    ).select_related('llm', 'user')



    context = {
        'novel': novel,
        'conversation': conversation,
        'is_shared': True,  # 공유 모드임을 템플릿에 알림
        'llm': llm,
        "last_wards":last_wards,
        "user_share_list":user_share_list
    }
    return render(request, 'main/shared_conversation.html', context)





def playlist_detail(request, playlist_id):
    playlist = get_object_or_404(
        GenrePlaylist.objects.select_related('genre').prefetch_related(
            'items__content__book'
        ),
        id=playlist_id,
        is_active=True
    )
    return render(request, 'main/playlist_detail.html', {'playlist': playlist})


# 에러
def bad_request(request, exception):
    return render(request, "error/400.html", status=400)

def permission_denied(request, exception):
    return render(request, "error/403.html", status=403)

def page_not_found(request, exception):
    return render(request, "error/404.html", status=404)

def server_error(request):
    return render(request, "error/500.html", status=500)


