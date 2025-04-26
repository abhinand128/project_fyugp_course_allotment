from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from datetime import date

class Department(models.Model):
    name = models.CharField(max_length=100)
    isMajor = models.BooleanField(default=False)

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

    admission_number = models.CharField(
        max_length=15, 
        unique=True,
        validators=[RegexValidator(r'^[A-Za-z0-9]+$', 'Only alphanumeric characters are allowed.')]
    )
    name = models.CharField(max_length=100)
    dob = models.DateField()
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=15, 
        unique=True,
        validators=[RegexValidator(r'^[0-9]+$', 'Only digits are allowed.')]
    )
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    admission_category = models.CharField(max_length=20, choices=CATEGORY, default='General')
    admission_year = models.PositiveIntegerField(
        validators=[
            MinValueValidator(2000),
            MaxValueValidator(date.today().year)
        ]
    )
    pathway = models.ForeignKey(Pathway, on_delete=models.CASCADE)
    current_sem = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(8)
        ]
    )
    normalized_marks = models.IntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1000)
        ]
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    first_sem_marks = models.FloatField(
        null=True, 
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1000)
        ]
    )
    status = models.IntegerField(choices=[(0, 'Inactive'), (1, 'Active')], default=1)

    def clean(self):
        if self.dob and self.dob > date.today():
            raise ValidationError("Date of birth cannot be in the future")
        
        if self.admission_year and self.admission_year > date.today().year:
            raise ValidationError("Admission year cannot be in the future")

    def save(self, *args, **kwargs):
        """Auto-create a Django user when saving a new student."""
        self.clean()
        
        username = self.admission_number
        password = self.dob.strftime('%d/%m/%y')

        if not self.user:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username, 
                    password=password, 
                    email=self.email
                )
                self.user = user

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.admission_number} - {self.name}"

class Course_type(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Course(models.Model):
    course_code = models.CharField(
        max_length=15, 
        unique=True,
        validators=[RegexValidator(r'^[A-Za-z0-9]+$', 'Only alphanumeric characters are allowed.')]
    )
    course_name = models.CharField(max_length=100)
    course_type = models.ForeignKey(Course_type, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    semester = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(8)
        ]
    )
    seat_limit = models.IntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['course_code', 'course_name'], 
                name='unique_course_code_name'
            )
        ]

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"

class Batch(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    year = models.CharField(
        max_length=9,
        validators=[RegexValidator(
            r'^\d{4}-\d{4}$',
            'Year must be in format YYYY-YYYY'
        )]
    )
    part = models.IntegerField(choices=[(1, 'Part 1'), (2, 'Part 2')])
    status = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'year', 'part'], 
                name='unique_course_year_part'
            )
        ]

    def clean(self):
        try:
            start_year, end_year = map(int, self.year.split('-'))
            if end_year != start_year + 1:
                raise ValidationError("Year range should be consecutive (e.g., 2023-2024)")
        except (ValueError, AttributeError):
            raise ValidationError("Invalid year format. Use YYYY-YYYY")

    def __str__(self):
        return f"{self.course.course_name} - Year: {self.year}, Part: {self.part}"

class CoursePreference(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    preference_number = models.PositiveIntegerField()
    paper_no = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'batch', 'paper_no'],
                name='unique_student_batch_paper'
            ),
            models.UniqueConstraint(
                fields=['student', 'preference_number', 'paper_no'],
                name='unique_student_preference_paper'
            )
        ]

    def clean(self):
        if CoursePreference.objects.filter(
            student=self.student,
            preference_number=self.preference_number,
            paper_no=self.paper_no
        ).exclude(pk=self.pk).exists():
            raise ValidationError(
                "A preference with this number already exists for this student and paper"
            )

    def __str__(self):
        return f"{self.student} - {self.batch} (Pref: {self.preference_number}, Paper: {self.paper_no})"

class CourseAllotment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    paper_no = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'paper_no'],
                name='unique_student_paper_allotment'
            )
        ]

    def __str__(self):
        return f"{self.student.name} - {self.batch} - Paper {self.paper_no}"

class HOD(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        validators=[RegexValidator(r'^[0-9]+$', 'Only digits are allowed.')]
    )
    department = models.ForeignKey('Department', on_delete=models.CASCADE)

    def clean(self):
        if self.phone_number and len(self.phone_number) < 10:
            raise ValidationError("Phone number must be at least 10 digits")

    def save(self, *args, **kwargs):
        self.clean()
        
        if not self.user:
            email_prefix = self.email.split('@')[0]
            username = email_prefix.lower()

            counter = 1
            original_username = username
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1

            password = f"{original_username}@123"
            user = User.objects.create_user(
                username=username, 
                password=password, 
                email=self.email
            )
            self.user = user

        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name

class AllocationSettings(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    strength = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(1)]
    )
    department_quota_percentage = models.PositiveIntegerField(
        default=20,
        help_text="Percentage of department strength to allocate as MDC quota",
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    general_quota_percentage = models.PositiveIntegerField(
        default=60,
        help_text="Percentage for General category",
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    sc_st_quota_percentage = models.PositiveIntegerField(
        default=20,
        help_text="Percentage for SC/ST category",
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    other_quota_percentage = models.PositiveIntegerField(
        default=20,
        help_text="Percentage for EWS/Sports/Management category",
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    class Meta:
        verbose_name = "Allocation Setting"
        verbose_name_plural = "Allocation Settings"
        constraints = [
            models.UniqueConstraint(
                fields=['department'],
                name='unique_department_allocation'
            )
        ]

    def clean(self):
        if (self.general_quota_percentage + 
            self.sc_st_quota_percentage + 
            self.other_quota_percentage) != 100:
            raise ValidationError(
                "The sum of General, SC/ST, and Other quotas must equal 100%"
            )

    def calculate_total_quota(self):
        return max(1, round(self.strength * self.department_quota_percentage / 100))

    def calculate_general_quota(self):
        return max(1, round(self.calculate_total_quota() * self.general_quota_percentage / 100))

    def calculate_sc_st_quota(self):
        return max(1, round(self.calculate_total_quota() * self.sc_st_quota_percentage / 100))

    def calculate_other_quota(self):
        return max(1, round(self.calculate_total_quota() * self.other_quota_percentage / 100))

    def __str__(self):
        return f"{self.department} Settings"