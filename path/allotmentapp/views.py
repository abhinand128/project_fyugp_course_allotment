from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .models import Student,Course,CoursePreference
from .forms import StudentForm,CourseFilterForm,CourseSelectionForm,CourseForm

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


def course_selection(request):
    student = request.user.student

    try:
        student = request.user.student  
        print("Student Object:", student)
    except student.DoesNotExist:
        print("No student found for admission number:", request.user.username)
        return render(request, 'error.html', {'message': 'Student not found'})
    
    # Check if preferences already exist for the student
    existing_preferences = CoursePreference.objects.filter(student=student)
    if existing_preferences.exists():
        return render(request, 'course_selection.html', {'view_preferences': True, 'already_submitted': True})

    if request.method == 'POST':
        form = CourseSelectionForm(request.POST, student=student)
        if form.is_valid():
            preferences = []

            # Handle DSC 1 separately (since it has no "_option_" in its name)
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
                    if field_name.startswith("dsc_2"):
                        paper_no = 2
                    elif field_name.startswith("dsc_3"):
                        paper_no = 3
                    elif field_name.startswith("mdc"):
                        paper_no = 4
                    else:
                        continue  

                    # Create CoursePreference object
                    preferences.append(
                        CoursePreference(
                            student=student,
                            batch=batch,
                            preference_number=preference_number,
                            paper_no=paper_no
                        )
                    )

            # Bulk create to optimize DB operations
            CoursePreference.objects.bulk_create(preferences)

            return redirect('view_preferences')  # Redirect after successful submission

    else:
        form = CourseSelectionForm(student=student)

    return render(request, 'student/course_selection.html', {'form': form, 'already_submitted': False})


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