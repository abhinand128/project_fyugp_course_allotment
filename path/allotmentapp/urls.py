from django.urls import path
from allotmentapp import views

urlpatterns = [
    path("admin-login/", views.admin_login, name="admin_login"),
    path("student-login/",views.student_login, name="student_login"),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('add-student/', views.add_student, name='add_student'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path("view_courses_std/", views.view_courses_student, name="view_courses_student"),
    path('course_selection/',views.course_selection, name='course_selection'),
    path('view_preferences/', views.view_preferences, name='view_preferences'),
    path('logout/',views.student_logout, name='logout'),


]
