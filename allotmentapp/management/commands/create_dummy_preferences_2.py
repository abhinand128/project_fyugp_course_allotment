from django.core.management.base import BaseCommand
from allotmentapp.models import Student, CoursePreference, Batch, Department
import random

class Command(BaseCommand):
    help = 'Create dummy course preferences for semester 2 testing allocation'

    def handle(self, *args, **options):
        students = Student.objects.filter(current_sem=2)
        
        for student in students:
            if CoursePreference.objects.filter(student=student).exists():
                self.stdout.write(f"Skipping {student.name} - already has preferences")
                continue
            
            # Get all available batches for semester 2
            all_batches = Batch.objects.filter(
                course__semester=2
            ).select_related('course', 'course__department')
            
            # Filter batches based on pathway rules
            if student.pathway.name == "Single Major":
                dsc_1_batches = all_batches.filter(
                    course__department=student.department,
                    course__course_type__name__startswith='DSC'
                )
                other_batches = all_batches.exclude(
                    course__department=student.department
                )
                dsc_2_batches = other_batches.filter(
                    course__course_type__name__startswith='DSC'
                )
                dsc_3_batches = other_batches.filter(
                    course__course_type__name__startswith='DSC'
                )
                mdc_batches = other_batches.filter(
                    course__course_type__name__startswith='MDC'
                )
                
            elif student.pathway.name == "Double Major":
                # Simulate having chosen a second department in semester 1
                # We'll randomly select a department that's not the student's primary
                second_dept = Department.objects.exclude(id=student.department.id).order_by('?').first()
                
                dsc_1_batches = all_batches.filter(
                    course__department=second_dept,
                    course__course_type__name__startswith='DSC'
                )
                dsc_2_batches = all_batches.filter(
                    course__department=second_dept,
                    course__course_type__name__startswith='DSC'
                )
                dsc_3_batches = all_batches.filter(
                    course__department=student.department,
                    course__course_type__name__startswith='DSC'
                )
                mdc_batches = all_batches.exclude(
                    course__department__in=[student.department, second_dept]
                ).filter(
                    course__course_type__name__startswith='MDC'
                )
                
            elif "Minor" in student.pathway.name:
                # For minor pathway, similar to Single Major but with different MDC rules
                dsc_1_batches = all_batches.filter(
                    course__department=student.department,
                    course__course_type__name__startswith='DSC'
                )
                other_batches = all_batches.exclude(
                    course__department=student.department
                )
                dsc_2_batches = other_batches.filter(
                    course__course_type__name__startswith='DSC'
                )
                dsc_3_batches = other_batches.filter(
                    course__course_type__name__startswith='DSC'
                )
                mdc_batches = other_batches.filter(
                    course__course_type__name__startswith='MDC'
                )
            
            else:
                self.stdout.write(f"Unknown pathway for {student.name}")
                continue
            
            preferences = []
            
            # Paper 1 - DSC 1 (single selection)
            if dsc_1_batches.exists():
                dsc1_batch = random.choice(list(dsc_1_batches))
                preferences.append(CoursePreference(
                    student=student,
                    batch=dsc1_batch,
                    preference_number=1,
                    paper_no=1
                ))
            
            # Paper 2 - DSC 2 (three different preferences or all available for Double Major)
            dsc2_batch_list = list(dsc_2_batches)
            random.shuffle(dsc2_batch_list)
            
            # For Double Major, add all available DSC 2 options from the relevant department
            # For other pathways, limit to 3 preferences
            option_count = len(dsc2_batch_list) if student.pathway.name == "Double Major" else min(3, len(dsc2_batch_list))
            
            for pref_num, batch in enumerate(dsc2_batch_list[:option_count], start=1):
                preferences.append(CoursePreference(
                    student=student,
                    batch=batch,
                    preference_number=pref_num,
                    paper_no=2
                ))
            
            # Paper 3 - DSC 3 (three different preferences or all available for Double Major)
            dsc3_batch_list = list(dsc_3_batches)
            random.shuffle(dsc3_batch_list)
            
            # For Double Major, add all available DSC 3 options from the relevant department
            # For other pathways, limit to 3 preferences
            option_count = len(dsc3_batch_list) if student.pathway.name == "Double Major" else min(3, len(dsc3_batch_list))
            
            for pref_num, batch in enumerate(dsc3_batch_list[:option_count], start=1):
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
                self.stdout.write(f"No suitable batches available for {student.name}")

        self.stdout.write("Finished creating dummy preferences for semester 2")