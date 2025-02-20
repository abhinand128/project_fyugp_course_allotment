from django import forms
from .models import Student,Course,Course_type,Department,Batch,CourseAllotment

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['admission_number', 'name', 'dob', 'email', 'department', 'admission_category', 'pathway', 'current_sem', 'normalized_marks']


class CourseFilterForm(forms.Form):
    course_type = forms.ModelChoiceField(
        queryset=Course_type.objects.all(), 
        required=False, 
        empty_label="Select Course Type", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(), 
        required=False, 
        empty_label="Select Department", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    semester = forms.IntegerField(
        required=False, 
        widget=forms.NumberInput(attrs={'placeholder': 'Enter Semester', 'class': 'form-control'})
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
            print("Student passed to form:", student)
            print("Student Department:", student.department)
            print("Student Pathway:", student.pathway)

            # Fetch Semester 1 Course Allotments for this student
            sem1_allotments = CourseAllotment.objects.filter(student=student, batch__course__semester=1)

        # Identify the department of Paper 3 and Paper 1
            paper_3_allotment = sem1_allotments.filter(paper_no=3).first()
            paper_1_allotment = sem1_allotments.filter(paper_no=1).first()

            paper_3_department = paper_3_allotment.batch.course.department if paper_3_allotment else None
            paper_1_department = paper_1_allotment.batch.course.department if paper_1_allotment else None

            print("Paper 3 Department:", paper_3_department)
            print("Paper 1 Department:", paper_1_department)
            
            # Fetch only Semester 1 batches
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


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['course_code', 'course_name', 'course_type', 'department', 'semester', 'seat_limit']

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['year', 'part']  # Removed 'course' as it's auto-assigned

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get('year')
        part = cleaned_data.get('part')

        if not year or not part:
            raise forms.ValidationError("Year and Part are required!")

        return cleaned_data

   

class BatchFilterForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.all(), required=False)
    year = forms.CharField(max_length=9, required=False)
    part = forms.ChoiceField(choices=[(1, 'Part 1'), (2, 'Part 2')], required=False)
