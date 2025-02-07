from django.urls import path
from allotmentapp import views

urlpatterns = [
    path("admin-login/", views.admin_login, name="admin_login"),
    path("student-login/",views.student_login, name="student_login"),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('add-student/', views.add_student, name='add_student'),


]
