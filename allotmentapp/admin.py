from django.contrib import admin
from .models import Student, Department, Pathway, Course,Batch,CoursePreference,Course_type,CourseAllotment
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from django.contrib import admin
from .models import Student

class StudentResource(resources.ModelResource):
    department = fields.Field(
        column_name='Department',
        attribute='department__name'
    )
    pathway = fields.Field(
        column_name='Pathway',
        attribute='pathway__name'
    )
    status = fields.Field(
        column_name='Status'
    )

    class Meta:
        model = Student
        fields = (
            'admission_number',
            'name',
            'dob',
            'email',
            'phone_number',
            'department',
            'admission_category',
            'admission_year',
            'pathway',
            'current_sem',
            'normalized_marks',
            'first_sem_marks',
            'status',
        )

    def dehydrate_status(self, student):
        return "Active" if student.status == 1 else "Inactive"


@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
    resource_class = StudentResource

# Register each model

admin.site.register(Department)
admin.site.register(Pathway)
admin.site.register(Course)
admin.site.register(Batch)
admin.site.register(CoursePreference)
admin.site.register(Course_type)
admin.site.register(CourseAllotment)
