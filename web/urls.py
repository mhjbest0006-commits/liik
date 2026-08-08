from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('login-api/', views.LoginView.as_view(), name='login_api'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),  
    path('regist/', views.regist, name='regist'),

    path('classrooms/set/', views.set_classrooms, name='set_classrooms'),
    path('classrooms/', views.get_classrooms, name='get_classrooms'),

    path('students/add/', views.add_student, name='add_student'),
    path('students/', views.get_students, name='get_students'),
    path('students/absence/', views.set_student_absence, name='set_student_absence'), 

    path('classrooms/meal-order/', views.get_class_meal_order, name='get_class_meal_order'),
    path('classrooms/meal-order/set/', views.set_class_meal_order, name='set_class_meal_order'),

    path('scan/', views.scan_barcode, name='scan_barcode'),
    path('api/scan-barcode/', views.scan_barcode, name='scan_barcode_api'),
    path('scan-page/', views.scan_page, name='scan_page'),
    path('mark-absent/', views.mark_absent, name='mark_absent'),

    path('status/', views.meal_dashboard, name='status'),
    path('status/reset-daily/', views.reset_daily_meal_status, name='reset_daily_meal_status'), 
    path('status/reset-wait-logs/', views.reset_wait_logs, name='reset_wait_logs'),
    path('api/line-cut-logs/', views.line_cut_logs, name='line_cut_logs'), 
    path('status-page/', views.status_page, name='status_page'), 
    path('announce/', views.announce, name='announce'), 
    path('congestion/', views.congestion_page, name='congestion_page'), 

    path('api/announcements/', views.list_announcements, name='list_announcements'),
    path('api/announcements/create/', views.create_announcement, name='create_announcement'),
    path('api/announcements/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),

    path('api/congestion-probability/', views.congestion_probability, name='congestion_probability'),
    path('api/time-statistics/', views.time_statistics, name='time_statistics'),
    path('api/linear-wait-model/', views.linear_wait_model, name='linear_wait_model'),
]
