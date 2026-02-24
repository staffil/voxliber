from django.urls import path
from . import views

urlpatterns = [
    path('fcm-token/', views.register_fcm_token, name='register_fcm_token'),
    path('list/', views.get_notifications, name='notifications_list'),
    path('<int:notification_id>/read/', views.mark_read, name='notification_read'),
    path('read-all/', views.mark_all_read, name='notification_read_all'),
]
