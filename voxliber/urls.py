"""
URL configuration for voxliber project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from book.sitemaps import BookSitemap, StaticViewSitemap
from django.http import FileResponse
import os

# Sitemap 설정
sitemaps = {
    'books': BookSitemap,
    'static': StaticViewSitemap,
}

# Deep Link 검증 파일 제공 뷰
def serve_well_known(request, filename):
    file_path = os.path.join(settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.BASE_DIR / 'static', '.well-known', filename)
    return FileResponse(open(file_path, 'rb'), content_type='application/json')

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("main.urls", "main"), namespace="main")),
    path("login/", include(("register.urls", "register"), namespace="register")),
    path("book/", include(("book.urls", "book"), namespace="book")),
    path("mypage/", include(("mypage.urls", "mypage"), namespace="mypage")),
    path("voice/", include(("voice.urls", "voice"), namespace="voice")),
    path("robots.txt", TemplateView.as_view(
        template_name="robots.txt",
        content_type="text/plain"
    )),
    path("sitemap.xml", sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('naver68afd1621fdbfa5d1c2dc3728aa152e8.html', TemplateView.as_view(template_name='naver68afd1621fdbfa5d1c2dc3728aa152e8.html')),

    # Deep Link Verification Files
    path('.well-known/apple-app-site-association',
         lambda request: serve_well_known(request, 'apple-app-site-association')),
    path('.well-known/assetlinks.json',
         lambda request: serve_well_known(request, 'assetlinks.json')),

]

# 개발 환경에서 미디어 파일 서빙
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

