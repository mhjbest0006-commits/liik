# views.py
import json
import os
from datetime import datetime, timedelta  # timedelta는 혼잡 자동 알림 중복 방지에 사용한다.

from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q  # 공지 목록을 전체 공지 OR 우리 반 공지로 필터링할 때 사용한다.
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from rest_framework import generics, status as drf_status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

from .models import (
    Class, MealStatus, Student, WaitLog, UserProfile, Announcement,
    ClassMealOrder,  # 월별 홀수반/짝수반 배식 순서를 저장하는 모델
)
# 문자와 식, 확률, 통계, 일차함수, 일차부등식을 계산해 주는 함수들
from .stats import (
    calculate_expected_wait,
    check_congestion,
    calculate_congestion_probability,
    calculate_hourly_statistics,
    fit_linear_wait_model,
    predict_actual_wait,
    # 번호 순서를 반영한 대기인원 계산 + 새치기 판단 함수
    calculate_own_class_ahead_count,
    detect_line_cut,
    calculate_other_class_ahead_count,
    # 1) 혼잡한 상황 => 다음반 담임에게 공지 자동 등록 시"다음 반을 찾는 함수
    find_next_class_in_queue,
)
from .serializers import LoginSerializer
from .decorators import admin_required, is_admin_user  # is_admin_user는 공지 목록 필터링에 쓴다.


def create_initial_user():
    username = os.environ.get('INITIAL_ADMIN_USERNAME', 'hyun_gun')
    password = os.environ.get('INITIAL_ADMIN_PASSWORD')
    if not password:
        return
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, password=password)
        Token.objects.get_or_create(user=user)
        user.profile.role = UserProfile.ROLE_ADMIN
        user.profile.save()


try:
    create_initial_user()
except Exception:
    pass


#  DRF 기반 로그인 
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data
        return Response({"success": True, "token": token.key}, status=drf_status.HTTP_200_OK)

    def get(self, request):
        return render(request, "web/login.html")


#  전통 HTML 로그인 
@csrf_exempt
def login(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)
            token, _ = Token.objects.get_or_create(user=user)
            return JsonResponse({"success": True, "token": token.key})
        return JsonResponse({"success": False, "error": "아이디 또는 비밀번호가 틀렸습니다."})
    return render(request, 'web/login.html')


#  로그아웃 
@login_required
def logout_view(request):
    auth_logout(request)
    return redirect('/login/')


# =====================================================================
# 회원가입 — 관리자 계정 / 학생 계정을 따로 만든다.
#
#  학생 계정은 아무나 만들 수 있으면 안 되고, 반드시 본인의 학생증으로 확인이 되어야 한다. 
# 그래서 학생으로 가입할 때는 아이디/비밀번호 외에도 반(class_id), 번호(number), 학생증 바코드(barcode) 3가지를 추가로 받아서 관리자가 미리 등록해 둔 Student 기록과 일치하는지 확인한다.
# =====================================================================
@csrf_exempt
def signup(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")
        role = data.get("role")         
        admin_code = data.get("admin_code", "")

        class_id = data.get("class_id")
        number = data.get("number")
        barcode = data.get("barcode")

        if not username or not password or not role:
            return JsonResponse({"success": False, "error": "아이디, 비밀번호, 계정 종류를 모두 입력해주세요."})

        if role not in (UserProfile.ROLE_ADMIN, UserProfile.ROLE_STUDENT):
            return JsonResponse({"success": False, "error": "계정 종류가 올바르지 않습니다."})

        if role == UserProfile.ROLE_ADMIN:
            if admin_code != settings.ADMIN_SIGNUP_CODE:
                return JsonResponse({"success": False, "error": "관리자 가입 코드가 올바르지 않습니다."})

        matched_student = None
        if role == UserProfile.ROLE_STUDENT:
            if not class_id or not number or not barcode:
                return JsonResponse({
                    "success": False,
                    "error": "학생 가입은 반, 번호, 학생증 스캔이 모두 필요합니다.",
                })

            try:
                matched_student = Student.objects.get(
                    cls__cls_id=class_id, number=number, barcode=barcode
                )
            except Student.DoesNotExist:
                return JsonResponse({
                    "success": False,
                    "error": "학생증 정보가 등록된 내용과 일치하지 않습니다. 반/번호를 확인하거나 학생증을 다시 스캔해주세요.",
                })

            # 중복 가입
            if matched_student.user is not None:
                return JsonResponse({
                    "success": False,
                    "error": "이미 이 학생증으로 가입된 계정이 있습니다.",
                })

        # 이미 있는 아이디인지 확인
        if User.objects.filter(username=username).exists():
            return JsonResponse({"success": False, "error": "이미 사용 중인 아이디입니다."})

        user = User.objects.create_user(username=username, password=password)
        user.profile.role = role
        user.profile.save()

        if role == UserProfile.ROLE_STUDENT and matched_student is not None:
            matched_student.user = user
            matched_student.save()

        return JsonResponse({
            "success": True,
            "message": "회원가입이 완료되었습니다. 로그인해주세요.",
        })

    return render(request, 'web/signup.html')


#  index 페이지 
def index(request):
    return render(request, 'web/index.html')


#  regist 페이지 
@admin_required
def regist(request):
    return render(request, "web/regist.html")


#  반 개수 등록 
@admin_required
@csrf_exempt
def set_classrooms(request):
    if request.method == "POST":
        data = json.loads(request.body)
        count = int(data.get("count", 0))
        Class.objects.all().delete()
        for i in range(1, count + 1):
            Class.objects.update_or_create(cls_id=i, defaults={"cls_id": i, "name": f"{i}반"})
        return JsonResponse({"success": True})
    return render(request, "web/regist.html")


#  반 목록 조회 
@admin_required
def get_classrooms(request):
    classrooms = Class.objects.all().values("cls_id", "name")
    return JsonResponse(list(classrooms), safe=False)


#  학생 등록 
@admin_required
@csrf_exempt
def add_student(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            class_id = data.get("class_id")
            number = data.get("number")
            barcode = data.get("barcode")

            if not class_id or not number or not barcode:
                return JsonResponse({"success": False, "error": "반, 번호, 바코드는 필수 입력사항입니다."})

            try:
                classroom = Class.objects.get(cls_id=class_id)
            except Class.DoesNotExist:
                return JsonResponse({"success": False, "error": "존재하지 않는 반입니다."})

            if Student.objects.filter(barcode=barcode).exists():
                return JsonResponse({"success": False, "error": "이미 등록된 바코드입니다."})

            if Student.objects.filter(cls=classroom, number=number).exists():
                return JsonResponse({"success": False, "error": f"{classroom.name}에 {number}번 학생이 이미 존재합니다."})

            student = Student.objects.create(
                cls=classroom,
                number=int(number),
                barcode=barcode
            )

            return JsonResponse({
                "success": True,
                "message": f"{classroom.name} {number}번 학생이 등록되었습니다.",
                "student": {
                    "id": student.id,
                    "classroom": classroom.name,
                    "number": student.number,
                    "barcode": student.barcode
                }
            })

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "잘못된 JSON 형식입니다."})
        except ValueError:
            return JsonResponse({"success": False, "error": "번호는 숫자여야 합니다."})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"서버 오류: {str(e)}"})

    return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})


#  학생 목록 조회 
# 결석 처리 : 결석 체크 화면(regist.html)에서 학생별로 결석 여부를 보여주고 체크할 수 있어야 하므로, is_absent / has_eaten / cls_id 값과 번호 순서 정렬을 함께 내려주도록 바꿨다.
@admin_required
def get_students(request):
    students = Student.objects.all().select_related("cls").order_by("cls__cls_id", "number")
    data = [
        {
            "id": s.id,
            "cls": s.cls.name,
            "cls_id": s.cls.cls_id,     
            "number": s.number,
            "barcode": s.barcode,
            "has_eaten": s.has_eaten,   
            "is_absent": s.is_absent,    
        }
        for s in students
    ]
    return JsonResponse(data, safe=False)


# =====================================================================
# 결석 체크 / 해제
#
# 관리자가 결석한 학생을 체크하는 화면. is_absent가 True인 학생은 stats.py의 계산 함수들(같은 반 앞번호 대기인원,
# =====================================================================
@admin_required
@csrf_exempt
def set_student_absence(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "잘못된 JSON 형식입니다."})

    student_id = data.get("student_id")
    is_absent = data.get("is_absent")

    if student_id is None or is_absent is None:
        return JsonResponse({"success": False, "error": "student_id와 is_absent 값이 모두 필요합니다."})

    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return JsonResponse({"success": False, "error": "존재하지 않는 학생입니다."})

    student.is_absent = bool(is_absent)
    student.save()

    meal_status, _ = MealStatus.objects.get_or_create(
        cls=student.cls,
        defaults={'total': student.cls.student_set.filter(is_absent=False).count(), 'current': 0}
    )
    meal_status.total = student.cls.student_set.filter(is_absent=False).count()
    meal_status.current = student.cls.student_set.filter(is_absent=False, has_eaten=True).count()
    meal_status.save()

    if student.is_absent:
        message = f"{student.cls.name} {student.number}번 학생을 결석 처리했습니다."
    else:
        message = f"{student.cls.name} {student.number}번 학생의 결석 처리를 해제했습니다."

    return JsonResponse({
        "success": True,
        "message": message,
        "student": {"id": student.id, "is_absent": student.is_absent},
    })


# =====================================================================
# 월별 홀수반/짝수반 배식 순서 조회 / 저장
# 매달 관리자가 홀수반은 어느 반이 먼저 먹는지, 짝수반은 어느 반이 먼저 먹는지를 다시 정할 수 있도록 만든 화면(API)이다.
#   1) get_class_meal_order : 특정 연/월의 현재 순서를 조회한다.
#   2) set_class_meal_order : 특정 연/월의 순서를 저장(갱신)한다.
# 반이 홀수반인지 짝수반인지는 반 번호(cls_id)의 홀/짝으로 자동 판단한다.
# =====================================================================
@admin_required
def get_class_meal_order(request):
    year_param = request.GET.get("year")
    month_param = request.GET.get("month")

    if year_param and month_param:
        year = int(year_param)
        month = int(month_param)
    else:
        # 연/월을 안 주면 오늘 날짜 기준으로 보여준다.
        today = now()
        year = today.year
        month = today.month

    # 1) 이번에 조회한 연/월에 이미 저장된 순서가 있으면 반별로 모아둔다.
    saved_orders = ClassMealOrder.objects.filter(year=year, month=month)
    cls_id_to_order_no = {}
    for o in saved_orders:
        cls_id_to_order_no[o.cls.cls_id] = o.order_no

    # 2) 전체 반을 홀수반/짝수반으로 나누고, 저장된 순서가 있으면 함께 담는다.
    odd_classes = []
    even_classes = []
    for c in Class.objects.all().order_by("cls_id"):
        item = {
            "cls_id": c.cls_id,
            "name": c.name,
            "order_no": cls_id_to_order_no.get(c.cls_id),   # 아직 안 정해졌으면 None
        }
        if c.cls_id % 2 == 0:
            even_classes.append(item)
        else:
            odd_classes.append(item)

    return JsonResponse({
        "success": True,
        "year": year,
        "month": month,
        "odd_classes": odd_classes,
        "even_classes": even_classes,
    })


@admin_required
@csrf_exempt
def set_class_meal_order(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "잘못된 JSON 형식입니다."})

    year = data.get("year")
    month = data.get("month")
    orders = data.get("orders", [])

    if not year or not month or not orders:
        return JsonResponse({"success": False, "error": "연도, 월, 순서 목록이 모두 필요합니다."})

    # 1) 저장하기 전에, 같은 그룹(홀수반/짝수반) 안에서 순서 번호가 겹치지 않는지 먼저 검사한다. (겹치면 어떤 반이 먼저인지 알 수 없다)
    group_to_used_numbers = {ClassMealOrder.GROUP_ODD: [], ClassMealOrder.GROUP_EVEN: []}
    checked_items = []   # (Class객체, group, order_no)를 순서대로 담아둔다.

    for item in orders:
        cls_id = item.get("cls_id")
        order_no = item.get("order_no")
        if cls_id is None or order_no is None:
            return JsonResponse({"success": False, "error": "cls_id와 order_no는 모두 필요합니다."})

        try:
            classroom = Class.objects.get(cls_id=cls_id)
        except Class.DoesNotExist:
            return JsonResponse({"success": False, "error": f"존재하지 않는 반입니다. (cls_id={cls_id})"})

        # 반 번호(cls_id)의 홀/짝으로 그룹을 자동으로 정한다.
        if classroom.cls_id % 2 == 0:
            group = ClassMealOrder.GROUP_EVEN
            group_label = "짝수반"
        else:
            group = ClassMealOrder.GROUP_ODD
            group_label = "홀수반"

        order_no = int(order_no)
        if order_no in group_to_used_numbers[group]:
            return JsonResponse({
                "success": False,
                "error": f"{group_label} 안에서 순서 {order_no}번이 중복되었습니다.",
            })
        group_to_used_numbers[group].append(order_no)

        checked_items.append((classroom, group, order_no))

    # 2) 검사를 통과했으면 실제로 저장한다.
    for classroom, group, order_no in checked_items:
        ClassMealOrder.objects.update_or_create(
            cls=classroom, year=int(year), month=int(month),
            defaults={"group": group, "order_no": order_no},
        )

    return JsonResponse({
        "success": True,
        "message": f"{year}년 {month}월 배식 순서가 저장되었습니다. 지금부터 이 순서를 기준으로 대기인원을 계산합니다.",
    })


#   혼잡한 상황 => 다음반 담임에게 공지 자동 등록
AUTO_NOTICE_DEDUP_MINUTES = 5   # [같은 반에게 자동 알림을 다시 보내기까지 최소로 기다리는 시간(분)


def notify_next_class_about_congestion(current_class, waiting_count, expected_wait_seconds, scan_time):
    # 1) 다음 반을 찾는다.
    next_class = find_next_class_in_queue(current_class, scan_time.year, scan_time.month)
    if next_class is None:
        return None

    # 최근 몇 분 안에 이미 같은 반을 대상으로 한 자동 알림이 있는지 확인한다.
    dedup_since = scan_time - timedelta(minutes=AUTO_NOTICE_DEDUP_MINUTES)
    already_notified_recently = Announcement.objects.filter(
        target_class=next_class,
        is_auto=True,
        created_at__gte=dedup_since,
    ).exists()
    if already_notified_recently:
        return None

    # 다음 반을 대상으로 하는 공지를 새로 만든다.
    title = f"[자동 혼잡 알림] {next_class.name} 담임 선생님께"
    content = (
        f"{current_class.name}의 배식 대기인원이 {waiting_count}명이라 "
        f"예상 대기시간이 약 {round(expected_wait_seconds)}초로 혼잡합니다.\n"
        f"{next_class.name}은 다음 순서로 배식받는 반이니, 학생들이 급식실 앞에 "
        "너무 일찍 모이지 않도록 이동 시간을 조금 늦춰주시면 대기줄이 덜 붐빌 수 있습니다."
    )
    announcement = Announcement.objects.create(
        title=title,
        content=content,
        author=None,             # 사람이 아니라 시스템이 자동으로 쓴 공지이므로 작성자는 비워둔다.
        target_class=next_class,
        is_auto=True,
    )
    return announcement


#  바코드 인식 (배식 체크) 
@admin_required
@csrf_exempt
def scan_barcode(request):
    if request.method == "POST":
        data = json.loads(request.body)
        barcode = data.get("barcode")
        try:
            student = Student.objects.get(barcode=barcode)
        except Student.DoesNotExist:
            return JsonResponse({"success": False, "message": "등록되지 않은 바코드"})

        if student.has_eaten:
            return JsonResponse({"success": False, "message": "이미 배식 완료"})

        # 결석 처리 결석 처리된 학생은 애초에 급식실에 없어야 하므로 학생증이 찍혀도 배식 처리를 하지 않는다. (관리자가 결석을 잘못 눌렀다면 regist.html의 결석 체크를 먼저 해제한 뒤 다시 찍어야 한다)
        if student.is_absent:
            return JsonResponse({
                "success": False,
                "message": "결석 처리된 학생입니다. 결석 처리를 먼저 해제해주세요.",
            })

        scan_time = now()

        own_class_ahead_count = calculate_own_class_ahead_count(student.cls, student.number)

        other_class_ahead_count = calculate_other_class_ahead_count(
            student.cls, scan_time.year, scan_time.month
        )

        waiting_count = own_class_ahead_count + other_class_ahead_count
        service_time_per_person = settings.MEAL_SERVICE_TIME_PER_PERSON
        expected_wait_seconds = calculate_expected_wait(waiting_count, service_time_per_person)
        is_congested = check_congestion(waiting_count, expected_wait_seconds)

        auto_notice = None
        if is_congested:
            auto_notice = notify_next_class_about_congestion(
                student.cls, waiting_count, expected_wait_seconds, scan_time
            )

        # 새치기 판단 :  나보다 번호가 작은데 아직 안 먹은(결석 아닌) 학생이 우리 반에 남아있다면, 그 학생들을 제치고 먼저 찍은 것이다.
        is_line_cut, skipped_numbers = detect_line_cut(student.cls, student.number)
        skipped_numbers_text = ",".join(str(n) for n in skipped_numbers)

        last_log = WaitLog.objects.filter(cls=student.cls).order_by('-scanned_at').first()

        actual_wait_seconds = None
        if last_log is not None:
            time_diff = scan_time - last_log.scanned_at
            actual_wait_seconds = time_diff.total_seconds()

        # 위에서 구한 값들을 한 줄의 기록(WaitLog)으로 저장한다.
        WaitLog.objects.create(
            cls=student.cls,
            scanned_at=scan_time,
            waiting_count=waiting_count,
            service_time_per_person=service_time_per_person,
            expected_wait_seconds=expected_wait_seconds,
            actual_wait_seconds=actual_wait_seconds,
            is_congested=is_congested,
            own_class_ahead_count=own_class_ahead_count,       
            other_class_ahead_count=other_class_ahead_count,    
            is_line_cut=is_line_cut,                          
            skipped_student_numbers=skipped_numbers_text,      
            scanned_student_number=student.number,            
        )

        student.has_eaten = True
        student.save()

        meal_status, _ = MealStatus.objects.get_or_create(
            cls=student.cls,
            defaults={'total': student.cls.student_set.filter(is_absent=False).count(), 'current': 0}
        )
        meal_status.total = student.cls.student_set.filter(is_absent=False).count()
        meal_status.current = student.cls.student_set.filter(is_absent=False, has_eaten=True).count()
        meal_status.save()

        # 문자와 식(예상 대기시간)과 일차부등식(혼잡 여부) 계산 결과를 함께 화면에 보여주기 위한 안내 문구를 만든다.
        if is_congested:
            congestion_message = (
                "혼잡 경고: 대기인원 " + str(waiting_count) + "명 / "
                "예상 대기시간 " + str(round(expected_wait_seconds)) + "초"
            )
        else:
            congestion_message = "정상 (혼잡 아님)"

        # 새치기 알림 문구 새치기라면 몇 번 학생을 제치고 찍었는지 알려준다.
        if is_line_cut:
            line_cut_message = (
                str(student.number) + "번 학생이 " +
                ", ".join(str(n) + "번" for n in skipped_numbers) +
                " 학생보다 먼저 찍었습니다. (새치기로 기록되었습니다)"
            )
        else:
            line_cut_message = None

        return JsonResponse({
            "success": True,
            "message": f"{student.cls.name} {student.number}번 배식 완료",
            "student": {
                "cls_name": student.cls.name,
                "number": student.number,
                "barcode": student.barcode,
            },
            # 위에서 계산한 값들을 스캔 응답에 함께 담아 보낸다. 이렇게 하면 키오스크 화면(scan.html)이 바로 예상 대기시간과 혼잡 경고, 새치기 여부를 보여줄 수 있다.
            "wait_info": {
                "waiting_count": waiting_count,
                "own_class_ahead_count": own_class_ahead_count,       
                "other_class_ahead_count": other_class_ahead_count,   
                "service_time_per_person": service_time_per_person,
                "expected_wait_seconds": expected_wait_seconds,
                "is_congested": is_congested,
                "congestion_message": congestion_message,
                "is_line_cut": is_line_cut,                            
                "skipped_numbers": skipped_numbers,                    
                "line_cut_message": line_cut_message,                  
                # 혼잡 자동 알림이 실제로 다음 반에게 전송됐다면 그 반 이름을, 아니라면(다음 반이 없거나 최근에 이미 보냈다면) null을 내려준다.
                "auto_notice_sent_to": auto_notice.target_class.name if auto_notice else None,
            },
        })
    return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})


# =====================================================================
# [확률, 통계, 일차함수 결과를 각각 보여주는 화면
# login_required(로그인만 하면 접근 가능)로 둔다.
# =====================================================================

#  혼잡 확률 조회 
@login_required
def congestion_probability(request):
    logs = WaitLog.objects.all()                          # 1) 전체 기록 가져오기
    class_id = request.GET.get("class_id")
    if class_id:
        logs = logs.filter(cls__cls_id=class_id)          # 2) 반 골라내기 (선택)

    result = calculate_congestion_probability(logs)        # 3) 확률 계산
    return JsonResponse({"success": True, **result})




#  [시간대별 혼잡도 통계 조회 
@login_required
def time_statistics(request):
    logs = WaitLog.objects.all()                          # 1) 전체 기록 가져오기
    class_id = request.GET.get("class_id")
    if class_id:
        logs = logs.filter(cls__cls_id=class_id)          # 2) 반 골라내기 (선택)

    result = calculate_hourly_statistics(logs)              # 3) 통계 계산
    return JsonResponse({"success": True, **result})


#   대기인원-대기시간 관계식 조회 
@login_required
def linear_wait_model(request):
    logs = WaitLog.objects.all()                          # 1) 전체 기록 가져오기
    class_id = request.GET.get("class_id")
    if class_id:
        logs = logs.filter(cls__cls_id=class_id)          # 2) 반 골라내기 (선택)

    model = fit_linear_wait_model(logs)                     # 3) 일차함수(a, b) 계산

    prediction = None
    waiting_count_param = request.GET.get("waiting_count")
    if waiting_count_param is not None:                     # 4) 예측값 계산 (선택)
        try:
            prediction = predict_actual_wait(int(waiting_count_param), model)
        except ValueError:
            prediction = None

    return JsonResponse({"success": True, "model": model, "prediction": prediction})


#  배식 완료 취소
@admin_required
@csrf_exempt
def mark_absent(request):
    if request.method == "POST":
        data = json.loads(request.body)
        barcode = data.get("barcode")
        if not barcode:
            return JsonResponse({"success": False, "error": "바코드가 없습니다."})
        try:
            student = Student.objects.get(barcode=barcode)
        except Student.DoesNotExist:
            return JsonResponse({"success": False, "error": "등록되지 않은 바코드"})

        student.has_eaten = False
        student.save()

        # total/current 모두 결석(is_absent=True) 학생은 빼고 계산한다.
        meal_status, _ = MealStatus.objects.get_or_create(
            cls=student.cls,
            defaults={'total': student.cls.student_set.filter(is_absent=False).count(), 'current': 0}
        )
        meal_status.total = student.cls.student_set.filter(is_absent=False).count()
        meal_status.current = student.cls.student_set.filter(is_absent=False, has_eaten=True).count()
        meal_status.save()

        return JsonResponse({"success": True, "student": str(student)})
    return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})


#  새치기 기록 조회 
@admin_required
def line_cut_logs(request):
    logs = WaitLog.objects.filter(is_line_cut=True).select_related('cls').order_by('-scanned_at')[:50]

    data = []
    for log in logs:
        data.append({
            "cls_name": log.cls.name,
            "scanned_at": log.scanned_at.strftime("%Y-%m-%d %H:%M:%S"),
            "scanned_student_number": log.scanned_student_number,
            "skipped_student_numbers": log.skipped_student_numbers,
        })

    return JsonResponse({"success": True, "logs": data})


#  반별 급식 현황 대시보드(데이터) 
@admin_required
def meal_dashboard(request):
    data = []
    for cls in Class.objects.all().order_by('cls_id'):
        total_present = cls.student_set.filter(is_absent=False).count()
        current_eaten = cls.student_set.filter(is_absent=False, has_eaten=True).count()
        data.append({"class": cls.name, "total": total_present, "current": current_eaten})
    return JsonResponse({'records': data, 'date': str(now().date())})


# [급식 현황 데이터 삭제/초기화
#
# 이전에는 has_eaten과 MealStatus가 계속 누적되기만 해서, 하루가 지나도 이미 배식 완료인 상태가 그대로 남아있고, WaitLog도 계속 쌓이기만 하는 문제가 있었다. 관리자가 필요할 때 직접 정리할 수 있도록 아래 두 화면을 만들었다.
#   1) reset_daily_meal_status : 오늘 배식 완료 상태를 전부 초기화한다. (다음 끼니/다음 날을 새로 시작할 때 사용한다)
#   2) reset_wait_logs : 혼잡도 계산에 쓰인 오래된 기록(WaitLog)을 관리자가 고른 기준으로 직접 삭제한다.

#  오늘 배식 상태 초기화 
@admin_required
@csrf_exempt
def reset_daily_meal_status(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})

    Student.objects.all().update(has_eaten=False, is_absent=False)

    for meal_status in MealStatus.objects.all():
        meal_status.current = 0
        meal_status.total = meal_status.cls.student_set.count()
        meal_status.save()

    return JsonResponse({"success": True, "message": "오늘 급식 현황이 초기화되었습니다."})


# ----------------- 오래된 WaitLog 삭제 
@admin_required
@csrf_exempt
def reset_wait_logs(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "잘못된 JSON 형식입니다."})

    mode = data.get("mode")

    if mode == "all":
        # 2) 전체 기록을 지운다.
        target_logs = WaitLog.objects.all()
    elif mode == "before_date":
        # 1) 기준 날짜보다 이전 기록만 지운다.
        before_date_text = data.get("before_date")
        if not before_date_text:
            return JsonResponse({"success": False, "error": "삭제 기준 날짜(before_date)가 필요합니다."})
        try:
            before_date = datetime.strptime(before_date_text, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"success": False, "error": "날짜 형식이 올바르지 않습니다. (예: 2026-08-01)"})
        target_logs = WaitLog.objects.filter(scanned_at__date__lt=before_date)
    else:
        return JsonResponse({"success": False, "error": "mode 값은 'all' 또는 'before_date' 여야 합니다."})

    deleted_count = target_logs.count()
    target_logs.delete()

    return JsonResponse({
        "success": True,
        "message": f"{deleted_count}건의 기록이 삭제되었습니다.",
        "deleted_count": deleted_count,
    })


#  급식 현황 화면 
@admin_required
def status_page(request):
    return render(request, 'web/status.html')


#  공지 페이지 
# 학생 계정도 볼 수 있어야 하므로 login_required(로그인만 하면 접근 가능)로 그대로 둔다.
@login_required
def announce(request):
    return render(request, 'web/announce.html')


#   혼잡도 분석 화면 
@login_required
def congestion_page(request):
    return render(request, 'web/congestion.html')


# 공지사항 목록 조회 / 작성 / 삭제
#   1) 목록 조회는 로그인만 하면 누구나(관리자든 학생이든) 할 수 있다.
#   2) 작성과 삭제는 관리자만 할 수 있다. (admin_required로 막는다)

#  [보완] 공지 목록 조회 
@login_required
def list_announcements(request):
    is_admin = is_admin_user(request.user)

    if is_admin:
        # 1) 관리자는 전체 공지 + 모든 반 대상 공지를 다 본다.
        announcements = Announcement.objects.all()
    else:
        # 2) 학생은 전체 공지 + 내 반 대상 공지만 본다.
        my_student = getattr(request.user, 'student_profile', None)
        if my_student is not None:
            announcements = Announcement.objects.filter(
                Q(target_class__isnull=True) | Q(target_class=my_student.cls)
            )
        else:
            announcements = Announcement.objects.filter(target_class__isnull=True)

    data = []
    for a in announcements:
        author_name = "관리자"
        if a.author is not None:
            author_name = a.author.username
        elif a.is_auto:
            author_name = "자동 알림(시스템)"

        data.append({
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "author": author_name,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M"),
            "target_class_name": a.target_class.name if a.target_class else None,
            "is_auto": a.is_auto,
        })

    return JsonResponse({"success": True, "announcements": data})


#   공지 작성 
@admin_required
@csrf_exempt
def create_announcement(request):
    if request.method == "POST":
        data = json.loads(request.body)
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
        target_class_id = data.get("target_class_id")   # 없거나 빈 값이면 전체 공지다.

        if not title or not content:
            return JsonResponse({"success": False, "error": "제목과 내용을 모두 입력해주세요."})

        # target_class_id가 왔다면 실제로 존재하는 반인지 확인한다.
        target_class = None
        if target_class_id:
            try:
                target_class = Class.objects.get(cls_id=target_class_id)
            except Class.DoesNotExist:
                return JsonResponse({"success": False, "error": "존재하지 않는 반입니다."})

        announcement = Announcement.objects.create(
            title=title,
            content=content,
            author=request.user,
            target_class=target_class,   
        )

        return JsonResponse({
            "success": True,
            "message": "공지가 등록되었습니다.",
            "announcement": {
                "id": announcement.id,
                "title": announcement.title,
                "content": announcement.content,
                "author": request.user.username,
                "created_at": announcement.created_at.strftime("%Y-%m-%d %H:%M"),
                "target_class_name": target_class.name if target_class else None, 
                "is_auto": False, 
            },
        })

    return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})


#  공지 삭제  
@admin_required
@csrf_exempt
def delete_announcement(request, announcement_id):
    if request.method == "POST":
        try:
            announcement = Announcement.objects.get(id=announcement_id)
        except Announcement.DoesNotExist:
            return JsonResponse({"success": False, "error": "존재하지 않는 공지입니다."})

        announcement.delete()
        return JsonResponse({"success": True, "message": "공지가 삭제되었습니다."})

    return JsonResponse({"success": False, "error": "POST 요청만 허용됩니다."})


#  학생증 스캔(키오스크) 화면 
@admin_required
def scan_page(request):
    return render(request, 'web/scan.html')

