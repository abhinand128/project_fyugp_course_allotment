from django import forms
from .models import Student,Course,Course_type,Department,Batch,CourseAllotment
from django.core.exceptions import ValidationError
from datetime import datetime

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['admission_number', 'name', 'dob', 'email', 'department', 'admission_category', 'pathway', 'current_sem', 'normalized_marks']


class CourseFilterForm(forms.Form):
    SEMESTER_CHOICES = [("", "Select Semester")] + [(str(i), f"Semester {i}") for i in range(1, 9)]

    COURSE_TYPE_CHOICES = [
        ("", "All Course Types"),
        ("DSC", "DSC"),
        ("MDC", "MDC"),
    ]

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


class CourseSelectionFormSem1(forms.Form):
    def __init__(self, *args, **kwargs):
        student = kwargs.pop('student', None)
        super(CourseSelectionFormSem1, self).__init__(*args, **kwargs)

        if student:
            print("Student passed to form:", student)
            print("Student Department:", student.department)
            print("Student Pathway:", student.pathway)

            
            # Fetch only Semester 1 batches
            dsc_batches = Batch.objects.select_related('course', 'course__department').filter(
                course__course_type__name__startswith='DSC',
                course__semester=1  # Ensuring the course is for Semester 1
            )
            mdc_batches = Batch.objects.select_related('course', 'course__department').filter(
                course__course_type__name__startswith='MDC',
                course__semester=1  # Ensuring the course is for Semester 1
            )

            # Pathway-specific logic
            if student.pathway.name == "Single Major":
                dsc_1_batches = dsc_batches.filter(course__department=student.department)
                dsc_2_batches = dsc_batches.exclude(course__department=student.department)
                dsc_3_batches = dsc_batches.exclude(course__department=student.department)
                mdc_filtered_batches = mdc_batches.exclude(course__department=student.department)

            elif student.pathway.name == "Double Major":
                dsc_1_batches = dsc_batches.filter(course__department=student.department)
                dsc_2_batches = dsc_batches.filter(course__department=student.department)  # Filter by same department
                dsc_3_batches = dsc_batches.exclude(course__department=student.department)
                mdc_filtered_batches = mdc_batches.exclude(course__department=student.department)

            else:  # Single Major with Single/Double Minor
                dsc_1_batches = dsc_batches.filter(course__department=student.department)
                dsc_2_batches = dsc_batches.exclude(course__department=student.department)
                dsc_3_batches = dsc_batches.exclude(course__department=student.department)
                mdc_filtered_batches = mdc_batches.exclude(course__department=student.department)

            # Define field order
            field_order = []

            # Helper function to customize choice labels
            def batch_label(batch):
                return f"{batch.course.department.name} - {batch.course.course_name}"

            # Add form field for DSC 1 (single selection)
            self.fields['dsc_1'] = forms.ModelChoiceField(
                queryset=dsc_1_batches,
                required=True,
                label='',
                empty_label="Select an option",
            )
            self.fields['dsc_1'].label_from_instance = batch_label
            field_order.append('dsc_1')

            # Add DSC 2 options (same for all pathways, but dynamic in Double Major)
            if student.pathway.name == "Double Major":
                dsc_2_count = dsc_2_batches.count()
                for i in range(1, dsc_2_count):
                    field_name = f'dsc_2_option_{i}'
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=dsc_2_batches,
                        required=True,
                        label=f'Option {i}',
                        empty_label="Select an option",
                    )
                    self.fields[field_name].label_from_instance = batch_label
                    field_order.append(field_name)
            else:
                # For other pathways, just use all available DSC 2 batches (without department filtering)
                for i in range(1, 4):
                    field_name = f'dsc_2_option_{i}'
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=dsc_2_batches,
                        required=True,
                        label=f'Option {i}',
                        empty_label="Select an option",
                    )
                    self.fields[field_name].label_from_instance = batch_label
                    field_order.append(field_name)

            # Add DSC 3 options (same for all pathways)
            for i in range(1, 4):
                field_name = f'dsc_3_option_{i}'
                self.fields[field_name] = forms.ModelChoiceField(
                    queryset=dsc_3_batches,
                    required=True,
                    label=f'Option {i}',
                    empty_label="Select an option",
                )
                self.fields[field_name].label_from_instance = batch_label
                field_order.append(field_name)

            # Dynamically generate MDC options based on available courses
            mdc_count = mdc_filtered_batches.count()
            for i in range(1, mdc_count + 1):
                field_name = f'mdc_option_{i}'
                self.fields[field_name] = forms.ModelChoiceField(
                    queryset=mdc_filtered_batches,
                    required=True,
                    label=f'Option {i}',
                    empty_label="Select an option",
                )
                self.fields[field_name].label_from_instance = batch_label
                field_order.append(field_name)

            # Ensure the form fields appear in the specified order
            self.order_fields(field_order)

        # Debug: Print final field order
        print("Final Field Order:", list(self.fields.keys()))

class CourseSelectionFormSem2(forms.Form):
    def __init__(self, *args, **kwargs):
        student = kwargs.pop('student', None)
        super(CourseSelectionFormSem2, self).__init__(*args, **kwargs)

        if student:

            # Fetch Semester 1 Course Allotments for this student
            sem1_allotments = CourseAllotment.objects.filter(student=student, batch__course__semester=1)

            # Identify the department of Paper 3 and Paper 1
            paper_3_allotment = sem1_allotments.filter(paper_no=3).first()
            paper_1_allotment = sem1_allotments.filter(paper_no=1).first()

            paper_3_department = paper_3_allotment.batch.course.department if paper_3_allotment else None
            paper_1_department = paper_1_allotment.batch.course.department if paper_1_allotment else None


            # Fetch only Semester 2 batches
            dsc_batches = Batch.objects.select_related('course', 'course__department').filter(
                course__course_type__name__startswith='DSC',
                course__semester=2  # Ensuring the course is for Semester 2
            )
            mdc_batches = Batch.objects.select_related('course', 'course__department').filter(
                course__course_type__name__startswith='MDC',
                course__semester=2  # Ensuring the course is for Semester 2
            )

            # Pathway-specific logic
            if student.pathway.name == "Single Major":
                dsc_1_batches = dsc_batches.filter(course__department=student.department)
                dsc_2_batches = dsc_batches.exclude(course__department=student.department)
                dsc_3_batches = dsc_batches.exclude(course__department=student.department)
                mdc_filtered_batches = mdc_batches.exclude(course__department=student.department)

            elif student.pathway.name == "Double Major":
                dsc_1_batches = dsc_batches.filter(course__department=paper_3_department)
                dsc_2_batches = dsc_batches.filter(course__department=paper_3_department)  # Filter by same department
                dsc_3_batches = dsc_batches.filter(course__department=paper_1_department)
                mdc_filtered_batches = mdc_batches.exclude(course__department=student.department)

            else:  # Single Major with Single/Double Minor
                dsc_1_batches = dsc_batches.filter(course__department=student.department)
                dsc_2_batches = dsc_batches.exclude(course__department=student.department)
                dsc_3_batches = dsc_batches.exclude(course__department=student.department)
                mdc_filtered_batches = mdc_batches.exclude(course__department=student.department)

            # Define field order
            field_order = []

            # Helper function to customize choice labels
            def batch_label(batch):
                return f"{batch.course.department.name} - {batch.course.course_name}"

            # Add form field for DSC 1 (single selection)
            self.fields['dsc_1'] = forms.ModelChoiceField(
                queryset=dsc_1_batches,
                required=True,
                label='',
                empty_label="Select an option",
            )
            self.fields['dsc_1'].label_from_instance = batch_label
            field_order.append('dsc_1')

            # Add DSC 2 options (same for all pathways, but dynamic in Double Major)
            if student.pathway.name == "Double Major":
                dsc_2_count = dsc_2_batches.count()
                for i in range(1, dsc_2_count):  # Dynamically set number of DSC 2 fields
                    field_name = f'dsc_2_option_{i}'
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=dsc_2_batches,
                        required=True,
                        label=f'Option {i}',
                        empty_label="Select an option",
                    )
                    self.fields[field_name].label_from_instance = batch_label
                    field_order.append(field_name)
            else:
                # For other pathways, fixed 3 options for DSC 2
                for i in range(1, 4):
                    field_name = f'dsc_2_option_{i}'
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=dsc_2_batches,
                        required=True,
                        label=f'Option {i}',
                        empty_label="Select an option",
                    )
                    self.fields[field_name].label_from_instance = batch_label
                    field_order.append(field_name)

            # Add DSC 3 options (Dynamic for Double Major)
            if student.pathway.name == "Double Major":
                dsc_3_count = dsc_3_batches.count()
                for i in range(1, dsc_3_count + 1):  # Dynamically set number of DSC 3 fields
                    field_name = f'dsc_3_option_{i}'
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=dsc_3_batches,
                        required=True,
                        label=f'Option {i}',
                        empty_label="Select an option",
                    )
                    self.fields[field_name].label_from_instance = batch_label
                    field_order.append(field_name)
            else:
                # For other pathways, fixed 3 options for DSC 3
                for i in range(1, 4):
                    field_name = f'dsc_3_option_{i}'
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=dsc_3_batches,
                        required=True,
                        label=f'Option {i}',
                        empty_label="Select an option",
                    )
                    self.fields[field_name].label_from_instance = batch_label
                    field_order.append(field_name)

            # Dynamically generate MDC options based on available courses
            mdc_count = mdc_filtered_batches.count()
            for i in range(1, mdc_count + 1):
                field_name = f'mdc_option_{i}'
                self.fields[field_name] = forms.ModelChoiceField(
                    queryset=mdc_filtered_batches,
                    required=True,
                    label=f'Option {i}',
                    empty_label="Select an option",
                )
                self.fields[field_name].label_from_instance = batch_label
                field_order.append(field_name)

            # Ensure the form fields appear in the specified order
            self.order_fields(field_order)

        # Debug: Print final field order
        print("Final Field Order:", list(self.fields.keys()))



from django import forms
class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_code', 'course_name', 'course_type', 'department', 'semester', 'seat_limit']


class BatchForm(forms.ModelForm):
    # Generate year choices dynamically (from current year onwards)
    def get_year_choices():
        current_year = datetime.now().year
        return [(f"{year}-{year+1}", f"{year}-{year+1}") for year in range(current_year, current_year + 10)]

    year = forms.ChoiceField(
        choices=[('', 'Select Year')] + get_year_choices(),
        label="Academic Year",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    part = forms.ChoiceField(
        choices=[('', 'Select Part'), ('1', 'Part 1'), ('2', 'Part 2')],
        label="Batch Part",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Batch
        fields = ['year', 'part']

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get('year')
        part = cleaned_data.get('part')

        if not year or not part:
            raise forms.ValidationError("Year and Part are required!")

        return cleaned_data


   

class BatchFilterForm(forms.Form):
    year = forms.ChoiceField(
        required=False,
        label="Academic Year",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    part = forms.ChoiceField(
        choices=[('', 'Select Part'), ('1', 'Part 1'), ('2', 'Part 2')],
        required=False,
        label="Batch Part",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super(BatchFilterForm, self).__init__(*args, **kwargs)
        # Dynamically populate year choices from the database
        years = Batch.objects.values_list('year', flat=True).distinct()
        self.fields['year'].choices = [('', 'Select Year')] + [(year, year) for year in years]

from django import forms
from .models import Student

class StudentRegistrationForm(forms.ModelForm):
    dob = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Date of Birth"
    )
    password = forms.CharField(
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
        label="Password (Auto-filled from DOB)",
        required=False
    )

    class Meta:
        model = Student
        fields = ['admission_number', 'name', 'dob', 'email', 'phone_number', 'department', 
                  'admission_category', 'admission_year', 'pathway',
                  'normalized_marks', 'password']
        
        widgets = {
            'admission_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Admission Number'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'admission_category': forms.Select(attrs={'class': 'form-select'}),
            'admission_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Admission Year'}),
            'pathway': forms.Select(attrs={'class': 'form-select'}),
            
        }

    def clean(self):
        cleaned_data = super().clean()
        dob = cleaned_data.get('dob')

        if dob:
            # Auto-fill password field in the form (does not store in DB)
            formatted_password = dob.strftime('%d/%m/%y')  # DD/MM/YY format
            self.initial['password'] = formatted_password  # Set initial value
        
        return cleaned_data

    def save(self, commit=True):
        """Ensure password is stored in the User model if needed."""
        instance = super().save(commit=False)
        
        # If instance has a related user, set password
        if instance.user:
            instance.user.set_password(instance.dob.strftime('%d/%m/%y'))
            instance.user.save()

        if commit:
            instance.save()
        return instance


class BulkStudentUploadForm(forms.Form):
    csv_file = forms.FileField(label="Upload CSV File", help_text="Only .csv files are allowed")


class StudentEditForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['admission_number','name', 'dob', 'email', 'phone_number', 'department', 'admission_category', 
                  'pathway', 'current_sem', 'first_sem_marks', 'normalized_marks', 'status']
        widgets = {
            'dob': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
            'normalized_marks': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter Plus Two Marks'}),
            'first_sem_marks': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}, choices=[(0, 'Inactive'), (1, 'Active')]),
        }
        labels = {
            'normalized_marks': 'Plus Two Marks (Normalized)',
            'first_sem_marks':'First Semester Marks (SGP)'
        }


from django import forms
from .models import HOD

class HODEditForm(forms.ModelForm):
    class Meta:
        model = HOD
        fields = ['full_name', 'email', 'department']


class HODForm(forms.ModelForm):
    class Meta:
        model = HOD
        fields = ['full_name', 'email', 'phone_number', 'department']  # No need for password field
        
        

from datetime import datetime

class StudentAllotmentFilterForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(), required=False, label="Department"
    )

    semester = forms.ChoiceField(
        choices=[("", "Select Semester")] + [(str(i), f"Semester {i}") for i in range(1, 9)], 
        required=False, label="Semester"
    )

    admission_year = forms.ChoiceField(
        choices=[], required=False, label="Admission Year"
    )

    def __init__(self, *args, **kwargs):
            super(StudentAllotmentFilterForm, self).__init__(*args, **kwargs)

    # Fetch distinct admission years from Student model
            years = (
            Student.objects.order_by("admission_year")
            .values_list("admission_year", flat=True)
            .distinct()
            )

            year_choices = [("", "Select Year")] + [(str(y), str(y)) for y in years]
            self.fields["admission_year"].choices = year_choices

          





