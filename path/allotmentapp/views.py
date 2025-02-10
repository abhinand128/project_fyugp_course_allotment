from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .models import Student,Course,CoursePreference,Batch,CourseAllotment
from .forms import StudentForm,CourseFilterForm,CourseSelectionForm,CourseForm,BatchForm,BatchFilterForm
from django.db import transaction

def allocate_courses():
    with transaction.atomic():
        # 1. Allocate Paper 1:
        for student in Student.objects.all():
            allocated = False
            preferences = CoursePreference.objects.filter(student=student, paper_no=1).order_by('preference_number')
            for preference in preferences:
                batch = preference.batch
                if batch.status and batch.course.seat_limit > CourseAllotment.objects.filter(batch=batch).count():
                    CourseAllotment.objects.create(student=student, batch=batch, paper_no=1)  # paper_no = 1
                    allocated = True
                    break

            if not allocated:
                print(f"Warning: Student {student.admission_number} could not be allocated Paper 1. All preferences full.")
                # Add default allocation logic here if needed (see previous examples)

        # 2. Allocate remaining papers (2, 3, 4...):
        for paper_no in range(2, 5):
            students = Student.objects.order_by('-normalized_marks')
            for student in students:
                allocated = False
                allotted_batches = CourseAllotment.objects.filter(student=student).values_list('batch', flat=True)
                preferences = CoursePreference.objects.filter(student=student, paper_no=paper_no).exclude(batch__in=allotted_batches).order_by('preference_number')
                for preference in preferences:
                    batch = preference.batch
                    if batch.status and batch.course.seat_limit > CourseAllotment.objects.filter(batch=batch).count():
                        CourseAllotment.objects.create(student=student, batch=batch, paper_no=paper_no)  # Save paper_no
                        allocated = True
                        break

                if not allocated:
                    print(f"Warning: Student {student.admission_number} could not be allocated Paper {paper_no}. All preferences full.")
                    # Add default allocation logic here if needed (see previous examples)


    
def index(request):
    return render(request, 'index.html')

def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_superuser:  # Ensure only superusers can log in
            login(request, user)
            return redirect("admin_dashboard")  # Redirect to admin dashboard
        else:
            messages.error(request, "Invalid credentials or not an admin.")

    return render(request, "login/admin_login.html")  # Render custom admin login page

def manage_allotment(request):
    """Render the manage courses page."""
    return render(request, 'admin/manage_allocation.html', {'page_name': 'manage allocation'})


def first_sem_allotment(request):
    """Render the manage courses page."""
    return render(request, 'admin/first_sem_allotment.html', {'page_name': 'first semester allotment'})


def admin_logout(request):
    logout(request)
    return redirect('home')  # Redirect to the login page after logout


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


def admin_dashboard(request):
    return render(request, 'admin/dashboard.html', {'page_name': 'Dashboard'})

def add_student(request):
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Student added successfully!")
            return redirect('student_list')  # Change this to your actual student listing URL
        else:
            messages.error(request, "Error adding student. Please check the form.")
    else:
        form = StudentForm()
    return render(request, 'admin/add_student.html', {'form': form})

def student_dashboard(request):
    # You can pass additional context like page_name if needed
    return render(request, 'student/student_dashboard.html', {'page_name': 'Dashboard'})

from django.contrib.auth import logout
from django.shortcuts import redirect

def student_logout(request):
    logout(request)
    return redirect('home')  # Redirect to the login page after logout

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


from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import CoursePreference, Student
from .forms import CourseSelectionForm

def course_selection(request):
    try:
        student = Student.objects.select_related('pathway', 'department').get(user=request.user)
        print("Student Object:", student)
        print("Student Department:", student.department)
        print("Student Pathway:", student.pathway)
    except Student.DoesNotExist:
        print("No student found for admission number:", request.user.username)
        return render(request, 'error.html', {'message': 'Student not found'})

   # Check if preferences or allotment already exist
    existing_preferences = CoursePreference.objects.filter(student=student).exists()
    already_allocated = CourseAllotment.objects.filter(student=student).exists()

    if existing_preferences or already_allocated:
        return render(request, 'student/course_selection.html', {
            'view_preferences': True,
            'already_submitted': True,
            'already_allocated': already_allocated,
            'student': student  # Pass student explicitly
        })

    if request.method == 'POST':
        form = CourseSelectionForm(request.POST, student=student)
        if form.is_valid():
            preferences = []

            # Handle DSC 1 separately
            preferences.append(
                CoursePreference(
                    student=student,
                    batch=form.cleaned_data["dsc_1"],
                    preference_number=1,  # Always first preference
                    paper_no=1  # DSC 1
                )
            )

            # Handle other DSC and MDC selections dynamically
            for field_name, batch in form.cleaned_data.items():
                if "option" in field_name or field_name.startswith("mdc"):
                    preference_number = int(field_name.split("_")[-1])  # Extract preference number

                    # Determine paper_no
                    paper_no = 2 if field_name.startswith("dsc_2") else \
                               3 if field_name.startswith("dsc_3") else \
                               4 if field_name.startswith("mdc") else None

                    if paper_no:
                        preferences.append(
                            CoursePreference(
                                student=student,
                                batch=batch,
                                preference_number=preference_number,
                                paper_no=paper_no
                            )
                        )

            # Bulk create preferences
            CoursePreference.objects.bulk_create(preferences)

            return redirect('view_preferences')  # Redirect after successful submission

    else:
        form = CourseSelectionForm(student=student)

    # Debugging response
    debug_info = {
        "student": str(student),
        "pathway": str(student.pathway),
        "pathway_name": student.pathway.name if student.pathway else "None"
    }
    print("Debug Info:", debug_info)

    return render(request, 'student/course_selection.html', {
        'form': form,
        'already_submitted': False,
        'student': student  # Pass student explicitly
    })



def view_preferences(request):
    student = request.user.student  # Get the logged-in student

    # Fetch selected preferences and order by preference number
    preferences = CoursePreference.objects.filter(student=student).order_by('preference_number')

    # Organizing preferences using paper_no
    categorized_preferences = {
        1: {},  # DSC1
        2: {},  # DSC2
        3: {},  # DSC3
        4: {}   # MDC
    }

    for pref in preferences:
        paper_no = pref.paper_no  # Use the new field
        preference_key = f"option_{pref.preference_number}"  # Ensure uniqueness
        categorized_preferences[paper_no][preference_key] = pref

    return render(request, 'student/view_preferences.html', {
        'categorized_preferences': categorized_preferences
    })


def manage_courses(request):
    """Render the manage courses page."""
    return render(request, 'admin/manage_courses.html', {'page_name': 'Manage Courses'})

def view_courses(request):
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
    return render(request, 'admin/view_courses.html', context)


def edit_courses(request):
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
    return render(request, 'admin/edit_courses.html', context)

def add_course(request):
    """Add a new course."""
    if request.method == 'POST':
        form = CourseForm(request.POST)  # Handle form submission
        if form.is_valid():
            form.save()
            return redirect('view_courses')  # Redirect to the courses page
    else:
        form = CourseForm()  # Create an empty form for GET request

    return render(request, 'admin/add_course.html', {'form': form, 'page_name': 'Add Course'})

def edit_course(request, course_id):
    """Edit an existing course."""
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            return redirect('view_courses')  # Redirect to the courses page
    else:
        form = CourseForm(instance=course)  # Populate form with course data

    context = {
        'form': form,
        'course': course,
        'page_name': 'Edit Course',  # Passed dynamically
    }
    return render(request, 'admin/edit_course.html', context)

def delete_course(request, course_id):
    """Delete a course."""
    course = get_object_or_404(Course, id=course_id)
    course.delete()  # Delete the course
    return redirect('view_courses')  # Redirect to the courses page

def view_batches(request):
    """Display all batches."""
    batches = Batch.objects.all()
    return render(request, 'admin/view_batches.html', {'batches': batches})

def manage_batches(request):
    """Render the manage batches page."""
    return render(request, 'admin/manage_batches.html')

def edit_batches(request):
    """Display all batches."""
    batches = Batch.objects.all()
    return render(request, 'admin/edit_batches.html', {'batches': batches})



def create_batch(request):
    courses = Course.objects.all()  # Default all courses
    filter_form = CourseFilterForm(request.GET or None)

    if filter_form.is_valid():
        course_type = filter_form.cleaned_data.get('course_type')
        department = filter_form.cleaned_data.get('department')
        semester = filter_form.cleaned_data.get('semester')

        if course_type or department or semester:
            if course_type:
                courses = courses.filter(course_type=course_type)
            if department:
                courses = courses.filter(department=department)
            if semester:
                courses = courses.filter(semester=semester)

    if request.method == 'POST':
        form = BatchForm(request.POST)

        if form.is_valid():
            year = form.cleaned_data['year']
            part = form.cleaned_data['part']

            if courses.exists():
                for course in courses:
                    batch, created = Batch.objects.get_or_create(
                        course=course, year=year, part=part
                    )

                messages.success(request, "Batch created successfully!")
                return redirect('view_batches')  # Redirect to view batches
            else:
                messages.error(request, "No courses found for the given selection.")

    else:
        form = BatchForm()

    return render(request, 'admin/create_batch.html', {
        'form': form,
        'filter_form': filter_form,
        'courses': courses
    })




def edit_batch(request, batch_id):
    """Edit batch status (only status can be changed)."""
    batch = get_object_or_404(Batch, id=batch_id)  
    course = batch.course  # Get the single related course

    if request.method == 'POST':
        status_value = request.POST.get('status')  # Get status from form
        batch.status = status_value == "True"  # Convert string to boolean
        batch.save()
        return redirect('admin/view_batches')  # Redirect after successful update

    return render(request, 'admin/edit_batch.html', {
        'batch': batch,
        'course': course  # Pass the single course
    })


def delete_batch(request, batch_id):
    """Delete a batch."""
    batch = get_object_or_404(Batch, id=batch_id)
    batch.delete()
    return redirect('admin/view_batches')  # Redirect to the batches page after deletion


def first_sem_allotment(request):
    if CourseAllotment.objects.exists():  # If any allotments are found
        return render(request, 'admin/first_sem_allotment.html', {'already_allocated': True})

    if request.method == 'POST':
        try:
            allocate_courses()
            messages.success(request, "Course allotment successful!")
            CoursePreference.objects.all().delete()
            return redirect('view_allotments')
        except Exception as e:
            messages.error(request, f"An error occurred during allotment: {e}")

    return render(request, 'admin/first_sem_allotment.html', {'page_name': 'First Semester Allotment'})


from django.shortcuts import render
from .models import CourseAllotment

def view_allotments(request):
    allotments = CourseAllotment.objects.all()

    student_allotments = {}
    for allotment in allotments:
        student = allotment.student
        if student not in student_allotments:
            student_allotments[student] = {}
        
        paper_no = allotment.paper_no  # Get the paper number from the allotment
        student_allotments[student][f'paper{paper_no}'] = allotment.batch.course.course_name

    allotment_data = []
    for student, papers in student_allotments.items():
        allotment_data.append({
            'admission_number': student.admission_number,
            'name': student.name,
            'department': student.department.name,
            'pathway': student.pathway.name,
            'paper1': papers.get('paper1'),
            'paper2': papers.get('paper2'),
            'paper3': papers.get('paper3'),
            'paper4': papers.get('paper4'),
        })

    return render(request, 'admin/view_allotments.html', {'allotment_data': allotment_data, 'page_name': 'View Allotments'})


@login_required
def view_student_allotment(request):
    try:
        student = request.user.student  # Fetch student linked to the logged-in user
    except AttributeError:
        return render(request, 'error.html', {'message': 'Student profile not found'})

    # Fetch all allotments for the student
    allotments = CourseAllotment.objects.filter(student=student)

    if not allotments.exists():
        return render(request, 'error.html', {'message': 'No allotment records found'})

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
        'allotted_courses': allotted_courses
    })