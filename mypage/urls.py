from django.urls import path
from mypage import views
from mypage import api_views

app_name = "mypage"

urlpatterns = [
    path("profile/", views.my_profile, name="my_profile"),
    path("profile/update/", views.my_profile_update, name="my_profile_update"),
    path("my/book/list/", views.my_book_list, name="my_book_list"),
    path("library/", views.my_library, name="my_library"),
    path("snippet/<uuid:book_uuid>/", views.book_snippet_form, name="book_snippet_form"),
    path("api/library/", views.api_my_library, name="api_my_library"),
    path("library/update-progress/", views.update_reading_progress, name="update_reading_progress"),
    path("delete/<int:pk>/", views.delete_my_voice, name="delete_my_voice"),
    path("toggle_myvoice_favorite/<int:pk>/", views.toggle_favorite, name="toggle_myvoice_favorite"),
    path("select_book/<int:pk>/", views.select_book, name="select_book"),
    path("account/delete/", views.delete_account, name="delete_account"),

    # api 구간
    path("api/user_info/", api_views.api_user_info, name="api_user_info"),
    path("api/user/intro/<uuid:user_uuid>/", api_views.public_user_profile, name="public_user_profile"),
    path("api/user/<uuid:user_uuid>/follow/toggle/", api_views.toggle_follow_api, name="toggle_follow_api"),
    path("api/listening-stats/", api_views.api_listening_stats, name="api_listening_stats"),

]
