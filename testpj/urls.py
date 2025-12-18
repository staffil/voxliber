from django.urls import path
from testpj import views  # testpj 내부에서 . 으로 import

app_name = "testpg"

urlpatterns = [
    path("test_tts/", views.test_tts, name="test_tts"),
    path("soundpg/", views.soundpg, name="soundpg"),
]