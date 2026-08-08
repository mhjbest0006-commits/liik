from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User          # 계정 종류 구분을 위해 User를 가져온다.
from django.db.models.signals import post_save        # 회원가입 시 자동으로 프로필을 만들기 위한 신호다.
from django.dispatch import receiver


# =====================================================================
#UserProfile
# =====================================================================
class UserProfile(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_STUDENT = 'student'
    ROLE_CHOICES = [
        (ROLE_ADMIN, '관리자'),
        (ROLE_STUDENT, '학생'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STUDENT)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


# 새로운 User가 만들어질 때마다(회원가입 등) 자동으로 UserProfile을 하나씩 만들어 준다. 기본값은 학생으로 두고, 필요한 곳(관리자 회원가입 등)에서 나중에 role 값을 admin으로 바꿔준다.
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance, defaults={'role': UserProfile.ROLE_STUDENT})


class Class(models.Model):
    name = models.CharField(max_length=50)
    cls_id = models.IntegerField(unique=True, default=0)

    def __str__(self):
        return self.name


class Student(models.Model):
    name = models.CharField(max_length=50, default="학생")
    cls = models.ForeignKey(Class, on_delete=models.CASCADE)
    number = models.IntegerField(default=0)
    barcode = models.CharField(max_length=50, unique=True)
    has_eaten = models.BooleanField(default=False)

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile'
    )

    # =================================================================
    # is_absent
    # =================================================================
    is_absent = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.number}번 - {self.barcode}'


class MealStatus(models.Model):
    cls = models.ForeignKey(Class, on_delete=models.CASCADE)
    current = models.IntegerField(default=0)
    total = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.cls.name}: {self.current}/{self.total}"


# =====================================================================
#  ClassMealOrder (홀 짝 순서)
# =====================================================================
class ClassMealOrder(models.Model):
    GROUP_ODD = 'odd'
    GROUP_EVEN = 'even'
    GROUP_CHOICES = [
        (GROUP_ODD, '홀수반'),
        (GROUP_EVEN, '짝수반'),
    ]

    cls = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='meal_orders')
    year = models.IntegerField()
    month = models.IntegerField()

    # cls.cls_id의 홀/짝으로 자동 계산해서 저장해 둔다. (조회를 쉽게 하기 위함)
    group = models.CharField(max_length=10, choices=GROUP_CHOICES)

    order_no = models.IntegerField()

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cls', 'year', 'month') 
        ordering = ['year', 'month', 'group', 'order_no']

    def __str__(self):
        group_label = '홀수반' if self.group == self.GROUP_ODD else '짝수반'
        return f"{self.year}년 {self.month}월 {self.cls.name} ({group_label} {self.order_no}번째)"


# =====================================================================
#  WaitLog
# =====================================================================
class WaitLog(models.Model):
    cls = models.ForeignKey(Class, on_delete=models.CASCADE)
    scanned_at = models.DateTimeField(default=timezone.now)

    # 문자와 식] 학생증을 찍은 순간의 대기인원 x(명)을 저장한다.
    waiting_count = models.IntegerField(default=0)

    # 문자와 식] 그 순간의 1인당 배식시간 t(초)를 저장한다.
    service_time_per_person = models.FloatField(default=3.0)

    # 문자와 식] x * t 로 계산한 예상 대기시간(초)을 저장한다.
    expected_wait_seconds = models.FloatField(default=0.0)

    # 실제로 걸린 대기시간(초)을 저장한다.
    # 값을 구하는 방법은 다음과 같다.
    #   1) 같은 반에서 바로 앞 학생이 배식받은 시각을 찾는다.
    #   2) 지금 이 학생이 배식받은 시각에서 앞 학생의 시각을 뺀다.
    #   3) 그 차이(초)를 "실제 대기시간"으로 본다.
    # 이렇게 모은 (대기인원, 실제 대기시간) 데이터를 가지고 뒤에서 일차함수 y = a*x + b를 구한다.
    actual_wait_seconds = models.FloatField(null=True, blank=True)

    # waiting_count를 두 부분으로 나누어 따로 기록해 둔다. (waiting_count는 이 두 값의 합으로 그대로 유지한다)
    #   1) own_class_ahead_count  : 같은 반에서, 나보다 번호가 작고, 아직 안 먹은(결석 아닌) 학생 수
    #   2) other_class_ahead_count: 이번 달 배식 순서상 나보다 먼저 먹는, 반들에 아직 남아있는(결석 아닌) 학생 수의 합
    # 두 값을 나눠서 저장해 두면 나중에 "왜 대기인원이 이렇게 계산됐는지"를 따로 확인할 수 있다.
    own_class_ahead_count = models.IntegerField(default=0)
    other_class_ahead_count = models.IntegerField(default=0)

    # 새치기 감지 > 지금 학생증을 찍어서 이 기록을 만든 학생의 번호를 함께 저장해 둔다. WaitLog는 반 단위로만 저장되어 있어서, 이 값이 없으면 새치기 기록을 봐도 누가 새치기를 했는지 알 수 없기 때문이다.
    scanned_student_number = models.IntegerField(null=True, blank=True)

    # [새치기 감지]
    # 번호 순서대로 밥을 먹어야 하는데, 나보다 번호가 작으면서 아직 안 먹은 (결석도 아닌) 학생이 남아있는 상태에서 내가 먼저 학생증을 찍었다면 "새치기"로 본다.
    #   is_line_cut: 새치기 여부
    #   skipped_student_numbers: 새치기당한(순서가 밀린) 학생 번호들을  "1,2,5" 처럼 쉼표로 이어서 기록해 둔다.
    is_line_cut = models.BooleanField(default=False)
    skipped_student_numbers = models.CharField(max_length=200, blank=True, default='')

    is_congested = models.BooleanField(default=False)

    class Meta:
        ordering = ['-scanned_at']

    def __str__(self):
        return f"{self.cls.name} | {self.scanned_at:%H:%M:%S} | 대기 {self.waiting_count}명"


#  Announcement
class Announcement(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()

    # 어떤 관리자가 이 공지를 썼는지 기록해 둔다.
    # 그 관리자 계정이 삭제되더라도 공지 자체는 남아 있어야 하므로, on_delete=models.SET_NULL(관리자가 사라지면)로 설정한다.
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    # 1) 혼잡한 상황 => 다음반 담임에게 공지 자동 등록
    target_class = models.ForeignKey(
        'Class', on_delete=models.CASCADE, null=True, blank=True, related_name='announcements'
    )
    is_auto = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']   # 가장 최근에 쓴 공지가 맨 위에 오도록 정렬한다.

    def __str__(self):
        return f"{self.title} ({self.created_at:%Y-%m-%d %H:%M})"
