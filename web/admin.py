from django.contrib import admin
from .models import Student, Class, MealStatus, WaitLog, UserProfile, Announcement, ClassMealOrder

admin.site.register(Student)
admin.site.register(Class)
admin.site.register(MealStatus)
admin.site.register(WaitLog)          # Django 관리자 화면에서도 기록을 볼 수 있게 등록
admin.site.register(UserProfile)      # 계정 종류(관리자/학생)를 관리자 화면에서 바꿀 수 있게 등록
admin.site.register(Announcement)     # 공지사항도 Django 관리자 화면에서 관리할 수 있게 등록
admin.site.register(ClassMealOrder)   # [월별 홀수반/짝수반 배식 순서도 관리자 화면에서 볼 수 있게 등록
