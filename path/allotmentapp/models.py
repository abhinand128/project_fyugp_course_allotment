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
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    admission_category = models.CharField(max_length=20, choices=CATEGORY, default='General')
    pathway = models.ForeignKey(Pathway, on_delete=models.CASCADE)
    current_sem = models.PositiveIntegerField(default=1)
    normalized_marks = models.IntegerField()
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    def save(self, *args, **kwargs):
        """Auto-create a Django user when saving a new student."""
        if not self.user:
            username = self.admission_number
            password = self.dob.strftime('%d/%m/%y')  # Format DOB as DD/MM/YY
        
        # Ensure username is unique before creating the user
        if not User.objects.filter(username=username).exists():
            user = User.objects.create_user(username=username, password=password, email=self.email)
            self.user = user
        super().save(*args, **kwargs)

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

    def __str__(self):
        return f"{self.student.name} - {self.batch}"