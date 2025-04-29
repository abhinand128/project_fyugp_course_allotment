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
from datetime import date, datetime
from .models import (
    Student, Course, CoursePreference, Batch, CourseAllotment, 
    Department, Pathway, HOD,AllocationSettings
)
from .forms import (
    StudentForm, CourseFilterForm, CourseSelectionFormSem1, CourseSelectionFormSem2, 
    CourseForm, BatchForm, BatchFilterForm, BulkStudentUploadForm, 
    StudentRegistrationForm, StudentEditForm, HODEditForm, HODForm,StudentAllotmentFilterForm,AllocationSettingsForm
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

@transaction.atomic
def allocate_courses(semester):
    """Allocate courses for all students in the given semester"""
    # Clear existing allocations for this semester
    CourseAllotment.objects.filter(
        student__current_sem=semester
    ).delete()

    # 1. Allocate Paper 1 (DSC 1) - Core course from student's department
    for student in Student.objects.filter(current_sem=semester):
        allocate_paper(student, paper_no=1)

    # 2. Allocate Papers 2 & 3 based on academic performance
    if semester == 2:
        students = Student.objects.filter(current_sem=semester).order_by(
            F('first_sem_marks').desc(nulls_last=True)
        )
    else:
        students = Student.objects.filter(current_sem=semester).order_by('-normalized_marks')

    for paper_no in [2, 3]:  # DSC 2 and DSC 3
        for student in students:
            allocate_paper(student, paper_no=paper_no)

    # 3. Allocate Paper 4 (MDC) with improved quota handling
    # First pass: Try to allocate within department quotas
    for setting in AllocationSettings.objects.all():
        department = setting.department
        
        # Get all department students ordered by performance
        dept_students = Student.objects.filter(
            current_sem=semester,
            department=department
        ).order_by(
            F('first_sem_marks').desc(nulls_last=True) if semester == 2 else '-normalized_marks'
        )
        
        # Allocate to quota students first
        quota_categories = [
            ("General", setting.calculate_general_quota()),
            (["SC", "ST"], setting.calculate_sc_st_quota()),
            (["EWS", "Sports", "Management"], setting.calculate_other_quota())
        ]
        
        for categories, quota in quota_categories:
            if quota > 0:
                quota_students = dept_students.filter(
                    admission_category__in=categories if isinstance(categories, list) else categories
                )[:quota]
                
                for student in quota_students:
                    if not CourseAllotment.objects.filter(student=student, paper_no=4).exists():
                        allocate_paper(student, paper_no=4)

    # Second pass: Allocate remaining students who didn't get MDC yet
    remaining_students = Student.objects.filter(
        current_sem=semester
    ).exclude(
        id__in=CourseAllotment.objects.filter(paper_no=4).values('student')
    ).order_by(
        F('first_sem_marks').desc(nulls_last=True) if semester == 2 else '-normalized_marks'
    )
    
    for student in remaining_students:
        allocate_paper(student, paper_no=4, allow_any_mdc=True)

def allocate_paper(student, paper_no, allow_any_mdc=False):
    """
    Allocate a specific paper for a student
    :param student: Student object
    :param paper_no: Paper number (1-4)
    :param allow_any_mdc: If True and paper_no=4, can allocate any available MDC
    """
    # Check if already allocated this paper
    if CourseAllotment.objects.filter(student=student, paper_no=paper_no).exists():
        return True
    
    # Get student's preferences for this paper
    preferences = CoursePreference.objects.filter(
        student=student, 
        paper_no=paper_no
    ).order_by('preference_number')
    
    # Get already allotted batches to avoid duplicates
    allotted_batches = CourseAllotment.objects.filter(
        student=student
    ).values_list('batch', flat=True)
    
    # Try preferences first
    for preference in preferences:
        batch = preference.batch
        if (batch.status and 
            batch.course.seat_limit > CourseAllotment.objects.filter(batch=batch).count() and
            batch not in allotted_batches):
            
            CourseAllotment.objects.create(
                student=student, 
                batch=batch, 
                paper_no=paper_no
            )
            return True
    
    # For MDC (paper 4), try any available if allowed
    if paper_no == 4 and allow_any_mdc:
        available_mdc = Batch.objects.filter(
            course__course_type__name__startswith='MDC',
            course__semester=student.current_sem,
            status=True
        ).exclude(
            id__in=allotted_batches
        ).annotate(
            allocated_count=Count('courseallotment')
        ).filter(
            course__seat_limit__gt=F('allocated_count')
        ).order_by('allocated_count')  # Prefer less filled courses
        
        if available_mdc.exists():
            CourseAllotment.objects.create(
                student=student,
                batch=available_mdc.first(),
                paper_no=4
            )
            return True
    
    return False
    
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

def common_logout(request):
    logout(request)
    return redirect('home') 

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

    return render(
        request,
        "hod/hod_dashboard.html",
        {"page_name": "Dashboard", "hod": hod},
    )
@group_required('Student')
def student_reset_password(request):
    # Ensure only users in the "hod" group can access
    if not request.user.groups.filter(name='Student').exists():
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

    return render(request, 'student/student_reset_password.html', {'form': form})
    
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
    """Display a list of courses for dynamic filtering (no Apply button)."""
    courses = Course.objects.all()

    # Prepare distinct filter options
    course_types = Course.objects.values_list('course_type__name', flat=True).distinct()
    departments = Course.objects.values_list('department__name', flat=True).distinct()
    semesters = Course.objects.values_list('semester', flat=True).distinct()

    context = {
        'courses': courses,
        'course_types': course_types,
        'departments': departments,
        'semesters': semesters,
        'page_name': 'Manage Courses',
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

    # Calculate student statistics
    total_students = students.count()
    
    # Identify students who haven't submitted preferences
    students_without_preferences_list = [
        student for student in students
        if not student.coursepreference_set.exists()
    ]
    
    students_without_preferences = len(students_without_preferences_list)
    students_with_preferences = total_students - students_without_preferences
    
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

    # Calculate department-wise statistics
    department_stats = []
    departments = set(student.department for student in students)
    for dept in departments:
        dept_students = [s for s in students if s.department == dept]
        dept_total = len(dept_students)
        dept_complete = len([s for s in dept_students if s.coursepreference_set.exists()])
        dept_pending = dept_total - dept_complete
        department_stats.append({
            'name': dept.name,
            'total': dept_total,
            'complete': dept_complete,
            'pending': dept_pending
        })

    # Calculate pathway-wise statistics
    pathway_stats = []
    pathways = set(student.pathway for student in students if student.pathway)
    for pathway in pathways:
        pathway_students = [s for s in students if s.pathway == pathway]
        pathway_total = len(pathway_students)
        pathway_complete = len([s for s in pathway_students if s.coursepreference_set.exists()])
        pathway_pending = pathway_total - pathway_complete
        pathway_stats.append({
            'name': pathway,
            'total': pathway_total,
            'complete': pathway_complete,
            'pending': pathway_pending
        })

    if request.method == 'POST':
        if students_without_preferences:
            missing_students = ", ".join(str(student.admission_number) for student in students_without_preferences_list)
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
        'total_students': total_students,
        'students_with_preferences': students_with_preferences,
        'students_missing_preferences': students_without_preferences_list,
        'department_stats': department_stats,
        'pathway_stats': pathway_stats,
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

    # Get all second-semester students
    students = Student.objects.filter(
        current_sem=2
    ).prefetch_related(
        'coursepreference_set',
        'coursepreference_set__batch',
        'coursepreference_set__batch__course'
    ).order_by('admission_number')

    # Calculate student statistics
    total_students = students.count()
    
    # Identify students who haven't submitted preferences
    students_without_preferences_list = [
        student for student in students
        if not student.coursepreference_set.exists()
    ]
    
    students_without_preferences = len(students_without_preferences_list)
    students_with_preferences = total_students - students_without_preferences
    
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

    # Calculate department-wise statistics
    department_stats = []
    departments = set(student.department for student in students)
    for dept in departments:
        dept_students = [s for s in students if s.department == dept]
        dept_total = len(dept_students)
        dept_complete = len([s for s in dept_students if s.coursepreference_set.exists()])
        dept_pending = dept_total - dept_complete
        department_stats.append({
            'name': dept.name,
            'total': dept_total,
            'complete': dept_complete,
            'pending': dept_pending
        })

    # Calculate pathway-wise statistics
    pathway_stats = []
    pathways = set(student.pathway for student in students if student.pathway)
    for pathway in pathways:
        pathway_students = [s for s in students if s.pathway == pathway]
        pathway_total = len(pathway_students)
        pathway_complete = len([s for s in pathway_students if s.coursepreference_set.exists()])
        pathway_pending = pathway_total - pathway_complete
        pathway_stats.append({
            'name': pathway,
            'total': pathway_total,
            'complete': pathway_complete,
            'pending': pathway_pending
        })

    if request.method == 'POST':
        if students_without_preferences:
            missing_students = ", ".join(str(student.admission_number) for student in students_without_preferences_list)
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
        'total_students': total_students,
        'students_with_preferences': students_with_preferences,
        'students_missing_preferences': students_without_preferences_list,
        'department_stats': department_stats,
        'pathway_stats': pathway_stats,
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
    """Download a sample CSV file with headers and example data"""
    # Define CSV headers and sample data
    headers = [
        "Admission Number", "Name", "Date of Birth (DD/MM/YYYY)", 
        "Email", "Phone Number", "Department", "Admission Category", 
        "Admission Year", "Pathway", "Current Semester", 
        "PlusTwo Marks(normalized)"
    ]
    
    # Example data row
    example_data = [
        "STU001", "John Doe", "15/05/2000", "john@example.com", 
        "9876543210", "Computer Science", "General", "2023", 
        "Single Major", "1", "85"
    ]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="student_upload_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerow(example_data)
    writer.writerow(["", "", "", "", "", "", "", "", "", "", ""])  # Empty row for clarity
    writer.writerow(["# Required Fields: Admission Number, Name, Date of Birth, Email"])
    writer.writerow(["# Date Format: DD/MM/YYYY"])
    writer.writerow(["# Phone Number: 10 digits only"])
    
    return response

@group_required('Admin')  
def bulk_student_upload(request):
    if request.method == "POST":
        form = BulkStudentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            
            # Validate file extension
            if not csv_file.name.lower().endswith('.csv'):
                messages.error(request, "Only CSV files are allowed.")
                return redirect("bulk_student_upload")
            
            try:
                decoded_file = csv_file.read().decode("utf-8-sig").splitlines()
                reader = csv.DictReader(decoded_file)
                
                if not reader.fieldnames:
                    messages.error(request, "The CSV file is empty or improperly formatted.")
                    return redirect("bulk_student_upload")
                
                required_fields = [
                    "Admission Number", "Name", "Date of Birth (DD/MM/YYYY)", 
                    "Email", "Department", "Pathway"
                ]
                
                # Validate CSV headers
                missing_fields = [field for field in required_fields 
                                if field not in reader.fieldnames]
                if missing_fields:
                    messages.error(
                        request, 
                        f"Missing required columns: {', '.join(missing_fields)}"
                    )
                    return redirect("bulk_student_upload")
                
                with transaction.atomic():
                    student_group = Group.objects.get_or_create(name="Student")[0]
                    students_to_create = []
                    users_to_create = []
                    existing_count = 0
                    success_count = 0
                    errors = []
                    
                    for row_num, row in enumerate(reader, start=2):  # Start at 2 for header row
                        try:
                            # Validate required fields
                            admission_number = row["Admission Number"].strip()
                            if not admission_number:
                                raise ValidationError("Admission Number is required")
                                
                            if Student.objects.filter(admission_number=admission_number).exists():
                                existing_count += 1
                                continue
                            
                            # Parse and validate date
                            dob_str = row["Date of Birth (DD/MM/YYYY)"].strip()
                            try:
                                dob = datetime.strptime(dob_str, "%d/%m/%Y").date()
                                if dob > date.today():
                                    raise ValidationError("Date of Birth cannot be in the future")
                            except ValueError:
                                raise ValidationError("Invalid date format. Use DD/MM/YYYY")
                            
                            # Validate email
                            email = row["Email"].strip().lower()
                            if not email or "@" not in email:
                                raise ValidationError("Valid email is required")
                            if Student.objects.filter(email=email).exists():
                                raise ValidationError("Email already exists")
                            
                            # Validate phone number if provided
                            phone_number = row.get("Phone Number", "").strip()
                            if phone_number:
                                if not phone_number.isdigit() or len(phone_number) != 10:
                                    raise ValidationError("Phone number must be 10 digits")
                                if Student.objects.filter(phone_number=phone_number).exists():
                                    raise ValidationError("Phone number already exists")
                            
                            # Validate and get foreign key relationships
                            department = Department.objects.get(
                                name__iexact=row["Department"].strip()
                            )
                            pathway = Pathway.objects.get(
                                name__iexact=row["Pathway"].strip()
                            )
                            
                            # Validate admission category
                            admission_category = row.get("Admission Category", "General").strip()
                            valid_categories = dict(Student.CATEGORY)
                            if admission_category not in valid_categories:
                                raise ValidationError(f"Invalid admission category. Valid options: {', '.join(valid_categories.keys())}")
                            
                            # Validate admission year
                            admission_year = row.get("Admission Year", str(date.today().year)).strip()
                            try:
                                admission_year = int(admission_year)
                                if not (2000 <= admission_year <= date.today().year):
                                    raise ValidationError(f"Admission year must be between 2000 and {date.today().year}")
                            except ValueError:
                                raise ValidationError("Admission year must be a number")
                            
                            # Validate current semester
                            current_sem = row.get("Current Semester", "1").strip()
                            try:
                                current_sem = int(current_sem)
                                if not (1 <= current_sem <= 8):
                                    raise ValidationError("Current semester must be between 1 and 8")
                            except ValueError:
                                raise ValidationError("Current semester must be a number")
                            
                            # Validate normalized marks
                            normalized_marks = row.get("PlusTwo Marks(normalized)", "0").strip()
                            try:
                                normalized_marks = int(normalized_marks)
                                if not (0 <= normalized_marks <= 100):
                                    raise ValidationError("Normalized marks must be between 0 and 100")
                            except ValueError:
                                raise ValidationError("Normalized marks must be a number")
                            
                            # Create user
                            if not User.objects.filter(username=admission_number).exists():
                                user = User(
                                    username=admission_number,
                                    email=email,
                                    is_active=True
                                )
                                user.set_password(dob.strftime('%d%m%Y'))
                                users_to_create.append(user)
                            
                            # Create student
                            student = Student(
                                admission_number=admission_number,
                                name=row["Name"].strip(),
                                dob=dob,
                                email=email,
                                phone_number=phone_number or None,
                                department=department,
                                admission_category=admission_category,
                                admission_year=admission_year,
                                pathway=pathway,
                                current_sem=current_sem,
                                normalized_marks=normalized_marks
                            )
                            students_to_create.append(student)
                            success_count += 1
                            
                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)}")
                            continue
                    
                    # Bulk create in optimal order
                    if users_to_create:
                        User.objects.bulk_create(users_to_create)
                        # Need to fetch users again to get their IDs
                        created_users = User.objects.filter(
                            username__in=[u.username for u in users_to_create]
                        )
                        user_map = {user.username: user for user in created_users}
                        
                        # Assign users to students
                        for student in students_to_create:
                            student.user = user_map.get(student.admission_number)
                    
                    if students_to_create:
                        Student.objects.bulk_create(students_to_create)
                    
                    # Assign student group to new users
                    if users_to_create:
                        for user in created_users:
                            user.groups.add(student_group)
                    
                    # Prepare result message
                    result_msg = []
                    if success_count:
                        result_msg.append(f"Successfully created {success_count} students")
                    if existing_count:
                        result_msg.append(f"Skipped {existing_count} existing students")
                    if errors:
                        result_msg.append(f"{len(errors)} rows had errors")
                        messages.warning(request, "<br>".join(result_msg))
                        messages.error(request, "<br>".join(errors[:10]))  # Show first 10 errors
                    elif success_count:
                        messages.success(request, "<br>".join(result_msg))
                    else:
                        messages.warning(request, "No new students were created")
                    
                    return redirect("bulk_student_upload")
            
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
                return redirect("bulk_student_upload")
    
    else:
        form = BulkStudentUploadForm()
    
    return render(request, "admin/bulk_student_upload.html", {
        "form": form,
        "departments": Department.objects.all(),
        "pathways": Pathway.objects.all()
    })


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
    
    # Get all pathways for this department (for the filter dropdown)
    pathways = Pathway.objects.all()
    
    context = {
        'students': students,
        'pathways': pathways,
        'page_title': 'Student Management'
    }
    
    return render(request, 'hod/student_list.html', context)

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

@group_required('hod')
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


@group_required('Admin')
def allocation_settings_view(request):
    if request.method == 'POST':
        form = AllocationSettingsForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved successfully!')
            return redirect('allocation_settings')
    else:
        departments_with_settings = Department.objects.filter(
            allocationsettings__isnull=False
        ).values_list('id', flat=True)

        available_departments = Department.objects.filter(
            isMajor=True
        ).exclude(id__in=departments_with_settings)

        form = AllocationSettingsForm()
        form.fields['department'].queryset = available_departments  

    settings = AllocationSettings.objects.select_related('department').all()

    context = {
        'form': form,
        'settings': settings,
    }
    return render(request, 'admin/allocation_settings.html', context)

@group_required('Admin')
def edit_allocation_setting(request, pk):
    setting = AllocationSettings.objects.get(pk=pk)
    if request.method == 'POST':
        form = AllocationSettingsForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, f'{setting.department} settings updated successfully!')
            return redirect('allocation_settings')
    else:
        form = AllocationSettingsForm(instance=setting)
    
    return render(request, 'admin/edit_setting.html', {'form': form, 'setting': setting})

@group_required('Admin')
def delete_allocation_setting(request, pk):
    setting = AllocationSettings.objects.get(pk=pk)
    if request.method == 'POST':
        setting.delete()
        messages.success(request, f'{setting.department} settings deleted successfully!')
        return redirect('allocation_settings')
    return render(request, 'admin/delete_setting.html', {'setting': setting})
