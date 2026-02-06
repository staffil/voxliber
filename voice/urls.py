from django.urls import path
from main import views  
from django.conf import settings
from django.conf.urls.static import static
from voice import views

app_name = "voice"

urlpatterns = [
    path('voice/list/', views.voice_list, name='voice_list'),

]