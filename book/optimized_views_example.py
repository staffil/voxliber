"""
성능 최적화된 뷰 예시
"""
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Count, Avg, Prefetch
from book.models import Books, Contents, Review

# ❌ 최적화 안 된 버전 (N+1 쿼리)
def book_list_slow(request):
    books = Books.objects.all()  # 1번 쿼리
    # 템플릿에서 book.user.nickname 접근할 때마다 쿼리 실행 (N번)
    # 템플릿에서 book.genres.all() 접근할 때마다 쿼리 실행 (N번)
    return render(request, 'book/list.html', {'books': books})


# ✅ 최적화된 버전
def book_list_fast(request):
    books = Books.objects.select_related('user').prefetch_related(
        'genres',
        'tags',
        Prefetch('contents', queryset=Contents.objects.filter(is_publish=True).order_by('-created_at')[:3])
    ).annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__score')
    ).all()

    # 페이지네이션 (한 번에 모든 데이터 로드 방지)
    paginator = Paginator(books, 20)  # 페이지당 20개
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'book/list.html', {'books': page_obj})


# ✅ 도서 상세 페이지 최적화
def book_detail_fast(request, book_id):
    book = Books.objects.select_related('user').prefetch_related(
        'genres',
        'tags',
        Prefetch('contents', queryset=Contents.objects.filter(is_publish=True).order_by('episode_number')),
        Prefetch('reviews', queryset=Review.objects.select_related('user').order_by('-created_at')[:10])
    ).get(id=book_id)

    return render(request, 'book/detail.html', {'book': book})
