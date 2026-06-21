import os
import json
import requests
from urllib.parse import quote

from django.shortcuts import redirect
from django.contrib.auth import get_user_model, login as auth_login

from book.models import APIKey

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

User = get_user_model()

_CALLBACK_PATH = '/login/oauth/google/callback/'


def google_login(request):
    flutter_redirect_uri = request.GET.get('redirect_uri')
    if flutter_redirect_uri:
        request.session['oauth_redirect_uri'] = flutter_redirect_uri

    redirect_uri = request.build_absolute_uri(_CALLBACK_PATH)
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=openid email profile"
    )
    return redirect(auth_url)


def google_callback(request):
    code = request.GET.get("code")
    redirect_uri = request.build_absolute_uri(_CALLBACK_PATH)

    token_res = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).json()
    access_token = token_res.get("access_token")

    profile = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    google_id = str(profile.get("id", ""))
    email = profile.get("email") or f"google_{google_id}@example.com"

    user = User.objects.filter(email=email).first()
    if not user:
        user = User.objects.create(
            username=f"google_{google_id}",
            email=email,
            is_profile_completed=False,
        )
    auth_login(request, user)

    flutter_redirect = request.session.pop('oauth_redirect_uri', None)
    is_mobile = 'VoxLiberApp' in request.META.get('HTTP_USER_AGENT', '')

    if flutter_redirect or is_mobile:
        api_key_obj = APIKey.objects.filter(user=user, is_active=True, name='모바일 앱').first()
        if not api_key_obj:
            api_key_obj = APIKey.objects.create(user=user, name='모바일 앱')

        if is_mobile:
            return redirect(f'/login/mobile-login-success/{api_key_obj.key}/')

        user_data = {
            "id": str(user.public_uuid),
            "username": user.username,
            "nickname": getattr(user, "nickname", ""),
            "email": user.email,
            "profile_img": user.user_img.url if user.user_img else None,
            "is_profile_completed": user.is_profile_completed,
            "birthdate": str(user.birthdate) if user.birthdate else None,
            "is_adult": user.is_adult(),
        }
        state = "signup_required" if not user.is_profile_completed else "signup_complete"
        user_json = quote(json.dumps(user_data))
        return redirect(
            f"{flutter_redirect}?api_key={api_key_obj.key}&user={user_json}&state={state}"
        )

    if not user.is_profile_completed:
        return redirect('/login/signup/')
    return redirect("/")
