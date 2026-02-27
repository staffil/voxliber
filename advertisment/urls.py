from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from advertisment import views


app_name = "advertisment"

urlpatterns = [
    path('request/list/', views.request_ad_list, name='request_ad_view'),
    path('my/', views.my_ad_list, name='my_ad_list'),
    path('settlement/', views.ad_settlement, name='ad_settlement'),
]
