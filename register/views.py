from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, login as auth_login, logout
from dotenv import load_dotenv
import os
from django.http import HttpResponse
import requests
from datetime import date, datetime
import json
from urllib.parse import quote
from book.models import APIKey

load_dotenv()

User = get_user_model()

# -------------------------
# OAuth 설정
# -------------------------
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# -------------------------
# 로그인/로그아웃
# -------------------------
def login_view(request):
    return render(request, 'register/login.html')

def logout_view(request):
    logout(request)
    return redirect("/")

# -------------------------
# 유틸 함수
# -------------------------
def convert_gender(g):
    if g == "male":
        return "M"
    if g == "female":
        return "F"
    return "O"

def calc_age(birthdate_str):
    birth = datetime.strptime(birthdate_str, "%Y-%m-%d").date()
    today = date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

# -------------------------
# 회원가입
# -------------------------
def signup_view(request):
    if not request.user.is_authenticated:
        return redirect("/")

    user = request.user

    if user.is_profile_completed:
        return redirect("/")

    if request.method == "GET":
        return render(request, "register/signup.html", {"user": user})

    if request.method == "POST":
        nickname = request.POST.get("nickname")
        birthdate = request.POST.get("birthdate")
        gender = request.POST.get("gender")
        marketing = request.POST.get("terms_marketing") == "on"
        user_img = request.FILES.get("user-image")
        # 🔴 닉네임 유효성 검사
        if not nickname:
            return render(request, "register/signup.html", {
                "user": user,
                "error": "닉네임을 입력해주세요."
            })
        elif len(nickname) > 20: 
            return render(request, "register/signup.html", {
                "user": user,
                "error": "이름이 너무 깁니다. 20자 이내로 작성해 주세요."
            })

        # 🔴 닉네임 중복 검사 (본인 제외)
        if User.objects.filter(nickname=nickname).exclude(pk=user.user_id).exists():
            return render(request, "register/signup.html", {
                "user": user,
                "error": "이미 사용 중인 닉네임입니다."
            })
        # 사용자 정보 저장
        user.nickname = nickname
        user.birthdate = birthdate
        user.age = calc_age(birthdate)
        user.gender = convert_gender(gender)
        if user_img:
            user.user_img = user_img
        user.is_profile_completed = True
        user.save()

        return redirect("/")

# -------------------------
# 공통 OAuth 콜백 처리
# -------------------------
def _oauth_callback(request, provider, profile_json, uid_key, email_key):
    print(f"🔐 [OAuth Callback] 시작 - Provider: {provider}")

    flutter_redirect_uri = request.session.get('oauth_redirect_uri')
    print(f"📱 [OAuth] Flutter redirect_uri: {flutter_redirect_uri}")

    oauth_id = profile_json.get(uid_key)
    email = profile_json.get(email_key)
    if not email:
        email = f"{provider}_{oauth_id}@example.com"

    print(f"👤 [OAuth] 사용자 정보 - Email: {email}, OAuth ID: {oauth_id}")

    user = User.objects.filter(email=email).first()
    if not user:
        print(f"🆕 [OAuth] 신규 사용자 생성 중...")
        user = User.objects.create(
            username=f"{provider}_{oauth_id}",
            email=email,
            is_profile_completed=False
        )
        print(f"✅ [OAuth] 신규 사용자 생성 완료 - ID: {user.user_id}, Profile Completed: {user.is_profile_completed}")
    else:
        print(f"👤 [OAuth] 기존 사용자 발견 - ID: {user.user_id}, Profile Completed: {user.is_profile_completed}")

    auth_login(request, user)

    # User-Agent로 모바일 WebView 감지
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    is_mobile_webview = 'VoxLiberApp' in user_agent

    api_key_obj = None
    if flutter_redirect_uri or is_mobile_webview:
        api_key_obj = APIKey.objects.filter(user=user, is_active=True, name='모바일 앱').first()
        if not api_key_obj:
            print(f"🆕 [OAuth] API Key가 없음 - 새로 생성")
            api_key_obj = APIKey.objects.create(user=user, name='모바일 앱')
            print(f"✅ [OAuth] API Key 생성 완료: {api_key_obj.key[:10]}...")
        else:
            print(f"🔑 [OAuth] API Key 발견: {api_key_obj.key[:10]}...")

    # 모바일 WebView 처리
    if is_mobile_webview:
        print(f"📱 [OAuth] 모바일 WebView로 리다이렉트")
        return redirect(f'/login/mobile-login-success/{api_key_obj.key}/')

    # Flutter 앱 redirect 처리
    if flutter_redirect_uri:
        request.session.pop('oauth_redirect_uri', None)
        user_data = {
            "id": str(user.public_uuid),
            "username": user.username,
            "nickname": getattr(user, "nickname", ""),
            "email": user.email,
            "profile_img": user.user_img.url if user.user_img else None,
            "is_profile_completed": user.is_profile_completed,
        }
        user_json = quote(json.dumps(user_data))
        state = "signup_required" if not user.is_profile_completed else "signup_complete"

        redirect_url = f"{flutter_redirect_uri}?api_key={api_key_obj.key}&user={user_json}&state={state}"
        print(f"📲 [OAuth] Flutter 앱으로 리다이렉트")
        print(f"   State: {state}")
        print(f"   Is Profile Completed: {user.is_profile_completed}")
        print(f"   Redirect URL: {redirect_url[:100]}...")

        return redirect(redirect_url)

    # 웹 브라우저용 처리
    print(f"🌐 [OAuth] 웹 브라우저용 처리")
    if not user.is_profile_completed:
        print(f"🆕 [OAuth] 프로필 미완성 → /login/signup/으로 이동")
        return redirect('/login/signup/')
    print(f"✅ [OAuth] 프로필 완성 → 홈으로 이동")
    return redirect("/")

# -------------------------
# 카카오 OAuth
# -------------------------
def kakao_login(request):
    flutter_redirect_uri = request.GET.get('redirect_uri')
    if flutter_redirect_uri:
        request.session['oauth_redirect_uri'] = flutter_redirect_uri

    # 동적 Redirect URI 생성
    callback_path = '/login/oauth/kakao/callback/'
    kakao_redirect_uri = request.build_absolute_uri(callback_path)

    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?"
        f"client_id={KAKAO_REST_API_KEY}&redirect_uri={kakao_redirect_uri}&response_type=code"
    )
    return redirect(kakao_auth_url)

def kakao_callback(request):
    code = request.GET.get("code")

    # 동적 Redirect URI 생성
    callback_path = '/login/oauth/kakao/callback/'
    kakao_redirect_uri = request.build_absolute_uri(callback_path)

    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": kakao_redirect_uri,
        "client_secret": KAKAO_CLIENT_SECRET,
        "code": code,
    }
    token_response = requests.post(token_url, data=data).json()
    access_token = token_response.get('access_token')

    profile_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    profile_json = requests.get(profile_url, headers=headers).json()

    return _oauth_callback(request, 'kakao', profile_json, 'id', 'kakao_account')

# -------------------------
# 네이버 OAuth
# -------------------------
def naver_login(request):
    flutter_redirect_uri = request.GET.get('redirect_uri')
    if flutter_redirect_uri:
        request.session['oauth_redirect_uri'] = flutter_redirect_uri

    # 동적 Redirect URI 생성
    callback_path = '/login/oauth/naver/callback/'
    naver_redirect_uri = request.build_absolute_uri(callback_path)

    state = "RANDOM_STATE_STRING"
    naver_auth_url = (
        f"https://nid.naver.com/oauth2.0/authorize?"
        f"response_type=code&client_id={NAVER_CLIENT_ID}&redirect_uri={naver_redirect_uri}&state={state}"
    )
    return redirect(naver_auth_url)

def naver_callback(request):
    code = request.GET.get("code")
    state = request.GET.get("state")

    # 동적 Redirect URI는 토큰 요청 시 필요하지 않음 (state로 검증)
    token_url = "https://nid.naver.com/oauth2.0/token"
    params = {
        "grant_type": "authorization_code",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "code": code,
        "state": state,
    }
    token_response = requests.get(token_url, params=params).json()
    access_token = token_response.get('access_token')

    profile_url = "https://openapi.naver.com/v1/nid/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    profile_json = requests.get(profile_url, headers=headers).json()
    response = profile_json.get("response", {})

    return _oauth_callback(request, 'naver', response, 'id', 'email')

# -------------------------
# 구글 OAuth
# -------------------------
def google_login(request):
    flutter_redirect_uri = request.GET.get('redirect_uri')
    if flutter_redirect_uri:
        request.session['oauth_redirect_uri'] = flutter_redirect_uri

    # 동적 Redirect URI 생성
    callback_path = '/login/oauth/google/callback/'
    google_redirect_uri = request.build_absolute_uri(callback_path)

    scope = "openid email profile"
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={google_redirect_uri}&scope={scope}"
    )
    return redirect(google_auth_url)

def google_callback(request):
    code = request.GET.get("code")

    # 동적 Redirect URI 생성
    callback_path = '/login/oauth/google/callback/'
    google_redirect_uri = request.build_absolute_uri(callback_path)

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": google_redirect_uri,
        "grant_type": "authorization_code",
    }
    token_response = requests.post(token_url, data=data).json()
    access_token = token_response.get("access_token")

    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    profile_json = requests.get(userinfo_url, headers=headers).json()

    return _oauth_callback(request, 'google', profile_json, 'id', 'email')

# -------------------------
# 네이티브 앱 OAuth (Google, Kakao, Naver)
# -------------------------
from django.http import JsonResponse
from book.api_utils import oauth_callback_secure

@oauth_callback_secure
def native_oauth_callback(request, provider):
    """
    Flutter 네이티브 OAuth 콜백
    네이티브 SDK에서 받은 토큰/사용자 정보로 인증 처리
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        print(f"🔐 [Native OAuth] {provider} 인증 요청")
        print(f"   Data: {data}")

        # 이메일 추출
        email = data.get('email')
        user_id = data.get('user_id')

        if not email:
            email = f"{provider}_{user_id}@example.com"

        print(f"👤 [Native OAuth] 사용자 정보 - Email: {email}, User ID: {user_id}")

        # 사용자 찾기 또는 생성
        user = User.objects.filter(email=email).first()
        if not user:
            print(f"🆕 [Native OAuth] 신규 사용자 생성 중...")
            user = User.objects.create(
                username=f"{provider}_{user_id}",
                email=email,
                is_profile_completed=False
            )
            print(f"✅ [Native OAuth] 신규 사용자 생성 완료 - ID: {user.user_id}")
        else:
            print(f"👤 [Native OAuth] 기존 사용자 발견 - ID: {user.user_id}")

        # API Key 생성 또는 가져오기
        api_key_obj = APIKey.objects.filter(user=user, is_active=True, name='모바일 앱').first()
        if not api_key_obj:
            print(f"🆕 [Native OAuth] API Key가 없음 - 새로 생성")
            api_key_obj = APIKey.objects.create(user=user, name='모바일 앱')
            print(f"✅ [Native OAuth] API Key 생성 완료: {api_key_obj.key[:10]}...")
        else:
            print(f"🔑 [Native OAuth] API Key 발견: {api_key_obj.key[:10]}...")

        # 응답 데이터 구성
        user_data = {
            "id":str(user.public_uuid),
            "username": user.username,
            "nickname": getattr(user, "nickname", ""),
            "email": user.email,
            "profile_img": user.user_img.url if user.user_img else None,
            "is_profile_completed": user.is_profile_completed,
        }

        state = "signup_required" if not user.is_profile_completed else "signup_complete"

        response_data = {
            "api_key": api_key_obj.key,
            "user": user_data,
            "state": state,
        }

        print(f"✅ [Native OAuth] 인증 성공")
        print(f"   State: {state}")
        print(f"   Is Profile Completed: {user.is_profile_completed}")

        return JsonResponse(response_data, status=200)

    except Exception as e:
        print(f"❌ [Native OAuth] 에러: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)



# -------------------------
# 모바일 앱 로그인 성공 처리
# -------------------------
def mobile_login_success(request, api_key):
    """
    모바일 앱 OAuth 로그인 성공 페이지
    WebView가 이 URL을 감지하면 API 키를 추출
    """
    return HttpResponse(f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>로그인 성공</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 2rem;
            }}
            .checkmark {{
                font-size: 64px;
                margin-bottom: 1rem;
            }}
            h1 {{
                font-size: 24px;
                margin-bottom: 0.5rem;
            }}
            p {{
                font-size: 16px;
                opacity: 0.9;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="checkmark">✓</div>
            <h1>로그인 성공!</h1>
            <p>잠시만 기다려주세요...</p>
        </div>
    </body>
    </html>
    ''')



# 회원 탈퇴
