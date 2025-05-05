from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator,FileExtensionValidator
from datetime import date, datetime
from .models import (
    Student, Course, Course_type, Department, Batch, 
    CourseAllotment, AllocationSettings, HOD
)

class StudentForm(forms.ModelForm):
    dob = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        validators=[lambda value: ValidationError("Date of birth cannot be in the future") 
                    if value > date.today() else None]
    )
    
    admission_year = forms.IntegerField(
        validators=[
            MinValueValidator(2000, message="Admission year must be 2000 or later"),
            MaxValueValidator(
                lambda: date.today().year,
                message="Admission year cannot be in the future"
            )
        ]
    )

    class Meta:
        model = Student
        fields = [
            'admission_number', 'name', 'dob', 'email', 'department', 
            'admission_category', 'pathway', 'current_sem', 'normalized_marks'
        ]
        widgets = {
            'admission_number': forms.TextInput(attrs={
                'pattern': '[A-Za-z0-9]+',
                'title': 'Only alphanumeric characters allowed'
            }),
            'normalized_marks': forms.NumberInput(attrs={
                'min': 0,
                'max': 100
            }),
            'current_sem': forms.NumberInput(attrs={
                'min': 1,
                'max': 8
            })
        }

class CourseFilterForm(forms.Form):
    SEMESTER_CHOICES = [("", "Select Semester")] + [(i, f"Semester {i}") for i in range(1, 9)]
    COURSE_TYPE_CHOICES = [("", "All Course Types"), ("DSC", "DSC"), ("MDC", "MDC")]

    course_type = forms.ChoiceField(
        choices=COURSE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Course Type"
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Department"
    )

    semester = forms.ChoiceField(
        choices=SEMESTER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Semester"
    )

class BaseCourseSelectionForm(forms.Form):
    """Base class with common functionality for semester selection forms"""
    
    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        
        if self.student:
            self.setup_fields()
            self.order_fields(self.get_field_order())

    def setup_fields(self):
        """Setup form fields based on student pathway"""
        raise NotImplementedError("Subclasses must implement this method")

    def get_field_order(self):
        """Define the order of fields in the form"""
        raise NotImplementedError("Subclasses must implement this method")

    @staticmethod
    def batch_label(batch):
        """Standard label format for batch choices"""
        return f"{batch.course.department.name} - {batch.course.course_name}"

    def create_batch_field(self, name, queryset, label='', required=True):
        """Helper method to create consistent batch selection fields"""
        self.fields[name] = forms.ModelChoiceField(
            queryset=queryset,
            required=required,
            label=label,
            empty_label="Select an option",
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        self.fields[name].label_from_instance = self.batch_label

class CourseSelectionFormSem1(BaseCourseSelectionForm):
    def setup_fields(self):
        # Fetch Semester 1 batches
        dsc_batches = Batch.objects.select_related('course', 'course__department').filter(
            course__course_type__name__startswith='DSC',
            course__semester=1
        )
        mdc_batches = Batch.objects.select_related('course', 'course__department').filter(
            course__course_type__name__startswith='MDC',
            course__semester=1
        )

        # Pathway-specific filtering
        if self.student.pathway.name == "Single Major":
            dsc_1_batches = dsc_batches.filter(course__department=self.student.department)
            dsc_2_batches = dsc_batches.exclude(course__department=self.student.department)
            dsc_3_batches = dsc_batches.exclude(course__department=self.student.department)
            mdc_filtered_batches = mdc_batches.exclude(course__department=self.student.department)
        elif self.student.pathway.name == "Double Major":
            dsc_1_batches = dsc_batches.filter(course__department=self.student.department)
            dsc_2_batches = dsc_batches.filter(course__department=self.student.department)
            dsc_3_batches = dsc_batches.exclude(course__department=self.student.department)
            mdc_filtered_batches = mdc_batches.exclude(course__department=self.student.department)
        else:  # Single/Double Minor
            dsc_1_batches = dsc_batches.filter(course__department=self.student.department)
            dsc_2_batches = dsc_batches.exclude(course__department=self.student.department)
            dsc_3_batches = dsc_batches.exclude(course__department=self.student.department)
            mdc_filtered_batches = mdc_batches.exclude(course__department=self.student.department)

        # Create fields
        self.create_batch_field('dsc_1', dsc_1_batches, 'DSC 1')
        
        # DSC 2 options
        option_count = dsc_2_batches.count() if self.student.pathway.name == "Double Major" else 4
        for i in range(1, option_count):
            self.create_batch_field(f'dsc_2_option_{i}', dsc_2_batches, f'Option {i}')

        # DSC 3 options
        for i in range(1, 4):
            self.create_batch_field(f'dsc_3_option_{i}', dsc_3_batches, f'Option {i}')

        # MDC options
        for i in range(1, mdc_filtered_batches.count() + 1):
            self.create_batch_field(f'mdc_option_{i}', mdc_filtered_batches, f'Option {i}')

    def get_field_order(self):
        return ['dsc_1'] + \
               [f'dsc_2_option_{i}' for i in range(1, 4)] + \
               [f'dsc_3_option_{i}' for i in range(1, 4)] + \
               [f'mdc_option_{i}' for i in range(1, 6)]  # Assuming max 5 MDC options

class CourseSelectionFormSem2(BaseCourseSelectionForm):
    def setup_fields(self):
        # Get previous semester allotments
        sem1_allotments = CourseAllotment.objects.filter(
            student=self.student, 
            batch__course__semester=1
        )
        paper_3_dept = sem1_allotments.filter(paper_no=3).first().batch.course.department if sem1_allotments.filter(paper_no=3).exists() else None
        paper_1_dept = sem1_allotments.filter(paper_no=1).first().batch.course.department if sem1_allotments.filter(paper_no=1).exists() else None

        # Fetch Semester 2 batches
        dsc_batches = Batch.objects.select_related('course', 'course__department').filter(
            course__course_type__name__startswith='DSC',
            course__semester=2
        )
        mdc_batches = Batch.objects.select_related('course', 'course__department').filter(
            course__course_type__name__startswith='MDC',
            course__semester=2
        )

        # Pathway-specific filtering
        if self.student.pathway.name == "Double Major":
            dsc_1_batches = dsc_batches.filter(course__department=paper_3_dept)
            dsc_2_batches = dsc_batches.filter(course__department=paper_3_dept)
            dsc_3_batches = dsc_batches.filter(course__department=paper_1_dept)
        else:
            dsc_1_batches = dsc_batches.filter(course__department=self.student.department)
            dsc_2_batches = dsc_batches.exclude(course__department=self.student.department)
            dsc_3_batches = dsc_batches.exclude(course__department=self.student.department)
        
        mdc_filtered_batches = mdc_batches.exclude(course__department=self.student.department)

        # Create fields
        self.create_batch_field('dsc_1', dsc_1_batches, 'DSC 1')
        
        # DSC 2 options
        option_count = dsc_2_batches.count() if self.student.pathway.name == "Double Major" else 3
        for i in range(1, option_count + 1):
            self.create_batch_field(f'dsc_2_option_{i}', dsc_2_batches, f'Option {i}')

        # DSC 3 options
        option_count = dsc_3_batches.count() if self.student.pathway.name == "Double Major" else 3
        for i in range(1, option_count + 1):
            self.create_batch_field(f'dsc_3_option_{i}', dsc_3_batches, f'Option {i}')

        # MDC options
        for i in range(1, mdc_filtered_batches.count() + 1):
            self.create_batch_field(f'mdc_option_{i}', mdc_filtered_batches, f'Option {i}')

    def get_field_order(self):
        return ['dsc_1'] + \
               [f'dsc_2_option_{i}' for i in range(1, 4)] + \
               [f'dsc_3_option_{i}' for i in range(1, 4)] + \
               [f'mdc_option_{i}' for i in range(1, 6)]

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_code', 'course_name', 'course_type', 'department', 'semester', 'seat_limit']
        widgets = {
            'course_code': forms.TextInput(attrs={
                'pattern': '[A-Za-z0-9]+',
                'title': 'Only alphanumeric characters allowed'
            }),
            'semester': forms.NumberInput(attrs={
                'min': 1,
                'max': 8
            }),
            'seat_limit': forms.NumberInput(attrs={
                'min': 1
            })
        }

class BatchForm(forms.ModelForm):
    year = forms.ChoiceField(
        choices=lambda: [('', 'Select Year')] + [
            (f"{year}-{year+1}", f"{year}-{year+1}") 
            for year in range(datetime.now().year, datetime.now().year + 10)
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    part = forms.ChoiceField(
        choices=[('', 'Select Part'), ('1', 'Part 1'), ('2', 'Part 2')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Batch
        fields = ['year', 'part']

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('year') or not cleaned_data.get('part'):
            raise ValidationError("Both year and part are required")
        return cleaned_data

class BatchFilterForm(forms.Form):
    year = forms.ChoiceField(
        choices=lambda: [('', 'Select Year')] + [
            (year, year) for year in 
            Batch.objects.values_list('year', flat=True).distinct()
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    part = forms.ChoiceField(
        choices=[('', 'Select Part'), ('1', 'Part 1'), ('2', 'Part 2')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class StudentRegistrationForm(forms.ModelForm):
    dob = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        validators=[lambda value: ValidationError("Date cannot be in future") 
                    if value > date.today() else None]
    )
    
    password = forms.CharField(
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = Student
        fields = [
            'admission_number', 'name', 'dob', 'email', 'phone_number', 'department',
            'admission_category', 'admission_year', 'pathway', 'normalized_marks', 'password'
        ]
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'pattern': '[0-9]+',
                'minlength': '10',
                'maxlength': '15'
            }),
            'normalized_marks': forms.NumberInput(attrs={
                'min': 0,
                'max': 100
            }),
            'admission_year': forms.NumberInput(attrs={
                'min': 2000,
                'max': date.today().year
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        if 'dob' in cleaned_data:
            cleaned_data['password'] = cleaned_data['dob'].strftime('%d/%m/%y')
        return cleaned_data

class BulkStudentUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV File",
        widget=forms.FileInput(attrs={'accept': '.csv'}),
        validators=[FileExtensionValidator(allowed_extensions=['csv'])]
    )

class StudentEditForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'admission_number', 'name', 'dob', 'email', 'phone_number', 'department',
            'admission_category', 'pathway', 'current_sem', 'first_sem_marks', 
            'normalized_marks', 'status'
        ]
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'phone_number': forms.TextInput(attrs={
                'pattern': '[0-9]+',
                'minlength': '10',
                'maxlength': '15'
            }),
            'current_sem': forms.NumberInput(attrs={
                'min': 1,
                'max': 8
            }),
            'first_sem_marks': forms.NumberInput(attrs={
                'min': 0,
                'max': 100,
                'step': '0.01'
            }),
            'normalized_marks': forms.NumberInput(attrs={
                'min': 0,
                'max': 100
            })
        }

class HODForm(forms.ModelForm):
    class Meta:
        model = HOD
        fields = ['full_name', 'email', 'phone_number', 'department']
        widgets = {
            'email': forms.EmailInput(attrs={'required': True}),
            'phone_number': forms.TextInput(attrs={
                'pattern': '[0-9]+',
                'minlength': '10',
                'maxlength': '15'
            })
        }

class HODEditForm(HODForm):
    class Meta(HODForm.Meta):
        pass  # Inherits all from HODForm but can be customized if needed

class StudentAllotmentFilterForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(), 
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    semester = forms.ChoiceField(
        choices=[("", "Select Semester")] + [(i, f"Semester {i}") for i in range(1, 9)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    admission_year = forms.ChoiceField(
        choices=lambda: [("", "Select Year")] + [
            (str(year), str(year)) for year in 
            Student.objects.order_by('admission_year')
                          .values_list('admission_year', flat=True)
                          .distinct()
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class AllocationSettingsForm(forms.ModelForm):
    class Meta:
        model = AllocationSettings
        fields = '__all__'
        widgets = {
            'strength': forms.NumberInput(attrs={'min': 1}),
            'department_quota_percentage': forms.NumberInput(attrs={
                'min': 1,
                'max': 100
            }),
            'general_quota_percentage': forms.NumberInput(attrs={
                'min': 1,
                'max': 100
            }),
            'sc_st_quota_percentage': forms.NumberInput(attrs={
                'min': 1,
                'max': 100
            }),
            'other_quota_percentage': forms.NumberInput(attrs={
                'min': 1,
                'max': 100
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['department'].disabled = True
        else:
            self.fields['department'].queryset = Department.objects.exclude(
                allocationsettings__isnull=False
            )

    def clean(self):
        cleaned_data = super().clean()
        quotas = [
            cleaned_data.get('general_quota_percentage', 0),
            cleaned_data.get('sc_st_quota_percentage', 0),
            cleaned_data.get('other_quota_percentage', 0)
        ]
        if sum(quotas) != 100:
            raise ValidationError("Quota percentages must sum to 100%")
        return cleaned_data