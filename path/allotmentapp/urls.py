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
    path('edit_preferences/', views.edit_preferences, name='edit_preferences'),

    path('logout/',views.student_logout, name='logout'),
    path('logout/',views.admin_logout, name='admin_logout'),
    path('view_courses/', views.view_courses, name='view_courses'),
    path('add_course/', views.add_course, name='add_course'),
    path('edite_courses/', views.edit_courses, name='edit_courses'), 
    path('edit_course/<int:course_id>/', views.edit_course, name='edit_course'),
    path('delete_course/<int:course_id>/', views.delete_course, name='delete_course'),
    path('manage_courses/', views.manage_courses, name='manage_courses'),
    path('manage_batches/', views.manage_batches, name='manage_batches'),
    path('edit_batches/', views.edit_batches, name='edit_batches'),
    path('view_batches/', views.view_batches, name='view_batches'),
    path('create_batch/', views.create_batch, name='create_batch'),
    path('edit_batch/<int:batch_id>/', views.edit_batch, name='edit_batch'),
    path('delete_batch/<int:batch_id>/', views.delete_batch, name='delete_batch'),
     path('manage_allotment/', views.manage_allotment, name='manage_allotment'),
    path('first_sem_allotment/', views.first_sem_allotment, name='first_sem_allotment'),
    path('second_sem_allotment/', views.second_sem_allotment, name='second_sem_allotment'),
    path('view_first_sem_allotments/', views.view_first_sem_allotments, name='view_first_sem_allotments'),
    path('view_second_sem_allotments/', views.view_second_sem_allotments, name='view_second_sem_allotments'),

    path('view-allotment/', views.view_student_allotment, name='view_student_allotment'),


]
