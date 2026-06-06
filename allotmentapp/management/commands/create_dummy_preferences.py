from django.core.management.base import BaseCommand
from allotmentapp.models import Student, CoursePreference, Batch, Department, Pathway
import random

class Command(BaseCommand):
    help = 'Create dummy course preferences for testing allocation'

    def handle(self, *args, **options):
        students = Student.objects.all()
        
        for student in students:
            if CoursePreference.objects.filter(student=student).exists():
                self.stdout.write(f"Skipping {student.name} - already has preferences")
                continue
            
            # Get all available batches for the current semester
            all_batches = Batch.objects.filter(
                course__semester=student.current_sem
            ).select_related('course', 'course__department')
            
            # Filter batches based on pathway rules
            if student.pathway.name == "Single Major":
                dsc1_batches = all_batches.filter(
                    course__department=student.department,
                    course__course_type__name__startswith='DSC'
                )
                other_batches = all_batches.exclude(
                    course__department=student.department
                )
                dsc2_batches = other_batches.filter(
                    course__course_type__name__startswith='DSC'
                )
                mdc_batches = other_batches.filter(
                    course__course_type__name__startswith='MDC'
                )
                
            elif student.pathway.name == "Double Major":
                other_dept = Department.objects.exclude(id=student.department.id).order_by('?').first()
                
                dsc1_batches = all_batches.filter(
                    course__department=student.department,
                    course__course_type__name__startswith='DSC'
                )
                dsc2_batches = all_batches.filter(
                    course__department=other_dept,
                    course__course_type__name__startswith='DSC'
                )
                mdc_batches = all_batches.exclude(
                    course__department__in=[student.department, other_dept]
                ).filter(
                    course__course_type__name__startswith='MDC'
                )
                
            elif "Minor" in student.pathway.name:
                dsc1_batches = all_batches.filter(
                    course__department=student.department,
                    course__course_type__name__startswith='DSC'
                )
                dsc2_batches = all_batches.exclude(
                    course__department=student.department
                ).filter(
                    course__course_type__name__startswith='DSC'
                )
                mdc_batches = all_batches.exclude(
                    course__department=student.department
                ).filter(
                    course__course_type__name__startswith='MDC'
                )
            
            else:
                self.stdout.write(f"Unknown pathway for {student.name}")
                continue
            
            preferences = []
            
            # Paper 1 - DSC 1 (single selection)
            if dsc1_batches.exists():
                dsc1_batch = random.choice(list(dsc1_batches))
                preferences.append(CoursePreference(
                    student=student,
                    batch=dsc1_batch,
                    preference_number=1,
                    paper_no=1
                ))
            
            # Paper 2 - DSC 2 (three different preferences)
            dsc2_batch_list = list(dsc2_batches)
            random.shuffle(dsc2_batch_list)
            for pref_num, batch in enumerate(dsc2_batch_list[:3], start=1):
                preferences.append(CoursePreference(
                    student=student,
                    batch=batch,
                    preference_number=pref_num,
                    paper_no=2
                ))
            
            # Paper 3 - DSC 3 (three different preferences)
            dsc3_batch_list = list(dsc2_batches)
            random.shuffle(dsc3_batch_list)
            for pref_num, batch in enumerate(dsc3_batch_list[:3], start=1):
                preferences.append(CoursePreference(
                    student=student,
                    batch=batch,
                    preference_number=pref_num,
                    paper_no=3
                ))
            
            # Paper 4 - MDC (ALL available papers as preferences)
            mdc_batch_list = list(mdc_batches)
            random.shuffle(mdc_batch_list)
            for pref_num, batch in enumerate(mdc_batch_list, start=1):
                preferences.append(CoursePreference(
                    student=student,
                    batch=batch,
                    preference_number=pref_num,
                    paper_no=4
                ))
            
            # Save all preferences
            if preferences:
                CoursePreference.objects.bulk_create(preferences)
                self.stdout.write(f"Created preferences for {student.name}")
                for p in preferences:
                    self.stdout.write(f"  - Paper {p.paper_no}: {p.batch.course.course_name} (Pref {p.preference_number})")
            else:
                self.stdout.write(f"No batches available for {student.name}")

        self.stdout.write("Finished creating dummy preferences")
