from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, login as auth_login, logout
from register.decorator import login_required_to_main
from dotenv import load_dotenv
import os
from django.http import HttpResponse
import requests
from datetime import date, datetime
import json
from urllib.parse import quote
from book.models import APIKey
from register.oauth_google import google_login, google_callback  # noqa: F401

load_dotenv()

User = get_user_model()

# -------------------------
# OAuth 설정
# -------------------------
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# -------------------------
# 로그인/로그아웃
# -------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('main:main')
    return redirect('main:main')

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
    print(f" [OAuth Callback] 시작 - Provider: {provider}")

    flutter_redirect_uri = request.session.get('oauth_redirect_uri')
    print(f" [OAuth] Flutter redirect_uri: {flutter_redirect_uri}")

    oauth_id = profile_json.get(uid_key)
    email = profile_json.get(email_key)
    if not email:
        email = f"{provider}_{oauth_id}@example.com"

    print(f" [OAuth] 사용자 정보 - Email: {email}, OAuth ID: {oauth_id}")

    user = User.objects.filter(email=email).first()
    if not user:
        print(f" [OAuth] 신규 사용자 생성 중...")
        user = User.objects.create(
            username=f"{provider}_{oauth_id}",
            email=email,
            is_profile_completed=False
        )
        print(f" [OAuth] 신규 사용자 생성 완료 - ID: {user.user_id}, Profile Completed: {user.is_profile_completed}")
    else:
        print(f" [OAuth] 기존 사용자 발견 - ID: {user.user_id}, Profile Completed: {user.is_profile_completed}")

    auth_login(request, user)

    # User-Agent로 모바일 WebView 감지
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    is_mobile_webview = 'VoxLiberApp' in user_agent

    api_key_obj = None
    if flutter_redirect_uri or is_mobile_webview:
        api_key_obj = APIKey.objects.filter(user=user, is_active=True, name='모바일 앱').first()
        if not api_key_obj:
            print(f" [OAuth] API Key가 없음 - 새로 생성")
            api_key_obj = APIKey.objects.create(user=user, name='모바일 앱')
            print(f" [OAuth] API Key 생성 완료: {api_key_obj.key[:10]}...")
        else:
            print(f" [OAuth] API Key 발견: {api_key_obj.key[:10]}...")

    # 모바일 WebView 처리
    if is_mobile_webview:
        print(f" [OAuth] 모바일 WebView로 리다이렉트")
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
            "birthdate": str(user.birthdate) if user.birthdate else None,
            "is_adult": user.is_adult(),
        }
        user_json = quote(json.dumps(user_data))
        state = "signup_required" if not user.is_profile_completed else "signup_complete"

        redirect_url = f"{flutter_redirect_uri}?api_key={api_key_obj.key}&user={user_json}&state={state}"
        print(f" [OAuth] Flutter 앱으로 리다이렉트")
        print(f"   State: {state}")
        print(f"   Is Profile Completed: {user.is_profile_completed}")
        print(f"   Redirect URL: {redirect_url[:100]}...")

        return redirect(redirect_url)

    # 웹 브라우저용 처리
    print(f" [OAuth] 웹 브라우저용 처리")
    if not user.is_profile_completed:
        print(f" [OAuth] 프로필 미완성  /login/signup/으로 이동")
        return redirect('/login/signup/')
    print(f" [OAuth] 프로필 완성  홈으로 이동")
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

    # kakao_account 안에 email이 중첩되어 있으므로 플랫하게 변환
    kakao_account = profile_json.get('kakao_account', {})
    flat_profile = {
        'id': profile_json.get('id'),
        'email': kakao_account.get('email', ''),
    }
    return _oauth_callback(request, 'kakao', flat_profile, 'id', 'email')

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
        print(f" [Native OAuth] {provider} 인증 요청")
        print(f"   Data: {data}")

        # 이메일 추출
        email = data.get('email')
        user_id = data.get('user_id')

        if not email:
            email = f"{provider}_{user_id}@example.com"

        print(f" [Native OAuth] 사용자 정보 - Email: {email}, User ID: {user_id}")

        # 사용자 찾기 또는 생성
        user = User.objects.filter(email=email).first()
        if not user:
            print(f" [Native OAuth] 신규 사용자 생성 중...")
            user = User.objects.create(
                username=f"{provider}_{user_id}",
                email=email,
                is_profile_completed=False
            )
            print(f" [Native OAuth] 신규 사용자 생성 완료 - ID: {user.user_id}")
        else:
            print(f" [Native OAuth] 기존 사용자 발견 - ID: {user.user_id}")

        # API Key 생성 또는 가져오기
        api_key_obj = APIKey.objects.filter(user=user, is_active=True, name='모바일 앱').first()
        if not api_key_obj:
            print(f" [Native OAuth] API Key가 없음 - 새로 생성")
            api_key_obj = APIKey.objects.create(user=user, name='모바일 앱')
            print(f" [Native OAuth] API Key 생성 완료: {api_key_obj.key[:10]}...")
        else:
            print(f" [Native OAuth] API Key 발견: {api_key_obj.key[:10]}...")

        # 응답 데이터 구성
        user_data = {
            "id":str(user.public_uuid),
            "username": user.username,
            "nickname": getattr(user, "nickname", ""),
            "email": user.email,
            "profile_img": user.user_img.url if user.user_img else None,
            "is_profile_completed": user.is_profile_completed,
            "birthdate": str(user.birthdate) if user.birthdate else None,
            "is_adult": user.is_adult(),
        }

        state = "signup_required" if not user.is_profile_completed else "signup_complete"

        response_data = {
            "api_key": api_key_obj.key,
            "user": user_data,
            "state": state,
        }

        print(f" [Native OAuth] 인증 성공")
        print(f"   State: {state}")
        print(f"   Is Profile Completed: {user.is_profile_completed}")

        return JsonResponse(response_data, status=200)

    except Exception as e:
        print(f" [Native OAuth] 에러: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)



# -------------------------
# 모바일 앱 로그인 성공 처리
# -------------------------
def mobile_login_success(request, api_key):
    """
    모바일 앱 OAuth 로그인 성공 페이지
    JavaScript 채널을 통해 Flutter WebView에 API 키 전달
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
        <script>
            // Flutter JavaScript 채널로 API 키 전달
            (function() {{
                var apiKey = '{api_key}';
                if (window.FlutterCallback) {{
                    window.FlutterCallback.postMessage(apiKey);
                }}
            }})();
        </script>
    </body>
    </html>
    ''')



from django.shortcuts import render as _render
from django.utils import timezone
from datetime import timedelta

def subscribe_plan(request):
    from register.models import PricePlan, Subscription
    plans = PricePlan.objects.filter(is_active=True)
    subscription = None
    if request.user.is_authenticated:
        try:
            subscription = request.user.subscription
            if not subscription.is_active:
                subscription = None
        except Subscription.DoesNotExist:
            subscription = None
    return _render(request, 'register/subscribe_plan.html', {
        'plans': plans,
        'subscription': subscription,
    })


@login_required_to_main
def subscribe_checkout(request, plan_type):
    from register.models import PricePlan, Subscription
    if plan_type not in ('monthly', 'yearly'):
        return redirect('register:subscribe_plan')

    # 이미 구독 중이면 manage로
    try:
        sub = request.user.subscription
        if sub.is_active:
            return redirect('register:subscription_manage')
    except Subscription.DoesNotExist:
        pass

    try:
        plan = PricePlan.objects.get(plan_type=plan_type, is_active=True)
        price = int(plan.price)
    except PricePlan.DoesNotExist:
        price = 7900 if plan_type == 'monthly' else 80000

    vat = int(price * 0.1)
    total = price + vat
    today = timezone.localdate()

    return _render(request, 'register/subscribe_checkout.html', {
        'plan_type': plan_type,
        'price': price,
        'vat': vat,
        'total': total,
        'today': today,
        'user_email': request.user.email,
    })


@login_required_to_main
def subscribe_process(request, plan_type):
    from register.models import PricePlan, Subscription, PaymentHistory
    if request.method != 'POST':
        return redirect('register:subscribe_checkout', plan_type=plan_type)
    if plan_type not in ('monthly', 'yearly'):
        return redirect('register:subscribe_plan')

    now = timezone.now()
    expires_at = now + timedelta(days=30 if plan_type == 'monthly' else 365)

    try:
        plan_obj = PricePlan.objects.get(plan_type=plan_type, is_active=True)
        amount = int(plan_obj.price)
    except PricePlan.DoesNotExist:
        amount = 7900 if plan_type == 'monthly' else 80000

    try:
        sub = Subscription.objects.get(user=request.user)
        sub.plan = plan_type
        sub.status = 'active'
        sub.started_at = now
        sub.expires_at = expires_at
        sub.cancelled_at = None
        sub.save()
    except Subscription.DoesNotExist:
        Subscription.objects.create(
            user=request.user,
            plan=plan_type,
            status='active',
            started_at=now,
            expires_at=expires_at,
        )

    PaymentHistory.objects.create(
        user=request.user,
        plan=plan_type,
        amount=amount,
        method=request.POST.get('pay_method', 'card') or 'card',
        status='paid',
        receipt_email=request.POST.get('receipt_email', request.user.email) or request.user.email,
    )

    return redirect('register:subscribe_success', plan_type=plan_type)


@login_required_to_main
def subscribe_success(request, plan_type):
    from register.models import PaymentHistory
    latest = PaymentHistory.objects.filter(user=request.user).first()
    return _render(request, 'register/subscribe_success.html', {
        'plan_type': plan_type,
        'payment': latest,
    })


@login_required_to_main
def subscribe_change(request):
    """월간 ↔ 연간 플랜 변경"""
    from register.models import PricePlan, Subscription, PaymentHistory
    try:
        sub = request.user.subscription
        if not sub.is_active:
            return redirect('register:subscribe_plan')
    except Subscription.DoesNotExist:
        return redirect('register:subscribe_plan')

    target_plan = 'yearly' if sub.plan == 'monthly' else 'monthly'

    if request.method == 'POST':
        now = timezone.now()
        expires_at = now + timedelta(days=30 if target_plan == 'monthly' else 365)

        try:
            plan_obj = PricePlan.objects.get(plan_type=target_plan, is_active=True)
            amount = int(plan_obj.price)
        except PricePlan.DoesNotExist:
            amount = 7900 if target_plan == 'monthly' else 80000

        sub.plan = target_plan
        sub.started_at = now
        sub.expires_at = expires_at
        sub.cancelled_at = None
        sub.status = 'active'
        sub.save()

        PaymentHistory.objects.create(
            user=request.user,
            plan=target_plan,
            amount=amount,
            method='admin',
            status='paid',
            receipt_email=request.user.email,
        )

        return redirect('register:subscribe_success', plan_type=target_plan)

    try:
        plan_obj = PricePlan.objects.get(plan_type=target_plan, is_active=True)
        target_price = int(plan_obj.price)
    except PricePlan.DoesNotExist:
        target_price = 7900 if target_plan == 'monthly' else 80000

    return _render(request, 'register/subscribe_change.html', {
        'subscription': sub,
        'target_plan': target_plan,
        'target_price': target_price,
    })


@login_required_to_main
def payment_history(request):
    from register.models import PaymentHistory
    records = PaymentHistory.objects.filter(user=request.user)
    return _render(request, 'register/payment_history.html', {
        'records': records,
    })


@login_required_to_main
def subscription_manage(request):
    from register.models import Subscription, PaymentHistory
    try:
        subscription = request.user.subscription
    except Subscription.DoesNotExist:
        return redirect('register:subscribe_plan')

    payments = PaymentHistory.objects.filter(user=request.user)[:12]

    return _render(request, 'register/subscription_manage.html', {
        'subscription': subscription,
        'payments': payments,
    })


@login_required_to_main
def subscription_cancel(request):
    from register.models import Subscription
    if request.method != 'POST':
        return redirect('register:subscription_manage')

    try:
        sub = request.user.subscription
        sub.status = 'cancelled'
        sub.cancelled_at = timezone.now()
        sub.save()
    except Subscription.DoesNotExist:
        pass

    return redirect('register:subscribe_plan')

def author_center(request):
    return _render(request, 'register/author_center.html')


@login_required_to_main
def author_apply(request):
    from register.models import AuthorApplication
    user = request.user

    # 이미 작가인 경우
    if user.is_author:
        return redirect('register:author_center')

    # 기존 신청 조회
    try:
        application = AuthorApplication.objects.get(user=user)
    except AuthorApplication.DoesNotExist:
        application = None

    if request.method == 'POST':
        if application and application.status == 'pending':
            return redirect('register:author_apply')

        planned_work = request.POST.get('planned_work', '').strip()
        portfolio    = request.POST.get('portfolio', '').strip() or None
        policy_agreed = request.POST.get('policy_agreed') == 'on'

        if not planned_work:
            return _render(request, 'register/author_apply.html', {
                'application': application,
                'error': '작품 소개를 입력해주세요.',
            })
        if not policy_agreed:
            return _render(request, 'register/author_apply.html', {
                'application': application,
                'error': '작가 정책에 동의해주세요.',
            })

        if application:
            application.planned_work = planned_work
            application.portfolio    = portfolio
            application.policy_agreed = policy_agreed
            application.status       = 'pending'
            application.save()
        else:
            AuthorApplication.objects.create(
                user=user,
                planned_work=planned_work,
                portfolio=portfolio,
                policy_agreed=policy_agreed,
            )

        return redirect('register:author_apply')

    return _render(request, 'register/author_apply.html', {'application': application})

def author_inquiry_list(request):
    from register.models import AuthorInquiry
    inquiries = AuthorInquiry.objects.filter(user=request.user, parent__isnull=True).order_by('-created_at') if request.user.is_authenticated else []
    return _render(request, 'register/author_inquiry_list.html', {'inquiries': inquiries})


@login_required_to_main
def author_inquiry_write(request):
    from register.models import AuthorInquiry
    from book.models import Books

    my_books = Books.objects.filter(user=request.user, is_deleted=False)
    category_choices = AuthorInquiry.CATEGORY_CHOICES

    if request.method == 'POST':
        title    = request.POST.get('title', '').strip()
        message  = request.POST.get('message', '').strip()
        category = request.POST.get('category', 'other')
        book_id  = request.POST.get('book_id') or None

        if not title or not message:
            return _render(request, 'register/author_inquiry_write.html', {
                'my_books': my_books, 'category_choices': category_choices,
                'error': '제목과 내용을 입력해주세요.',
                'form': request.POST,
            })

        book = None
        if book_id:
            book = Books.objects.filter(id=book_id, user=request.user).first()

        inq = AuthorInquiry(
            user=request.user, category=category,
            title=title, message=message, book=book,
        )
        if 'attachment' in request.FILES:
            inq.attachment = request.FILES['attachment']
        inq.save()
        from django.contrib import messages
        messages.success(request, '문의가 등록되었습니다.')
        return redirect('register:author_inquiry_detail', inquiry_id=inq.id)

    return _render(request, 'register/author_inquiry_write.html', {
        'my_books': my_books, 'category_choices': category_choices,
    })


@login_required_to_main
def author_inquiry_detail(request, inquiry_id):
    from register.models import AuthorInquiry
    from django.shortcuts import get_object_or_404
    inq = get_object_or_404(AuthorInquiry, id=inquiry_id, user=request.user, parent__isnull=True)
    return _render(request, 'register/author_inquiry_detail.html', {'inq': inq})


@login_required_to_main
def author_inquiry_edit(request, inquiry_id):
    from register.models import AuthorInquiry
    from django.shortcuts import get_object_or_404
    from book.models import Books

    inq = get_object_or_404(AuthorInquiry, id=inquiry_id, user=request.user, parent__isnull=True)

    if inq.status != 'pending':
        from django.contrib import messages
        messages.error(request, '답변이 완료된 문의는 수정할 수 없습니다.')
        return redirect('register:author_inquiry_detail', inquiry_id=inq.id)

    my_books = Books.objects.filter(user=request.user, is_deleted=False)
    category_choices = AuthorInquiry.CATEGORY_CHOICES

    if request.method == 'POST':
        title    = request.POST.get('title', '').strip()
        message  = request.POST.get('message', '').strip()
        category = request.POST.get('category', inq.category)
        book_id  = request.POST.get('book_id') or None

        if not title or not message:
            return _render(request, 'register/author_inquiry_write.html', {
                'my_books': my_books, 'inq': inq,
                'category_choices': category_choices,
                'error': '제목과 내용을 입력해주세요.',
                'form': request.POST,
            })

        inq.title    = title
        inq.message  = message
        inq.category = category
        if book_id:
            inq.book = Books.objects.filter(id=book_id, user=request.user).first()
        if 'attachment' in request.FILES:
            inq.attachment = request.FILES['attachment']
        inq.save()
        from django.contrib import messages
        messages.success(request, '문의가 수정되었습니다.')
        return redirect('register:author_inquiry_detail', inquiry_id=inq.id)

    return _render(request, 'register/author_inquiry_write.html', {
        'my_books': my_books, 'inq': inq, 'category_choices': category_choices,
    })


@login_required_to_main
def author_inquiry_delete(request, inquiry_id):
    from register.models import AuthorInquiry
    from django.shortcuts import get_object_or_404

    inq = get_object_or_404(AuthorInquiry, id=inquiry_id, user=request.user)
    if inq.status == 'pending':
        inq.delete()
        from django.contrib import messages
        messages.success(request, '문의가 삭제되었습니다.')
    return redirect('register:author_inquiry_list')

# 회원 탈퇴
