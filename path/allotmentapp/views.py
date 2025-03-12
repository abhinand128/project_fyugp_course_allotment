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
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import F, Max, Count
from .decorators import group_required
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
                print(f"Student {student.admission_number} (Sem {semester}) could not be allocated Paper 1. All preferences full.")

        # 2. Allocate Papers 2 & 3 based on marks
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
                    print(f"Student {student.admission_number} (Sem {semester}) could not be allocated Paper {paper_no}. All preferences full.")

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

            selected_students = general_students + sc_st_students + other_students

            # ✅ Ensure one MDC course per student based on highest preference
            for student in selected_students:
                allotted_batches = CourseAllotment.objects.filter(student=student).values_list('batch', flat=True)
                
                # Get all MDC preferences sorted by priority
                preferences = CoursePreference.objects.filter(student=student, paper_no=4).exclude(batch__in=allotted_batches).order_by('preference_number')

                allocated = False
                for preference in preferences:
                    batch = preference.batch
                    seat_count = CourseAllotment.objects.filter(batch=batch).count()  # Optimized

                    if batch.status and batch.course.seat_limit > seat_count:
                        CourseAllotment.objects.create(student=student, batch=batch, paper_no=4)
                        allocated = True
                        break  # ✅ Ensures exactly one MDC course per student

                if not allocated:
                    print(f"Student {student.admission_number} (Sem {semester}) could not be allocated Paper 4 (MDC). All preferences full.")
           
    
def index(request):
    return render(request, 'registration/login.html')

def common_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        print(f"Trying to authenticate: {username}")  # Debugging

        user = authenticate(request, username=username, password=password)

        if user is not None:
            print(f"Authenticated user: {user.username}")  # Debugging

            # Check group membership
            if user.groups.filter(name="Admin").exists():
                login(request, user)
                print("Redirecting to admin dashboard")  # Debugging
                return redirect("admin_dashboard")

            elif user.groups.filter(name="hod").exists():
                login(request, user)
                print("Redirecting to HOD dashboard")  # Debugging
                return redirect("hod_dashboard")

            elif user.groups.filter(name="Student").exists():
                login(request, user)
                print("Redirecting to student dashboard")  # Debugging
                return redirect("student_dashboard")

            else:
                messages.error(request, "User role not assigned. Contact admin.")
                print("User has no assigned role.")  # Debugging

        else:
            messages.error(request, "Invalid username or password.")
            print("Authentication failed.")  # Debugging

    return render(request, "registration/login.html")


def admin_reset_password(request):
    # Ensure only users in the "Admin" group can access
    if not request.user.groups.filter(name='Admin').exists():
        messages.error(request, "You are not authorized to access this page.")
        return redirect('home')  # Redirect back to dashboard

    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)  # Keep user logged in
            messages.success(request, "Your password has been successfully updated.")
            return redirect('home')  # Redirect after success
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'admin/admin_reset_password.html', {'form': form})

@group_required('Admin')
def manage_allotment(request):
    """Render the manage courses page."""
    return render(request, 'admin/manage_allocation.html', {'page_name': 'manage allocation'})


@group_required('Admin')
def admin_dashboard(request):
    return render(request, 'admin/dashboard.html', {'page_name': 'Dashboard'})

@group_required("Student")
@login_required
def student_dashboard(request):
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        student = None  # Handle case where Student record is missing
    
    return render(
        request,
        "student/student_dashboard.html",
        {"page_name": "Dashboard", "student": student},
    )
@group_required("hod")
@login_required
def hod_dashboard(request):
    hod = None
    try:
        hod = HOD.objects.get(user=request.user)  # Query the HOD model
    except HOD.DoesNotExist:
        pass  # Handle case where no HOD record exists
    print(hod)
    return render(
        request,
        "hod/hod_dashboard.html",
        {"page_name": "Dashboard", "hod": hod},
    )

    
@group_required('Student')
def student_profile(request):
    student = Student.objects.get(user=request.user)  # Fetch the logged-in student's details
    return render(request, 'student/profile.html', {'student': student})


@group_required('Student')
def view_courses_student(request):
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        student = None  # Handle case where Student record is missing
    """Display a list of courses with optional filters."""
    form = CourseFilterForm(request.GET)  # Initialize the filter form
    courses = Course.objects.all()

    # Apply filters if the form is valid
    if form.is_valid():
        course_type = form.cleaned_data.get('course_type')
        department = form.cleaned_data.get('department')
        semester = form.cleaned_data.get('semester')

        if course_type:
            courses = courses.filter(course_type__name__startswith=course_type)
        if department:
            courses = courses.filter(department=department)
        if semester:
            courses = courses.filter(semester=semester)

    context = {
        'courses': courses,
        'form': form,
        'page_name': 'Courses',
        'student': student,
    }
    return render(request, 'student/view_courses_students.html', context)




@group_required('Student')
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
        'student': student,
        
    })

@group_required('Student') 
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

@group_required('Student')  
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


@group_required('Admin')
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
            courses = courses.filter(course_type__name__startswith=course_type)
        if department:
            courses = courses.filter(department=department)
        if semester:
            courses = courses.filter(semester=semester)

    context = {
        'courses': courses,
        'form': form,
        'page_name': 'Manage Courses',  # Passed dynamically
    }
    return render(request, 'admin/manage_courses.html', context)

@group_required('Admin')
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

@group_required('Admin')
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

@group_required('Admin')
def delete_course(request, course_id):
    """Delete a course."""
    course = get_object_or_404(Course, id=course_id)
    course.delete()
    messages.success(request, "Course deleted successfully!")# Delete the course
    return redirect('manage_courses')  # Redirect to the courses page

@group_required('Admin')
def create_batch(request):
    courses = Course.objects.all()  # Default to all courses
    filter_form = CourseFilterForm(request.GET or None)

    if filter_form.is_valid():
        course_type = filter_form.cleaned_data.get('course_type')
        department = filter_form.cleaned_data.get('department')
        semester = filter_form.cleaned_data.get('semester')

        if course_type:
            courses = courses.filter(course_type__name__startswith=course_type)
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
        'courses': courses,
        'page_name': 'Create Batch',
    })







@group_required('Admin')
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
        'course': course,
        'page_name': 'Edit Batch',
    })
    
@group_required('Admin')
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
            'page_name': 'Manage Batches',
        }
    )

@group_required('Admin')
def delete_batch(request, batch_id):
    """Delete a batch."""
    batch = get_object_or_404(Batch, id=batch_id)
    batch.delete()
    return redirect('admin/manage_batches')  # Redirect to the batches page after deletion


def get_current_academic_year():
    current_year = datetime.now().year
    next_year = current_year + 1
    return f"{current_year}-{next_year}"

# @group_required('Admin')
# def first_sem_allotment(request):

#     current_academic_year = get_current_academic_year()

#     if CourseAllotment.objects.filter(batch__course__semester=1, batch__year=current_academic_year).exists():
#         messages.warning(request, "Courses are already allocated for the first semester in the current academic year!")
#         return render(request, 'admin/first_sem_allotment.html', {'already_allocated': True})

#     # Get all first semester students
#     students = Student.objects.filter(
#         current_sem=1
#     ).prefetch_related(
#         'coursepreference_set',
#         'coursepreference_set__batch',
#         'coursepreference_set__batch__course'
#     ).order_by('admission_number')

#     # Get unique paper numbers and their maximum preferences
#     paper_preferences = CoursePreference.objects.filter(
#         student__current_sem=1
#     ).values('paper_no', 'preference_number').distinct().order_by('paper_no', 'preference_number')

#     # Create a structure of paper-preference combinations
#     paper_options = {}
#     for pref in paper_preferences:
#         paper_no = pref['paper_no']
#         pref_no = pref['preference_number']
#         if paper_no not in paper_options:
#             paper_options[paper_no] = []
#         paper_options[paper_no].append(pref_no)

#     if request.method == 'POST':
#         try:
#             allocate_courses(semester=1)
#             messages.success(request, "First semester course allotment completed successfully! Redirecting to view allotments...")
#             CoursePreference.objects.filter(student__current_sem=1).delete()
#             return redirect('view_first_sem_allotments')
#         except Exception as e:
#             messages.error(request, f"An error occurred during allotment: {e}")

#     context = {
#         'page_name': 'First Semester Allotment',
#         'students': students,
#         'paper_options': paper_options,
#     }
    
#     return render(request, 'admin/first_sem_allotment.html', context)
@group_required('Admin')
def first_sem_allotment(request):
    current_academic_year = get_current_academic_year()

    # Check if courses are already allocated
    if CourseAllotment.objects.filter(batch__course__semester=1, batch__year=current_academic_year).exists():
        messages.warning(request, "Courses are already allocated for the first semester in the current academic year!")
        return render(request, 'admin/first_sem_allotment.html', {'already_allocated': True})

    # Get all first-semester students
    students = Student.objects.filter(
        current_sem=1
    ).prefetch_related(
        'coursepreference_set',
        'coursepreference_set__batch',
        'coursepreference_set__batch__course'
    ).order_by('admission_number')

    # Identify students who haven't submitted preferences
    students_without_preferences = [
        student.admission_number
        for student in students
        if not student.coursepreference_set.exists()
    ]

    # Get unique paper numbers and their maximum preferences
    paper_preferences = CoursePreference.objects.filter(
        student__current_sem=1
    ).values('paper_no', 'preference_number').distinct().order_by('paper_no', 'preference_number')

    # Structure paper-preference combinations
    paper_options = {}
    for pref in paper_preferences:
        paper_no = pref['paper_no']
        pref_no = pref['preference_number']
        if paper_no not in paper_options:
            paper_options[paper_no] = []
        paper_options[paper_no].append(pref_no)

    if request.method == 'POST':
        if students_without_preferences:
            missing_students = ", ".join(map(str, students_without_preferences))
            messages.error(request, f"The following students have not submitted their preferences: {missing_students}. Please ask them to submit before proceeding.")
        else:
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
        'students_without_preferences': students_without_preferences,
    }

    return render(request, 'admin/first_sem_allotment.html', context)


@group_required('Admin')
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
        'Pathway',
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

@group_required('Admin')
def second_sem_allotment(request):
    current_academic_year = get_current_academic_year()

    # Check if courses are already allocated
    if CourseAllotment.objects.filter(batch__course__semester=2, batch__year=current_academic_year).exists():
        messages.warning(request, "Courses are already allocated for the second semester in the current academic year!")
        return render(request, 'admin/second_sem_allotment.html', {'already_allocated': True})

    # Get all first-semester students
    students = Student.objects.filter(
        current_sem=2
    ).prefetch_related(
        'coursepreference_set',
        'coursepreference_set__batch',
        'coursepreference_set__batch__course'
    ).order_by('admission_number')

    # Identify students who haven't submitted preferences
    students_without_preferences = [
        student.admission_number
        for student in students
        if not student.coursepreference_set.exists()
    ]

    # Get unique paper numbers and their maximum preferences
    paper_preferences = CoursePreference.objects.filter(
        student__current_sem=2
    ).values('paper_no', 'preference_number').distinct().order_by('paper_no', 'preference_number')

    # Structure paper-preference combinations
    paper_options = {}
    for pref in paper_preferences:
        paper_no = pref['paper_no']
        pref_no = pref['preference_number']
        if paper_no not in paper_options:
            paper_options[paper_no] = []
        paper_options[paper_no].append(pref_no)

    if request.method == 'POST':
        if students_without_preferences:
            missing_students = ", ".join(map(str, students_without_preferences))
            messages.error(request, f"The following students have not submitted their preferences: {missing_students}. Please ask them to submit before proceeding.")
        else:
            try:
                allocate_courses(semester=2)
                messages.success(request, "Second semester course allotment completed successfully! Redirecting to view allotments...")
                CoursePreference.objects.filter(student__current_sem=2).delete()
                return redirect('view_second_sem_allotments')
            except Exception as e:
                messages.error(request, f"An error occurred during allotment: {e}")

    context = {
        'page_name': 'Second Semester Allotment',
        'students': students,
        'paper_options': paper_options,
        'students_without_preferences': students_without_preferences,
    }

    return render(request, 'admin/second_sem_allotment.html', context)

@group_required('Admin')
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
        'Pathway',
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


@group_required('Admin')
def download_allotments_csv(request, semester):
    allotments = get_allotment_data(semester)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="semester_{semester}_allotments.csv"'

    writer = csv.writer(response)

    # Define paper names based on semester
    if semester == 1:
        paper_headers = ["Paper 1 (DSC 1)", "Paper 2 (DSC 2)", "Paper 3 (DSC 3)", "Paper 4 (MDC)"]
    elif semester == 2:
        paper_headers = ["Paper 1 (DSC 4)", "Paper 2 (DSC 5)", "Paper 3 (DSC 6)", "Paper 4 (MDC)"]
    else:
        paper_headers = ["Paper 1", "Paper 2", "Paper 3", "Paper 4"]  # Default if other semesters are added

    # Write the header row
    writer.writerow(["Admission Number", "Name", "Department", "Category", "Pathway"] + paper_headers)

    # Write student allotment data
    for data in allotments:
        writer.writerow([
            data['admission_number'], data['name'], data['department'], 
            data['admission_category'], data['pathway'], 
            data['paper1'], data['paper2'], data['paper3'], data['paper4']
        ])

    return response


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

@group_required('Admin')
def view_first_sem_allotments(request):
    if "download" in request.GET:  
        return download_allotments_csv(request, semester=1)  # ✅ Now passing request

    return render(request, 'admin/view_allotments.html', {
        'allotment_data': get_allotment_data(semester=1),
        'page_name': 'First Semester Allotments',
        'semester': 1  # Pass semester to template
    })

@group_required('Admin')
def view_second_sem_allotments(request):
    if "download" in request.GET:  
        return download_allotments_csv(request, semester=2)  

    return render(request, 'admin/view_allotments.html', {
        'allotment_data': get_allotment_data(semester=2),
        'page_name': 'Second Semester Allotments',
        'semester': 2  # Pass semester to template
    })

    
@group_required('Admin')
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



import csv
from django.http import HttpResponse

@group_required('Admin')
def download_filtered_allotments_csv(request):
    """
    Generates a CSV file containing only the filtered allotment results.
    """
    form = StudentAllotmentFilterForm(request.GET or None)
    allotments = []
    semester = None
    admission_year = None

    if form.is_valid():
        semester = form.cleaned_data.get("semester")
        department = form.cleaned_data.get("department")
        admission_year = form.cleaned_data.get("admission_year")

        if semester:
            # Ensure semester is treated as an integer
            try:
                semester = int(semester)
            except ValueError:
                semester = None  # Handle unexpected values

            allotments = get_allotment_data(semester, department, admission_year)

    


    paper_headers = ["Paper 1", "Paper 2", "Paper 3", "Paper 4"]  # Default values

    if semester == 1:
        paper_headers = ["Paper 1 (DSC 1)", "Paper 2 (DSC 2)", "Paper 3 (DSC 3)", "Paper 4 (MDC)"]
    elif semester == 2:
        paper_headers = ["Paper 1 (DSC 4)", "Paper 2 (DSC 5)", "Paper 3 (DSC 6)", "Paper 4 (MDC)"]

    
    file_name = "filtered_allotments"
    if semester:
        file_name += f"_sem{semester}"
    if admission_year:
        file_name += f"_year{admission_year}"
    file_name += ".csv"

    

    # Prepare CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    writer = csv.writer(response)

    # ✅ Write the correct headers
    headers = ["Admission No.", "Name", "Department", "Pathway", "Category"] + paper_headers
    writer.writerow(headers)

    # ✅ Write data rows
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




@group_required('Student') 
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
    


@group_required('Admin')  
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
@group_required('Admin')
def download_sample_csv(request):
    # Define CSV headers
    headers = [
        "Admission Number", "Name", "Date of Birth", "Email", "Phone Number",
        "Department", "Admission Category", "Admission Year",
        "Pathway", "Current Semester", "PlusTwo Marks(normalized)"
    ]
    

    # Create the HTTP response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="sample_students.csv"'

    writer = csv.writer(response)
    writer.writerow(headers)  # Write headers
    return response

@group_required('Admin')  
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
                    phone_number = row.get("Phone Number")
                    department_name = row.get("Department")
                    admission_category = row.get("Admission Category")
                    pathway_name = row.get("Pathway")
                    current_sem = row.get("Current Semester")
                    normalized_marks = row.get("PlusTwo Marks(normalized)")
                    admission_year = row.get("Admission Year")

                    # Validate Date of Birth
                    try:
                        dob = datetime.strptime(dob_str, "%d/%m/%Y").date()  
                        formatted_dob = dob.strftime("%d%m%Y")  
                    except ValueError:
                        messages.error(request, f"Invalid Date of Birth format: {dob_str}")
                        return redirect("bulk_student_upload")

                    # Validate Admission Year
                    try:
                        admission_year = int(admission_year)
                        if admission_year < 2000 or admission_year > datetime.today().year:
                            raise ValueError
                    except ValueError:
                        messages.error(request, f"Invalid Admission Year: {admission_year}")
                        return redirect("bulk_student_upload")

                    # Check for duplicate phone number
                    if Student.objects.filter(phone_number=phone_number).exists():
                        messages.error(request, f"Phone number '{phone_number}' already exists.")
                        return redirect("bulk_student_upload")

                    # Get related foreign key objects
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
                        phone_number=phone_number,
                        department=department,
                        admission_category=admission_category,
                        admission_year=admission_year,
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



@group_required('Admin')  
def manage_students(request):
    students = Student.objects.all()
    return render(request, 'admin/student_list.html', {'students': students})

@group_required('Admin')  
def student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    return render(request, 'admin/student_detail.html', {'student': student})

@group_required('Admin')  
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

@group_required('Admin')
def student_delete(request, student_id):
    """Delete a student without confirmation page."""
    student = get_object_or_404(Student, id=student_id)
    
    if student.user is not None:
        student.user.delete()  # Delete associated user account
        
    student.delete()  # Delete student record
    messages.success(request, "Student deleted successfully!")  # Success message
    return redirect('manage_students')  # Redirect to student list page


@group_required('Admin')
def hod_list(request):
    hods = HOD.objects.all().order_by('id')  # Fetch all HODs sorted by ID
    paginator = Paginator(hods, 10)  # Show 10 HODs per page

    page_number = request.GET.get('page')
    hods_page = paginator.get_page(page_number)

    return render(request, 'admin/hod_list.html', {'hods': hods_page})

@group_required('Admin')
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

@group_required('Admin')
def hod_delete(request, hod_id):
    """Delete an HOD without a confirmation page."""
    hod = get_object_or_404(HOD, id=hod_id)

    if hod.user is not None:
        hod.user.delete()  # Delete associated user account

    hod.delete()  # Delete HOD record
    messages.success(request, "HOD deleted successfully!")  # Success message
    return redirect('hod_list')  # Redirect to HOD list page

@group_required('Admin')
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

@group_required('hod')
def hod_student_list(request):
    # Get students only from the HOD's department
    students = Student.objects.filter(department=request.user.hod.department).order_by('admission_number')
    
    return render(request, 'hod/student_list.html', {'students': students})

from django.shortcuts import get_object_or_404

@group_required('hod')
def hod_student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id, department=request.user.hod.department)
    return render(request, 'hod/student_detail.html', {'student': student})

@group_required('hod')
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

@group_required('hod')
def hod_student_delete(request, student_id):
    """ Delete a student via AJAX request """
    if request.method == "POST":
        student = get_object_or_404(Student, id=student_id)
        student.delete()
        return JsonResponse({"success": True})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})

def hod_reset_password(request):
    # Ensure only users in the "hod" group can access
    if not request.user.groups.filter(name='hod').exists():
        messages.error(request, "You are not authorized to access this page.")
        return redirect('home')  # Redirect back to dashboard

    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)  # Keep user logged in
            messages.success(request, "Your password has been successfully updated.")
            return redirect('home')  # Redirect after success
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'hod/hod_reset_password.html', {'form': form})