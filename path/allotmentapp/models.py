from django.db import models
from django.contrib.auth.models import User

class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Pathway(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Student(models.Model):
    CATEGORY = [
        ('General', 'General'),
        ('SC', 'Scheduled Caste'),
        ('ST', 'Scheduled Tribe'),
        ('PWD', 'Persons with Disability'),
        ('EWS', 'Economically Weaker Section'),
        ('Sports', 'Sports Quota'),
        ('Management', 'Management Quota'),
    ]

    admission_number = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=100)
    dob = models.DateField()
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True,default=999999999)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    admission_category = models.CharField(max_length=20, choices=CATEGORY, default='General')
    admission_year=models.PositiveIntegerField(default=2022)
    pathway = models.ForeignKey(Pathway, on_delete=models.CASCADE)
    current_sem = models.PositiveIntegerField(default=1)
    normalized_marks = models.IntegerField()
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    first_sem_marks = models.FloatField(null=True, blank=True)
    status = models.IntegerField(choices=[(0, 'Inactive'), (1, 'Active')], default=1)

    def save(self, *args, **kwargs):
        """Auto-create a Django user when saving a new student."""
        username = self.admission_number  # Ensure username is always set
        password = self.dob.strftime('%d/%m/%y')  # Format DOB as DD/MM/YY

        if not self.user:
        # Ensure username is unique before creating the user
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(username=username, password=password, email=self.email)
                self.user = user

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.admission_number} - {self.name}"

class Course_type(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Course(models.Model):
    course_code = models.CharField(max_length=15, unique=True)
    course_name = models.CharField(max_length=100)
    course_type = models.ForeignKey(Course_type, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    semester=models.PositiveIntegerField(default=1)
    seat_limit = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['course_code', 'course_name'], name='unique_course_code_name')
        ]

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"

class Batch(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    year = models.CharField(max_length=9)
    part = models.IntegerField(choices=[(1, 'Part 1'), (2, 'Part 2')])  # Part 1 for odd sem, Part 2 for even sem
    status = models.BooleanField(default=True)  # Assuming status is a boolean field

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['course', 'year', 'part'], name='unique_course_year_part')
        ]
        


    def __str__(self):
        return f"{self.course.course_name} - Year: {self.year}, Part: {self.part}"


class CoursePreference(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)  # Allow null values temporarily
    preference_number = models.PositiveIntegerField() 
    paper_no = models.PositiveIntegerField(default=1)
    
class CourseAllotment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    paper_no = models.PositiveIntegerField(default=1)  # Add paper_no field

    def __str__(self):
        return f"{self.student.name} - {self.batch} - Paper {self.paper_no}"  # Include paper_no in __str__

class HOD(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)  
    full_name = models.CharField(max_length=100)  
    email = models.EmailField(unique=True)  
    phone_number = models.CharField(max_length=15, blank=True, null=True)  
    department = models.ForeignKey('Department', on_delete=models.CASCADE)  

    def save(self, *args, **kwargs):
        """ Automatically create a User for HOD and set username & password """
        if not self.user:  
            email_prefix = self.email.split('@')[0]  # Extract prefix before '@'
            username = email_prefix.lower()  # Ensure lowercase username

            # Ensure unique username in case of conflicts
            counter = 1
            original_username = username
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1  

            password = f"{original_username}@123"  # Default password

            user = User.objects.create_user(username=username, password=password, email=self.email)
            user.save()

            self.user = user  # Link user to HOD before saving

        super().save(*args, **kwargs)  

    def __str__(self):
        return self.full_name 