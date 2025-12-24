from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Books


class BookSitemap(Sitemap):
    """책 상세 페이지 Sitemap"""
    changefreq = "weekly"
    priority = 0.8
    protocol = 'https'

    def items(self):
        """모든 책 반환"""
        return Books.objects.all().order_by('-created_at')

    def lastmod(self, obj):
        """마지막 수정일"""
        return obj.created_at

    def location(self, obj):
        """책 상세 페이지 URL"""
        return f'/book/detail/{obj.id}/'


class StaticViewSitemap(Sitemap):
    """정적 페이지 Sitemap"""
    priority = 0.5
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        """정적 페이지 목록"""
        return ['home', 'book_list', 'about']

    def location(self, item):
        """정적 페이지 URL"""
        if item == 'home':
            return '/'
        elif item == 'book_list':
            return '/book/'
        elif item == 'about':
            return '/about/'
        return '/'
