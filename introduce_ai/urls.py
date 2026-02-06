from introduce_ai import views  
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path


app_name = "introduce_ai"

urlpatterns = [


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
  