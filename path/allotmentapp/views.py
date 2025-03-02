from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max, Count
import csv
from datetime import datetime
from .models import (
    Student, Course, CoursePreference, Batch, CourseAllotment, 
    Department, Pathway, HOD
)
from .forms import (
    StudentForm, CourseFilterForm, CourseSelectionFormSem1, CourseSelectionFormSem2, 
    CourseForm, BatchForm, BatchFilterForm, BulkStudentUploadForm, 
    StudentRegistrationForm, StudentEditForm, HODEditForm, HODForm,StudentAllotmentFilterForm
)



def Admin_group_required(user):
    """Check if the user belongs to the 'Admin' group."""
    return user.groups.filter(name='Admin').exists()

def student_group_required(user):
    """Check if the user belongs to the 'Admin' group."""
    return user.groups.filter(name='Student').exists()

def hod_group_required(user):
    """Check if the user belongs to the 'Admin' group."""
    return user.groups.filter(name='hod').exists()

def allocate_courses(semester):
    with transaction.atomic():
        # 1. Allocate Paper 1 (DSC 1) - Ensuring at least one core course is assigned
        for student in Student.objects.filter(current_sem=semester):
            allocated = False
            preferences = CoursePreference.objects.filter(student=student, paper_no=1).order_by('preference_number')

            for preference in preferences:
                batch = preference.batch
                if batch.status and batch.course.seat_limit > CourseAllotment.objects.filter(batch=batch).count():
                    CourseAllotment.objects.create(student=student, batch=batch, paper_no=1)
                    allocated = True
                    break

            if not allocated:
                print(f"Warning: Student {student.admission_number} (Sem {semester}) could not be allocated Paper 1. All preferences full.")

        # 2. Allocate Papers 2 & 3 based on marks
        # Sorting conditionally based on semester
        if semester == 2:
            students = Student.objects.filter(current_sem=semester).order_by(F('first_sem_marks').desc(nulls_last=True))
        else:
            students = Student.objects.filter(current_sem=semester).order_by('-normalized_marks')

        for paper_no in range(2, 4):
            for student in students:
                allocated = False
                allotted_batches = CourseAllotment.objects.filter(student=student).values_list('batch', flat=True)
                preferences = CoursePreference.objects.filter(student=student, paper_no=paper_no).exclude(batch__in=allotted_batches).order_by('preference_number')

                for preference in preferences:
                    batch = preference.batch
                    if batch.status and batch.course.seat_limit > CourseAllotment.objects.filter(batch=batch).count():
                        CourseAllotment.objects.create(student=student, batch=batch, paper_no=paper_no)
                        allocated = True
                        break

                if not allocated:
                    print(f"Warning: Student {student.admission_number} (Sem {semester}) could not be allocated Paper {paper_no}. All preferences full.")

        # 3. Allocate Paper 4 (MDC) with Department & Category Quota
        department_strengths = {
            "Economics": 48, "History": 48, "Malayalam": 36, "Commerce": 55, "Physics": 43,
            "Chemistry": 29, "Zoology": 29, "Botany": 29, "Statistics": 29
        }
        department_quota = {dept: max(1, round(strength * 0.2)) for dept, strength in department_strengths.items()}

        all_general_students = list(Student.objects.filter(current_sem=semester, admission_category="General").order_by(
            F('first_sem_marks').desc(nulls_last=True) if semester == 2 else '-normalized_marks'
        ))

        for department, total_dept_quota in department_quota.items():
            general_quota = max(1, round(total_dept_quota * 0.6))
            sc_st_quota = max(1, round(total_dept_quota * 0.2))
            other_quota = max(1, round(total_dept_quota * 0.2))

            general_students = list(Student.objects.filter(
                current_sem=semester, department__name=department, admission_category="General"
            ).order_by(F('first_sem_marks').desc(nulls_last=True) if semester == 2 else '-normalized_marks')[:general_quota])

            sc_st_students = list(Student.objects.filter(
                current_sem=semester, department__name=department, admission_category__in=["SC", "ST"]
            ).order_by(F('first_sem_marks').desc(nulls_last=True) if semester == 2 else '-normalized_marks')[:sc_st_quota])

            other_students = list(Student.objects.filter(
                current_sem=semester, department__name=department, admission_category__in=["EWS", "Sports", "Management"]
            ).order_by(F('first_sem_marks').desc(nulls_last=True) if semester == 2 else '-normalized_marks')[:other_quota])

            available_general_in_department = list(Student.objects.filter(
                current_sem=semester, department__name=department, admission_category="General"
            ).order_by(F('first_sem_marks').desc(nulls_last=True) if semester == 2 else '-normalized_marks'))

            while len(sc_st_students) < sc_st_quota and available_general_in_department:
                sc_st_students.append(available_general_in_department.pop(0))

            while len(other_students) < other_quota and available_general_in_department:
                other_students.append(available_general_in_department.pop(0))

            while len(sc_st_students) < sc_st_quota and all_general_students:
                sc_st_students.append(all_general_students.pop(0))

            while len(other_students) < other_quota and all_general_students:
                other_students.append(all_general_students.pop(0))

            while len(general_students) < general_quota and all_general_students:
                general_students.append(all_general_students.pop(0))

            selected_students = general_students + sc_st_students + other_students

            # Allocate courses for Paper 4
            for student in selected_students:
                allocated = False
                allotted_batches = CourseAllotment.objects.filter(student=student).values_list('batch', flat=True)
                preferences = CoursePreference.objects.filter(student=student, paper_no=4).exclude(batch__in=allotted_batches).order_by('preference_number')

                for preference in preferences:
                    batch = preference.batch
                    if batch.status and batch.course.seat_limit > CourseAllotment.objects.filter(batch=batch).count():
                        CourseAllotment.objects.create(student=student, batch=batch, paper_no=4)
                        allocated = True
                        break

                if not allocated:
                    print(f"Warning: Student {student.admission_number} (Sem {semester}) could not be allocated Paper 4. All preferences full.")



    
def index(request):
    return render(request, 'registration/login.html')

def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        
        if user is not None:  # Ensure only superusers can log in
            login(request, user)
            return redirect("admin_dashboard")  # Redirect to admin dashboard
        else:
            messages.error(request, "Invalid credentials or not an admin.")

    return render(request, "login/admin_login.html")  # Render custom admin login page

def admin_logout(request):
    logout(request)
    return redirect('home')  # Redirect to the login page after logout

@login_required
@user_passes_test(Admin_group_required)
def manage_allotment(request):
    """Render the manage courses page."""
    return render(request, 'admin/manage_allocation.html', {'page_name': 'manage allocation'})

# Student Login View
def student_login(request):
    if request.method == 'POST':
        admission_number = request.POST.get('admission_number')
        password = request.POST.get('password')

        user = authenticate(request, username=admission_number, password=password)

        if user is not None:  # Authentication successful
            login(request, user)
            return redirect('student_dashboard')  # Redirect to student dashboard
        else:
            messages.error(request, 'Invalid admission number or password.')

    return render(request, 'login/student_login.html')

@login_required
@user_passes_test(Admin_group_required)
def admin_dashboard(request):
    return render(request, 'admin/dashboard.html', {'page_name': 'Dashboard'})

@login_required
@user_passes_test(student_group_required)
def student_dashboard(request):
    # You can pass additional context like page_name if needed
    return render(request, 'student/student_dashboard.html', {'page_name': 'Dashboard'})

def student_logout(request):
    logout(request)
    return redirect('home')  # Redirect to the login page after logout

@login_required
@user_passes_test(student_group_required) 
def view_courses_student(request):
    """Display a list of courses with optional filters."""
    form = CourseFilterForm(request.GET)  # Initialize the filter form
    courses = Course.objects.all()

    # Apply filters if the form is valid
    if form.is_valid():
        course_type = form.cleaned_data.get('course_type')
        department = form.cleaned_data.get('department')
        semester = form.cleaned_data.get('semester')

        if course_type:
            courses = courses.filter(course_type=course_type)
        if department:
            courses = courses.filter(department=department)
        if semester:
            courses = courses.filter(semester=semester)

    context = {
        'courses': courses,
        'form': form,
        'page_name': 'Courses',  # Passed dynamically
    }
    return render(request, 'student/view_courses_students.html', context)




@login_required
@user_passes_test(student_group_required) 
def course_selection(request):
    try:
        student = Student.objects.select_related('pathway', 'department').get(user=request.user)
    except Student.DoesNotExist:
        return render(request, 'error.html', {'message': 'Student not found'})

    # Check if preferences or allotment already exist
    existing_preferences = CoursePreference.objects.filter(student=student).exists()
    already_allocated = CourseAllotment.objects.filter(student=student, batch__course__semester=student.current_sem).exists()

    print(already_allocated)

    if existing_preferences or already_allocated:
        return render(request, 'student/course_selection.html', {
            'view_preferences': True,
            'already_submitted': True,
            'already_allocated': already_allocated,
            'student': student
        })

    # Determine the correct form based on the semester
    if student.current_sem == 1:
        FormClass = CourseSelectionFormSem1
    elif student.current_sem == 2:
        FormClass = CourseSelectionFormSem2
    else:
        return render(request, 'error.html', {'message': 'Invalid semester'})

    if request.method == 'POST':
        form = FormClass(request.POST, student=student)
        if form.is_valid():
            preferences = []

            # Process form data (same logic as before)
            for field_name, batch in form.cleaned_data.items():
                preference_number = int(field_name.split("_")[-1]) if "option" in field_name else 1
                paper_no = 1 if "dsc_1" in field_name else 2 if "dsc_2" in field_name else 3 if "dsc_3" in field_name else 4

                preferences.append(CoursePreference(
                    student=student,
                    batch=batch,
                    preference_number=preference_number,
                    paper_no=paper_no
                ))

            CoursePreference.objects.bulk_create(preferences)
            return redirect('view_preferences')

    else:
        form = FormClass(student=student)

    return render(request, 'student/course_selection.html', {
        'form': form,
        'already_submitted': False,
        'student': student
    })

@login_required
@user_passes_test(student_group_required) 
def view_preferences(request):
    student = request.user.student  # Get the logged-in student

    # Fetch selected preferences and order by preference number
    preferences = CoursePreference.objects.filter(student=student, batch__course__semester=student.current_sem).order_by('preference_number')

    # Organizing preferences using paper_no
    categorized_preferences = {
        1: {},  # DSC1 → DSC4
        2: {},  # DSC2 → DSC5
        3: {},  # DSC3 → DSC6
        4: {}   # MDC
    }

    for pref in preferences:
        paper_no = pref.paper_no  # Use the new field
        preference_key = f"option_{pref.preference_number}"  # Ensure uniqueness
        categorized_preferences[paper_no][preference_key] = pref

    return render(request, 'student/view_preferences.html', {
        'categorized_preferences': categorized_preferences,
        'student': student  # Pass student object to template
    })

@login_required
@user_passes_test(student_group_required)  
def edit_preferences(request):
    try:
        student = Student.objects.select_related('pathway', 'department').get(user=request.user)
    except Student.DoesNotExist:
        return render(request, 'error.html', {'message': 'Student not found'})

    # Fetch existing preferences for the student's current semester
    existing_preferences = CoursePreference.objects.filter(
        student=student, 
        batch__course__semester=student.current_sem
    ).order_by('paper_no', 'preference_number')

    if not existing_preferences.exists():
        return redirect('course_selection')  # Redirect if no preferences exist for the current semester

    # Determine the correct form based on the semester
    FormClass = CourseSelectionFormSem1 if student.current_sem == 1 else CourseSelectionFormSem2

    if request.method == 'POST':
        form = FormClass(request.POST, student=student)
        if form.is_valid():
            # Clear old preferences for the current semester
            CoursePreference.objects.filter(
                student=student, 
                batch__course__semester=student.current_sem
            ).delete()

            # Save new preferences
            preferences = []
            for field_name, batch in form.cleaned_data.items():
                preference_number = int(field_name.split("_")[-1]) if "option" in field_name else 1

                # Keep original paper number mapping
                paper_no = (
                    1 if "dsc_1" in field_name else
                    2 if "dsc_2" in field_name else
                    3 if "dsc_3" in field_name else
                    4 if "mdc" in field_name else None
                )

                if paper_no:
                    preferences.append(CoursePreference(
                        student=student,
                        batch=batch,
                        preference_number=preference_number,
                        paper_no=paper_no
                    ))

            CoursePreference.objects.bulk_create(preferences)

            return redirect('view_preferences')

    else:
        # Pre-fill form with existing selections
        initial_data = {}
        for pref in existing_preferences:
            field_name = (
                "dsc_1" if pref.paper_no == 1 else
                f"dsc_2_option_{pref.preference_number}" if pref.paper_no == 2 else
                f"dsc_3_option_{pref.preference_number}" if pref.paper_no == 3 else
                f"mdc_option_{pref.preference_number}" if pref.paper_no == 4 else None
            )

            if field_name:
                initial_data[field_name] = pref.batch

        form = FormClass(student=student, initial=initial_data)

    return render(request, 'student/edit_preferences.html', {
        'form': form,
        'student': student
    })


@login_required
@user_passes_test(Admin_group_required)
def manage_courses(request):
    """Display a list of courses with optional filters."""
    form = CourseFilterForm(request.GET)  # Initialize the filter form
    courses = Course.objects.all()

    # Apply filters if the form is valid
    if form.is_valid():
        course_type = form.cleaned_data.get('course_type')
        department = form.cleaned_data.get('department')
        semester = form.cleaned_data.get('semester')

        if course_type:
            courses = courses.filter(course_type=course_type)
        if department:
            courses = courses.filter(department=department)
        if semester:
            courses = courses.filter(semester=semester)

    context = {
        'courses': courses,
        'form': form,
        'page_name': 'Courses',  # Passed dynamically
    }
    return render(request, 'admin/manage_courses.html', context)

@login_required
@user_passes_test(Admin_group_required)
def add_course(request):
    """Add a new course."""
    if request.method == 'POST':
        form = CourseForm(request.POST)  # Handle form submission
        if form.is_valid():
            form.save()
            messages.success(request, "Course created successfully!")
            return redirect('manage_courses')
        # Redirect to the courses page
    else:
        form = CourseForm()  # Create an empty form for GET request

    return render(request, 'admin/add_course.html', {'form': form, 'page_name': 'Add Course'})

@login_required
@user_passes_test(Admin_group_required)
def edit_course(request, course_id):
    """Edit an existing course."""
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Course updated successfully!")
            return redirect('manage_courses')  # Redirect to the courses page
    else:
        form = CourseForm(instance=course)  # Populate form with course data

    context = {
        'form': form,
        'course': course,
        'page_name': 'Edit Course',  # Passed dynamically
    }
    return render(request, 'admin/edit_course.html', context)

@login_required
@user_passes_test(Admin_group_required)
def delete_course(request, course_id):
    """Delete a course."""
    course = get_object_or_404(Course, id=course_id)
    course.delete()
    messages.success(request, "Course deleted successfully!")# Delete the course
    return redirect('manage_courses')  # Redirect to the courses page

@login_required
@user_passes_test(Admin_group_required)
def create_batch(request):
    courses = Course.objects.all()  # Default to all courses
    filter_form = CourseFilterForm(request.GET or None)

    if filter_form.is_valid():
        course_type = filter_form.cleaned_data.get('course_type')
        department = filter_form.cleaned_data.get('department')
        semester = filter_form.cleaned_data.get('semester')

        if course_type:
            courses = courses.filter(course_type=course_type)
        if department:
            courses = courses.filter(department=department)
        if semester:
            courses = courses.filter(semester=semester)

    if request.method == 'POST':
        form = BatchForm(request.POST)
        selected_courses = request.POST.getlist('selected_courses')  # Get selected courses

        if not selected_courses:
            messages.error(request, "Please select at least one course.")
        elif form.is_valid():
            year = form.cleaned_data['year']
            part = form.cleaned_data['part']
            duplicate_found = False

            for course_id in selected_courses:
                course = Course.objects.get(id=course_id)
                batch, created = Batch.objects.get_or_create(course=course, year=year, part=part)

                if not created:
                    duplicate_found = True  # Track if a duplicate batch exists

            if duplicate_found:
                messages.error(request, "Some batches already exist!")
                return redirect('create_batch')
            messages.success(request, "Batch created successfully!")
            return redirect('manage_batches')
        
            

    else:
        form = BatchForm()

    return render(request, 'admin/create_batch.html', {
        'form': form,
        'filter_form': filter_form,
        'courses': courses
    })







@login_required
@user_passes_test(Admin_group_required)
def edit_batch(request, batch_id):
    """Edit a single batch status."""
    batch = get_object_or_404(Batch, id=batch_id)
    course = batch.course  # Get the related course

    if request.method == 'POST':
        status_value = request.POST.get('status')  # Get status from form
        batch.status = status_value == "True"  # Convert string to boolean
        batch.save()
        messages.success(request, "Batch status updated successfully!")
        return redirect('edit_batches')  # Redirect to batch list after update

    return render(request, 'admin/edit_batch.html', {
        'batch': batch,
        'course': course
    })
    
@login_required
@user_passes_test(Admin_group_required)
def manage_batches(request):
    """View, filter, bulk update, and bulk delete batches."""
    
    if request.method == "POST":
        batch_ids = request.POST.getlist("batch_ids")  # Get selected batch IDs
        action = request.POST.get("action")  # Get which action was triggered

        if not batch_ids:
            messages.warning(request, "No batches selected for action.")
            return redirect("manage_batches")

        if action == "update":
            bulk_status = request.POST.get("bulk_status")

            if bulk_status not in ["True", "False"]:
                messages.error(request, "Invalid status selected.")
                return redirect("manage_batches")

            # Convert status from string to boolean
            status_value = bulk_status == "True"

            # Bulk update selected batches
            Batch.objects.filter(id__in=batch_ids).update(status=status_value)

            messages.success(request, "Selected batches updated successfully.")

        elif action == "delete":
            # Bulk delete selected batches
            Batch.objects.filter(id__in=batch_ids).delete()
            messages.success(request, "Selected batches deleted successfully.")

        return redirect("manage_batches")

    # Filtering logic
    form = BatchFilterForm(request.GET)
    batches = Batch.objects.all()

    if form.is_valid():
        year = form.cleaned_data.get("year")
        part = form.cleaned_data.get("part")

        if year:
            batches = batches.filter(year=year)
        if part:
            batches = batches.filter(part=part)

    # Extract unique years from DB for dropdown
    existing_years = Batch.objects.values_list("year", flat=True).distinct()

    return render(
        request, 
        "admin/manage_batches.html", 
        {
            "batches": batches,
            "form": form,
            "existing_years": existing_years,  # Only show years available in DB
        }
    )

@login_required
@user_passes_test(Admin_group_required)
def delete_batch(request, batch_id):
    """Delete a batch."""
    batch = get_object_or_404(Batch, id=batch_id)
    batch.delete()
    return redirect('admin/manage_batches')  # Redirect to the batches page after deletion


def get_current_academic_year():
    current_year = datetime.now().year
    next_year = current_year + 1
    return f"{current_year}-{next_year}"

@login_required
@user_passes_test(Admin_group_required)
def first_sem_allotment(request):

    current_academic_year = get_current_academic_year()

    if CourseAllotment.objects.filter(batch__course__semester=1, batch__year=current_academic_year).exists():
        messages.warning(request, "Courses are already allocated for the first semester in the current academic year!")
        return render(request, 'admin/first_sem_allotment.html', {'already_allocated': True})

    # Get all first semester students
    students = Student.objects.filter(
        current_sem=1
    ).prefetch_related(
        'coursepreference_set',
        'coursepreference_set__batch',
        'coursepreference_set__batch__course'
    ).order_by('admission_number')

    # Get unique paper numbers and their maximum preferences
    paper_preferences = CoursePreference.objects.filter(
        student__current_sem=1
    ).values('paper_no', 'preference_number').distinct().order_by('paper_no', 'preference_number')

    # Create a structure of paper-preference combinations
    paper_options = {}
    for pref in paper_preferences:
        paper_no = pref['paper_no']
        pref_no = pref['preference_number']
        if paper_no not in paper_options:
            paper_options[paper_no] = []
        paper_options[paper_no].append(pref_no)

    if request.method == 'POST':
        try:
            allocate_courses(semester=1)
            messages.success(request, "First semester course allotment completed successfully! Redirecting to view allotments...")
            CoursePreference.objects.filter(student__current_sem=1).delete()
            return redirect('view_first_sem_allotments')
        except Exception as e:
            messages.error(request, f"An error occurred during allotment: {e}")

    context = {
        'page_name': 'First Semester Allotment',
        'students': students,
        'paper_options': paper_options,
    }
    
    return render(request, 'admin/first_sem_allotment.html', context)

@login_required
@user_passes_test(Admin_group_required)
def download_preferences_csv_first_sem(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="first_sem_preferences.csv"'
    writer = csv.writer(response)
    
    # Get all paper-preference combinations
    paper_preferences = CoursePreference.objects.filter(
        student__current_sem=1
    ).values('paper_no', 'preference_number').distinct().order_by('paper_no', 'preference_number')
    
    # Create headers
    headers = [
        'Admission Number',
        'Student Name',
        'Department',
        'Pathway'
        'Category',
        'Normalized Marks'
    ]
    
    # Add dynamic headers for each paper-preference combination
    for pref in paper_preferences:
        headers.append(f'Paper {pref["paper_no"]} Option {pref["preference_number"]}')
    
    writer.writerow(headers)
    
    students = Student.objects.filter(
        current_sem=1
    ).prefetch_related(
        'coursepreference_set',
        'coursepreference_set__batch',
        'coursepreference_set__batch__course'
    ).order_by('admission_number')
    
    for student in students:
        row = [
            student.admission_number,
            student.name,
            student.department.name,
            student.pathway,
            student.admission_category,
            student.normalized_marks,
        ]
        
        # Add preferences for each paper-preference combination
        for pref in paper_preferences:
            course_pref = student.coursepreference_set.filter(
                paper_no=pref['paper_no'],
                preference_number=pref['preference_number']
            ).first()
            
            if course_pref:
                row.append(course_pref.batch.course.course_name)
            else:
                row.append('-')
        
        writer.writerow(row)
    
    return response

@login_required
@user_passes_test(Admin_group_required)
def second_sem_allotment(request):

    current_academic_year = get_current_academic_year()

    if CourseAllotment.objects.filter(batch__course__semester=2, batch__year=current_academic_year).exists():
        messages.warning(request, "Courses are already allocated for the Second semester in the current academic year!")
        return render(request, 'admin/second_sem_allotment.html', {'already_allocated': True})

    # Get all first semester students
    students = Student.objects.filter(
        current_sem=2
    ).prefetch_related(
        'coursepreference_set',
        'coursepreference_set__batch',
        'coursepreference_set__batch__course'
    ).order_by('admission_number')

    # Get unique paper numbers and their maximum preferences
    paper_preferences = CoursePreference.objects.filter(
        student__current_sem=2
    ).values('paper_no', 'preference_number').distinct().order_by('paper_no', 'preference_number')

    # Create a structure of paper-preference combinations
    paper_options = {}
    for pref in paper_preferences:
        paper_no = pref['paper_no']
        pref_no = pref['preference_number']
        if paper_no not in paper_options:
            paper_options[paper_no] = []
        paper_options[paper_no].append(pref_no)

    if request.method == 'POST':
        try:
            allocate_courses(semester=2)
            messages.success(request, "First semester course allotment completed successfully! Redirecting to view allotments...")
            CoursePreference.objects.filter(student__current_sem=2).delete()
            return redirect('second_sem_allotments')
        except Exception as e:
            messages.error(request, f"An error occurred during allotment: {e}")

    context = {
        'page_name': 'Second Semester Allotment',
        'students': students,
        'paper_options': paper_options,
    }
    
    return render(request, 'admin/second_sem_allotment.html', context)
@login_required
@user_passes_test(Admin_group_required)
def download_preferences_csv_second_sem(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Second_sem_preferences.csv"'
    writer = csv.writer(response)
    
    # Get all paper-preference combinations
    paper_preferences = CoursePreference.objects.filter(
        student__current_sem=2
    ).values('paper_no', 'preference_number').distinct().order_by('paper_no', 'preference_number')
    
    # Create headers
    headers = [
        'Admission Number',
        'Student Name',
        'Department',
        'Pathway'
        'Category',
        'Normalized Marks'
    ]
    
    # Add dynamic headers for each paper-preference combination
    for pref in paper_preferences:
        headers.append(f'Paper {pref["paper_no"]} Option {pref["preference_number"]}')
    
    writer.writerow(headers)
    
    students = Student.objects.filter(
        current_sem=2
    ).prefetch_related(
        'coursepreference_set',
        'coursepreference_set__batch',
        'coursepreference_set__batch__course'
    ).order_by('admission_number')
    
    for student in students:
        row = [
            student.admission_number,
            student.name,
            student.department.name,
            student.pathway,
            student.admission_category,
            student.normalized_marks,
        ]
        
        # Add preferences for each paper-preference combination
        for pref in paper_preferences:
            course_pref = student.coursepreference_set.filter(
                paper_no=pref['paper_no'],
                preference_number=pref['preference_number']
            ).first()
            
            if course_pref:
                row.append(course_pref.batch.course.course_name)
            else:
                row.append('-')
        
        writer.writerow(row)
    
    return response


@login_required
@user_passes_test(Admin_group_required)
def download_allotments_csv(semester):
    allotments = get_allotment_data(semester)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="semester_{semester}_allotments.csv"'

    writer = csv.writer(response)
    writer.writerow(["Admission Number", "Name", "Department", "Category", "Pathway", "Paper 1", "Paper 2", "Paper 3", "Paper 4"])

    for data in allotments:
        writer.writerow([
            data['admission_number'], data['name'], data['department'], 
            data['admission_category'], data['pathway'], 
            data['paper1'], data['paper2'], data['paper3'], data['paper4']
        ])

    return response

# def get_allotment_data(semester):
#     allotments = CourseAllotment.objects.filter(batch__course__semester=semester)

#     student_allotments = {}
#     for allotment in allotments:
#         student = allotment.student
#         if student not in student_allotments:
#             student_allotments[student] = {}

#         paper_no = allotment.paper_no  
#         student_allotments[student][f'paper{paper_no}'] = allotment.batch.course.course_name

#     allotment_data = []
#     for student, papers in student_allotments.items():
#         allotment_data.append({
#             'admission_number': student.admission_number,
#             'name': student.name,
#             'department': student.department.name,
#             'admission_category': student.admission_category,
#             'pathway': student.pathway.name,
#             'paper1': papers.get('paper1', ''),
#             'paper2': papers.get('paper2', ''),
#             'paper3': papers.get('paper3', ''),
#             'paper4': papers.get('paper4', ''),
#         })

#     return allotment_data

def get_allotment_data(semester, department=None, admission_year=None):
    allotments = CourseAllotment.objects.filter(batch__course__semester=semester)

    if department:
        allotments = allotments.filter(student__department=department)

    if admission_year:
        allotments = allotments.filter(student__admission_year=admission_year)

    student_allotments = {}
    for allotment in allotments:
        student = allotment.student
        if student not in student_allotments:
            student_allotments[student] = {}

        paper_no = f'paper{allotment.paper_no}'
        student_allotments[student][paper_no] = allotment.batch.course.course_name

    allotment_data = []
    for student, papers in student_allotments.items():
        allotment_data.append({
            'admission_number': student.admission_number,
            'name': student.name,
            'department': student.department.name,
            'admission_category': student.admission_category,
            'pathway': student.pathway.name,
            'paper1': papers.get('paper1', ''),
            'paper2': papers.get('paper2', ''),
            'paper3': papers.get('paper3', ''),
            'paper4': papers.get('paper4', ''),
        })

    return allotment_data

@login_required
@user_passes_test(Admin_group_required)
def view_first_sem_allotments(request):
    if "download" in request.GET:  
        return download_allotments_csv(semester=1)  

    return render(request, 'admin/view_allotments.html', {
        'allotment_data': get_allotment_data(semester=1),
        'page_name': 'First Semester Allotments',
        'semester': 1  # Pass semester to template
    })

@login_required
@user_passes_test(Admin_group_required)
def view_second_sem_allotments(request):
    if "download" in request.GET:  
        return download_allotments_csv(semester=2)  

    return render(request, 'admin/view_allotments.html', {
        'allotment_data': get_allotment_data(semester=2),
        'page_name': 'Second Semester Allotments',
        'semester': 2  # Pass semester to template
    })

    
@login_required
@user_passes_test(Admin_group_required)
def view_allotment_results(request):
    """
    Displays filtered allotment results based on department, semester, and admission year.
    """
    form = StudentAllotmentFilterForm(request.GET or None)
    allotments = []

    if form.is_valid():
        semester = form.cleaned_data.get("semester")
        department = form.cleaned_data.get("department")
        admission_year = form.cleaned_data.get("admission_year")

        if semester:
            allotments = get_allotment_data(semester, department, admission_year)

    return render(request, "admin/allotment_results.html", {"form": form, "allotments": allotments})



@login_required
@user_passes_test(Admin_group_required)
def download_filtered_allotments_csv(request):
    """
    Generates a CSV file containing only the filtered allotment results.
    """
    form = StudentAllotmentFilterForm(request.GET or None)
    allotments = []

    if form.is_valid():
        semester = form.cleaned_data.get("semester")
        department = form.cleaned_data.get("department")
        admission_year = form.cleaned_data.get("admission_year")

        if semester:
            allotments = get_allotment_data(semester, department, admission_year)

    # Prepare CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="filtered_allotments.csv"'
    writer = csv.writer(response)

    # Write CSV headers
    writer.writerow(["Admission No.", "Name", "Department", "Pathway", "Category", "Paper 1", "Paper 2", "Paper 3", "Paper 4"])

    # Write data rows
    for allotment in allotments:
        writer.writerow([
            allotment["admission_number"],
            allotment["name"],
            allotment["department"],
            allotment["pathway"],
            allotment["admission_category"],
            allotment["paper1"],
            allotment["paper2"],
            allotment["paper3"],
            allotment["paper4"],
        ])

    return response




@login_required
@user_passes_test(student_group_required)
def view_student_allotment(request):
    try:
        student = request.user.student  # Fetch student linked to the logged-in user
    except AttributeError:
        return render(request, 'error.html', {'message': 'Student profile not found'})

    # Fetch all allotments for the student
    allotments = CourseAllotment.objects.filter(student=student, batch__course__semester=student.current_sem)

    if not allotments.exists():
        return render(request, 'student/view_allotment.html', {
            'student': student,
            'allotment_published': False  # Flag to indicate no allotments found
        })

    # Structure data for display
    allotted_courses = []
    for allotment in allotments:
        course = allotment.batch.course
        allotted_courses.append({
            'paper_no': allotment.paper_no,
            'course_name': course.course_name,
            'department': course.department.name
        })

    return render(request, 'student/view_allotment.html', {
        'student': student,
        'allotment_published': True,  # Flag to indicate allotment exists
        'allotted_courses': allotted_courses
    })
    


@login_required
@user_passes_test(Admin_group_required)  
def student_register(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        
        if form.is_valid():
            student = form.save(commit=False)
            username = student.admission_number.strip().lower()
            password = student.dob.strftime('%d%m%Y')  # ✅ Consistent password format (DDMMYYYY)

            existing_user = User.objects.filter(username=username).first()
            if existing_user is None:
                user = User.objects.create_user(username=username, password=password, email=student.email)
                
                # ✅ Ensure "Student" group exists and assign user to it
                student_group, created = Group.objects.get_or_create(name='Student')
                user.groups.add(student_group)

                student.user = user
                student.save()
                messages.success(request, "Student successfully registered!")
                return redirect('manage_students')
            else:
                messages.error(request, "Student with this admission number already exists.")
        else:
            print("Form Errors:", form.errors)  # ✅ Debugging info
            messages.error(request, "Invalid input. Please check your form.")
    else:
        form = StudentRegistrationForm()

    return render(request, 'admin/student_register.html', {'form': form})


@login_required
@user_passes_test(Admin_group_required)  
def bulk_student_upload(request):
    if request.method == "POST":
        form = BulkStudentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]

            if not csv_file.name.endswith(".csv"):
                messages.error(request, "Please upload a valid CSV file.")
                return redirect("bulk_student_upload")

            try:
                decoded_file = csv_file.read().decode("utf-8").splitlines()
                reader = csv.DictReader(decoded_file)

                students_to_create = []
                users_to_create = []
                existing_students = 0  # Counter for existing students
                new_students = 0  # Counter for new students

                # Ensure "Student" group exists
                student_group, created = Group.objects.get_or_create(name="Student")

                for row in reader:
                    admission_number = row.get("Admission Number")

                    if Student.objects.filter(admission_number=admission_number).exists():
                        existing_students += 1
                        continue  # Skip existing students

                    name = row.get("Name")
                    dob_str = row.get("Date of Birth")  
                    email = row.get("Email")
                    department_name = row.get("Department")
                    admission_category = row.get("Admission Category")
                    pathway_name = row.get("Pathway")
                    current_sem = row.get("Current Semester")
                    normalized_marks = row.get("Marks")

                    try:
                        dob = datetime.strptime(dob_str, "%d/%m/%Y").date()  
                        formatted_dob = dob.strftime("%d%m%Y")  
                    except ValueError:
                        messages.error(request, f"Invalid Date of Birth format: {dob_str}")
                        return redirect("bulk_student_upload")

                    try:
                        department = Department.objects.get(name=department_name)
                    except Department.DoesNotExist:
                        messages.error(request, f"Department '{department_name}' not found.")
                        return redirect("bulk_student_upload")

                    try:
                        pathway = Pathway.objects.get(name=pathway_name)
                    except Pathway.DoesNotExist:
                        messages.error(request, f"Pathway '{pathway_name}' not found.")
                        return redirect("bulk_student_upload")

                    user = None
                    if not User.objects.filter(username=admission_number).exists():
                        user = User(username=admission_number, email=email)
                        user.set_password(formatted_dob)
                        users_to_create.append(user)

                    student = Student(
                        admission_number=admission_number,
                        name=name,
                        dob=dob,
                        email=email,
                        department=department,
                        admission_category=admission_category,
                        pathway=pathway,
                        current_sem=int(current_sem),
                        normalized_marks=int(normalized_marks),
                        user=user if user else None
                    )
                    students_to_create.append(student)
                    new_students += 1  

                if users_to_create:
                    User.objects.bulk_create(users_to_create)

                # Assign users to "Student" group
                for user in users_to_create:
                    user.groups.add(student_group)

                for student in students_to_create:
                    student.user = User.objects.get(username=student.admission_number)

                if students_to_create:
                    Student.objects.bulk_create(students_to_create)

                # Show appropriate success message
                if new_students > 0:
                    messages.success(request, f"{new_students} students uploaded successfully!")
                if existing_students > 0 and new_students == 0:
                    messages.warning(request, "All students already exist. No new students uploaded.")

                return redirect("bulk_student_upload")

            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
                return redirect("bulk_student_upload")

    else:
        form = BulkStudentUploadForm()

    return render(request, "admin/bulk_student_upload.html", {"form": form})


@login_required
@user_passes_test(Admin_group_required)  
def manage_students(request):
    students = Student.objects.all()
    return render(request, 'admin/student_list.html', {'students': students})

@login_required
@user_passes_test(Admin_group_required)  
def student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    return render(request, 'admin/student_detail.html', {'student': student})

@login_required
@user_passes_test(Admin_group_required)  
def student_edit(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == 'POST':
        form = StudentEditForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Student details updated successfully!")
            return redirect('student_detail', student_id=student.id)
    else:
        form = StudentEditForm(instance=student)

    return render(request, 'admin/student_edit.html', {'form': form, 'student': student})

@login_required
@user_passes_test(Admin_group_required)
def student_delete(request, student_id):
    """Delete a student without confirmation page."""
    student = get_object_or_404(Student, id=student_id)
    
    if student.user is not None:
        student.user.delete()  # Delete associated user account
        
    student.delete()  # Delete student record
    messages.success(request, "Student deleted successfully!")  # Success message
    return redirect('manage_students')  # Redirect to student list page


@login_required
@user_passes_test(Admin_group_required)
def hod_list(request):
    hods = HOD.objects.all().order_by('id')  # Fetch all HODs sorted by ID
    paginator = Paginator(hods, 10)  # Show 10 HODs per page

    page_number = request.GET.get('page')
    hods_page = paginator.get_page(page_number)

    return render(request, 'admin/hod_list.html', {'hods': hods_page})

@login_required
@user_passes_test(Admin_group_required)
def hod_edit(request, hod_id):
    hod = get_object_or_404(HOD, id=hod_id)

    if request.method == 'POST':
        form = HODEditForm(request.POST, instance=hod)
        if form.is_valid():
            form.save()
            messages.success(request, "HOD details updated successfully!")
            return redirect('hod_list')
    else:
        form = HODEditForm(instance=hod)

    return render(request, 'admin/hod_edit.html', {'form': form, 'hod': hod})

@login_required
@user_passes_test(Admin_group_required)
def hod_delete(request, hod_id):
    """Delete an HOD without a confirmation page."""
    hod = get_object_or_404(HOD, id=hod_id)

    if hod.user is not None:
        hod.user.delete()  # Delete associated user account

    hod.delete()  # Delete HOD record
    messages.success(request, "HOD deleted successfully!")  # Success message
    return redirect('hod_list')  # Redirect to HOD list page

@login_required
@user_passes_test(Admin_group_required)
def add_hod(request):
    if request.method == "POST":
        form = HODForm(request.POST)
        if form.is_valid():
            hod = form.save()  # Save directly; HOD's save() will handle User creation

            # Ensure user is assigned to HOD group
            if hod.user:
                hod_group, created = Group.objects.get_or_create(name="hod")
                hod.user.groups.add(hod_group)

            messages.success(request, "HOD registered successfully!")
            return redirect('hod_list')  # Redirect after success
    else:
        form = HODForm()

    return render(request, 'admin/add_hod.html', {'form': form})

def hod_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        # Check if user exists and is linked to an HOD account
        if user is not None and HOD.objects.filter(user=user).exists():
            login(request, user)
            return redirect("hod_student_list")  # Redirect to HOD dashboard
        else:
            messages.error(request, "Invalid credentials or not an HOD.")

    return render(request, "login/hod_login.html")

def hod_logout(request):
    logout(request)
    return redirect("home")  # Redirect to home page after logout

@login_required
@user_passes_test(hod_group_required)
def hod_student_list(request):
    # Get students only from the HOD's department
    students = Student.objects.filter(department=request.user.hod.department).order_by('admission_number')
    
    return render(request, 'hod/student_list.html', {'students': students})

from django.shortcuts import get_object_or_404

@login_required
@user_passes_test(hod_group_required)
def hod_student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id, department=request.user.hod.department)
    return render(request, 'hod/student_detail.html', {'student': student})

@login_required
@user_passes_test(hod_group_required)
def hod_student_edit(request, student_id):
    student = get_object_or_404(Student, id=student_id, department=request.user.hod.department)

    if request.method == 'POST':
        form = StudentEditForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Student details updated successfully!")
            return redirect('hod_student_detail', student_id=student.id)
    else:
        form = StudentEditForm(instance=student)

    return render(request, 'hod/student_edit.html', {'form': form, 'student': student})

@login_required
@user_passes_test(hod_group_required)
def hod_student_delete(request, student_id):
    """ Delete a student via AJAX request """
    if request.method == "POST":
        student = get_object_or_404(Student, id=student_id)
        student.delete()
        return JsonResponse({"success": True})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})