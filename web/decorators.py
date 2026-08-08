# =====================================================================
# web/decorators.py
#
# 관리자만 들어갈 수 있는 화면으로, 뷰 함수 위에 @admin_required 를 붙이기만 하면, 그 화면은
#   1) 로그인을 안 했으면 로그인 화면으로 보낸다.
#   2) 로그인은 했지만 학생 계정이면 관리자만 접근 가능합니다 화면을 보여준다.
#   3) 관리자 계정(또는 Django 최고관리자)이면 원래 화면을 그대로 보여준다.
# =====================================================================
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect, render


def is_admin_user(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    profile = getattr(user, 'profile', None)
    if profile is not None and profile.role == 'admin':
        return True

    return False


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # 1) 로그인 자체를 안 한 경우 
        if not request.user.is_authenticated:
            return redirect('/login/')

        # 2) 로그인은 했지만 관리자가 아닌 경우 
        if not is_admin_user(request.user):
            if request.method == "POST" or request.content_type == "application/json":
                return JsonResponse(
                    {"success": False, "error": "관리자만 접근할 수 있습니다."},
                    status=403,
                )
            return render(request, 'web/403.html', status=403)

        # 3) 관리자인 경우 
        return view_func(request, *args, **kwargs)

    return wrapper
