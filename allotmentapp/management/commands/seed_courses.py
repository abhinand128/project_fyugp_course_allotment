from allotmentapp.models import Department, Course_type, Course


# Get all department objects


# Get all department objects from your 16 departments
dept_sanskrit = Department.objects.get(name="Sanskrit")
dept_political_science = Department.objects.get(name="Political Science")
dept_zoology = Department.objects.get(name="Zoology")
dept_statistics = Department.objects.get(name="Statistics")
dept_physics = Department.objects.get(name="Physics")
dept_physical_education = Department.objects.get(name="Physical Education")
dept_mathematics = Department.objects.get(name="Mathematics")
dept_malayalam = Department.objects.get(name="Malayalam")
dept_history = Department.objects.get(name="History")
dept_hindi = Department.objects.get(name="Hindi")
dept_english = Department.objects.get(name="English")
dept_economics = Department.objects.get(name="Economics")
dept_computer_science = Department.objects.get(name="Computer Science")
dept_commerce = Department.objects.get(name="Commerce")
dept_polymer_chemistry = Department.objects.get(name="Polymer Chemistry")
dept_plant_science = Department.objects.get(name="Plant Science")

# Note: For Library Science courses, we'll use the most appropriate department
# KU02MDCLIB108 will be mapped to Computer Science or another relevant department

# Get course type objects
dsc5 = Course_type.objects.get(name="DSC5")
dsc6 = Course_type.objects.get(name="DSC6")
mdc = Course_type.objects.get(name="MDC")

# List of courses to insert - format: (course_code, course_name, course_type, department, semester, seat_limit)
# IMPORTANT: All chemistry-related courses map to "Polymer Chemistry" department
courses_to_insert = [
    # ===== DSC 5 COURSES ===== (Seat limit: 60)
    ("KU2DSCBOT106", "Angiosperm Taxonomy and Morphology", dsc5, dept_plant_science, 2, 60),
    ("KU2DSCCHE111", "Basic Physical Chemistry and Forensic Chemistry", dsc5, dept_polymer_chemistry, 2, 60),  # Map to Polymer Chemistry
    ("KU2DSCCOM107", "Fundamentals of Income Tax", dsc5, dept_commerce, 2, 60),
    ("KU2DSCCSC112", "Basics of Data Analytics", dsc5, dept_computer_science, 2, 60),
    ("KU2DSCECO107", "Foundations for Economic Analysis", dsc5, dept_economics, 2, 60),
    ("KU2DSCENG106", "Prose in English", dsc5, dept_english, 2, 60),
    ("KU2DSCENG109", "Sports Literatures", dsc5, dept_english, 2, 60),
    ("KU2DSCHIS109", "Understanding Contemporary World History", dsc5, dept_history, 2, 60),
    ("KU2DSCMAL106", "Indian Sahithya Parichayam", dsc5, dept_malayalam, 2, 60),
    ("KU2DSCMAT112", "Differential Calculus, Curve Fitting And Coordinate Systems", dsc5, dept_mathematics, 2, 60),
    ("KU2DSCSTA131", "Probability and Random Variables", dsc5, dept_statistics, 2, 60),
    ("KU2DSCZOO108", "Cell Biology and Immunology", dsc5, dept_zoology, 2, 60),
    ("KU2DSCPOL105", "Indian Constitution-institution and Processes", dsc5, dept_political_science, 2, 60),
    ("KU2DSCSAN108", "Prose and Drama", dsc5, dept_sanskrit, 2, 60),
    ("KU2DSCPHY102", "Physics of Solids and Fluids", dsc5, dept_physics, 2, 60),

    # ===== DSC 6 COURSES ===== (Seat limit: 60)
    ("KU2DSCCHE114", "Foundations in Physical and Organic Chemistry", dsc6, dept_polymer_chemistry, 2, 60),  # Map to Polymer Chemistry
    ("KU2DSCCHE115", "Foundation in Physical, Organic & Bioinorganic Chemistry", dsc6, dept_polymer_chemistry, 2, 60),  # Map to Polymer Chemistry
    ("KU2DSCCOM108", "Business Economics", dsc6, dept_commerce, 2, 60),
    ("KU2DSCCCSC109", "Data Management Platform", dsc6, dept_computer_science, 2, 60),
    ("KU2DSCECO108", "Demography", dsc6, dept_economics, 2, 60),
    ("KU2DSCENG110", "Contemporary Literatures", dsc6, dept_english, 2, 60),
    ("KU2DSCHIS108", "Economic History of Modern India (1858 to 1947)", dsc6, dept_history, 2, 60),
    ("KU2DSCMAL108", "Pravasavum Sahithyavum", dsc6, dept_malayalam, 2, 60),
    ("KU2DSCMAT116", "Multivariable Calculus", dsc6, dept_mathematics, 2, 60),
    ("KU2DSCMAT117", "Calculus and Matrix Algebra-II", dsc6, dept_mathematics, 2, 60),
    ("KU2DSCSTA134", "Quantitative Techniques in Data Analysis – I", dsc6, dept_statistics, 2, 60),
    ("KU2DSCPOL106", "Ideas and Concept in Political Science", dsc6, dept_political_science, 2, 60),
    ("KU2DSCSAN106", "Karnabhara- Relevance and Impact on Modern Theatre", dsc6, dept_sanskrit, 2, 60),
    ("KU2DSCPHY125", "Digital Electronics", dsc6, dept_physics, 2, 60),

    # ===== MDC COURSES ===== (Seat limit: 70)
    ("KU2MDCENG104", "Comic and Graphic Narratives", mdc, dept_english, 2, 70),
    ("KU2MDCCOM102", "Fundamentals of Entrepreneurship", mdc, dept_commerce, 2, 70),
    ("KU2MDCENG105", "Food and Fashion Narratives", mdc, dept_english, 2, 70),
    ("KU2MDCENG106", "Popular Narratives", mdc, dept_english, 2, 70),
    ("KU2MDCHIN102", "Anudit Malayalam Sahitya", mdc, dept_hindi, 2, 70),
    ("KU2MDCHIS106", "Indian National Movement", mdc, dept_history, 2, 70),
    ("KU2MDCSAN104", "Herbal Literacy and Ethno-Botanical Awareness", mdc, dept_sanskrit, 2, 70),
    ("KU02MDCLIB108", "Digital Librarianship", mdc, dept_computer_science, 2, 70),  # Map to Computer Science
    ("KU2MDCMAT101", "Mathematical Reasoning", mdc, dept_mathematics, 2, 70),
]

print("Starting course insertion with 16-department mapping...")
print("=" * 70)
print("DEPARTMENT MAPPING:")
print("- All CHE courses → Polymer Chemistry Department")
print("- LIB courses → Computer Science Department (closest match)")
print("- DSC 5: 15 courses (seat limit: 60)")
print("- DSC 6: 14 courses (seat limit: 60)")
print("- MDC: 9 courses (seat limit: 70)")
print("=" * 70)

created_count = 0
skipped_count = 0
error_count = 0

# Track counts by department
dept_counts = {}

for course_data in courses_to_insert:
    course_code, course_name, course_type, department, semester, seat_limit = course_data

    try:
        # Check if course already exists
        if Course.objects.filter(course_code=course_code).exists():
            print(f"⚠️  Skipping {course_code} - already exists")
            skipped_count += 1
            continue

        # Create the course
        course = Course.objects.create(
            course_code=course_code,
            course_name=course_name,
            course_type=course_type,
            department=department,
            semester=semester,
            seat_limit=seat_limit
        )

        # Track department counts
        dept_name = department.name
        dept_counts[dept_name] = dept_counts.get(dept_name, 0) + 1

        # Get course type label
        if course_type == dsc5:
            course_type_label = "DSC5"
        elif course_type == dsc6:
            course_type_label = "DSC6"
        else:
            course_type_label = "MDC"

        print(f"✅ Created: {course_code} [{course_type_label}] → {dept_name}")
        created_count += 1

    except Exception as e:
        print(f"❌ Error creating {course_code}: {e}")
        error_count += 1

print("\n" + "=" * 70)
print("INSERTION SUMMARY:")
print("=" * 70)
print(f"✅ Total Created: {created_count} courses")
print(f"⚠️  Skipped (already exists): {skipped_count} courses")
print(f"❌ Errors: {error_count} courses")
print("=" * 70)

# Show department-wise breakdown
print("\n📊 DEPARTMENT-WISE DISTRIBUTION:")
print("-" * 40)
sorted_depts = sorted(dept_counts.items(), key=lambda x: x[1], reverse=True)
for dept, count in sorted_depts:
    print(f"  {dept}: {count} courses")

# Verify insertion
total_in_db = Course.objects.count()
print(f"\n📈 DATABASE STATUS:")
print(f"Total courses in database: {total_in_db}")
print(f"Expected total courses: {15 + 14 + 9} = 38 courses")

# Show breakdown by course type in database
print("\n📋 BREAKDOWN BY COURSE TYPE:")
dsc5_db = Course.objects.filter(course_type=dsc5).count()
dsc6_db = Course.objects.filter(course_type=dsc6).count()
mdc_db = Course.objects.filter(course_type=mdc).count()
print(f"  DSC 5: {dsc5_db} courses")
print(f"  DSC 6: {dsc6_db} courses")
print(f"  MDC: {mdc_db} courses")
print("-" * 40)
print(f"  TOTAL: {dsc5_db + dsc6_db + mdc_db} courses")

