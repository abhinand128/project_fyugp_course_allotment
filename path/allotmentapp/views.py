from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
#from .models import Student  # Assuming you have a Student model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Student
from .forms import StudentForm



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
        # Get the submitted admission number and password
        admission_number = request.POST.get('admission_number')
        password = request.POST.get('password')

        # Check if user exists with the given admission number (username)
        user = authenticate(request, username=admission_number, password=password)

        if user is not None:  # Authentication successful
            login(request, user)

            # If it's the first time login (password change required), redirect to change password page
            if user.first_login:  # Assuming you added this field to track first login
                return redirect('change_password')

            return redirect('student_dashboard')  # Redirect to the student dashboard or home page
        else:
            messages.error(request, 'Invalid admission number or password.')
            #return redirect('login/student_login')
    
    return render(request, 'login/student_login.html')

def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            # Set first_login to False after password change
            request.user.first_login = False
            request.user.save()
            messages.success(request, 'Your password was successfully updated!')
            return redirect('student_dashboard')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'change_password.html', {'form': form})

def student_dashboard(request):
    return render(request, 'student_dashboard.html')

def admin_dashboard(request):
    # You can pass additional context like page_name if needed
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
