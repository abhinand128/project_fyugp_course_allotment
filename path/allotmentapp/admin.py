from django.contrib import admin
from .models import Student, Department, Pathway, Course,Batch,CoursePreference,Course_type,CourseAllotment

# Register each model
admin.site.register(Student)
admin.site.register(Department)
admin.site.register(Pathway)
admin.site.register(Course)
admin.site.register(Batch)
admin.site.register(CoursePreference)
admin.site.register(Course_type)
admin.site.register(CourseAllotment)