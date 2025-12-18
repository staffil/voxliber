from django.shortcuts import redirect
from functools import wraps

def login_required_popup(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        # ✅ 로그인 안했으면 너의 로그인 페이지로 보내버림
        return redirect("/login/?next=" + request.path)

    return wrapper
