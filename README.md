# FYUGP Course Allotment System

A robust Django-based web application designed to manage the Four-Year Undergraduate Programme (FYUGP) course allotment process. The system handles multiple student cohorts, complex pathway rules, and automated course allocation based on merit and category quotas.

## 🚀 Key Features

### 👨‍🎓 For Students
*   **Cohort-Aware Selection:** Students only see courses available for their specific admission year and semester.
*   **Dynamic Preference Setting:** Interface to select Major, Minor, MDC, and VAC courses based on FYUGP regulations.
*   **Real-time Availability:** Only active batches (courses) are displayed.
*   **Profile Management:** View academic records and allotment history.

### 🛡️ For Administrators
*   **Merit-Based Allotment:** Automated algorithm that ranks students by Normalized Marks (Sem 1/2) or Semester Marks (Sem 3+).
*   **Quota Management:** configurable seat percentages for General, SC/ST, EWS, and other categories.
*   **Multi-Cohort Support:** Run allotments for 2025 and 2026 batches simultaneously without data interference.
*   **Detailed Analytics:** View submission statistics and download reports in CSV format.

---

## 📸 Screenshots

### 1. Student Dashboard
*A clean interface providing access to course selection, results, and profile.*
![Student Dashboard](static/images/readme/student_dashboard.png)

### 2. Course Selection (Semester 3)
*Dynamic form showing the 6-paper selection logic (Majors, Minors, MDC, and VAC).*
![Course Selection](static/images/readme/course_selection.png)

### 3. Admin Allotment Management
*The control center for triggering automated allocations for different semesters.*
![Admin Allotment](static/images/readme/admin_allotment.png)

### 4. Allotment Statistics
*Visual breakdown of submission progress by department.*
![Allotment Stats](static/images/readme/allotment_stats.png)

---

## 🛠️ System Workflow

### 1. Database Architecture
The system uses three primary tables to manage the lifecycle of an allotment:
*   **`CoursePreference`**: Temporary storage for student choices.
*   **`CourseAllotment`**: Permanent storage for finalized results.
*   **`Batch`**: Tracks seat limits and real-time availability (`seats_taken`).

### 2. The Allotment Algorithm (Admin)
When the Admin triggers an allotment, the system executes these steps:
1.  **Scope Check:** Identifies the target cohort (Admission Year) based on the current academic cycle.
2.  **Student Ranking:** 
    *   **Sem 1 & 2:** Sorted by `normalized_marks`.
    *   **Sem 3:** Sorted by `first_sem_marks`.
3.  **Core Allocation:** Assigns Major papers (Paper 1 & 2) directly within the student's department.
4.  **Preference Processing:** Iterates through student choices for Minors, MDC, and VAC.
5.  **Quota Enforcement:** For MDC/VAC, the system fills seats based on General, SC/ST, and Special quotas before performing a "Second Pass" for unallotted students.

---

## 💻 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone git@github.com:abhinand128/project_fyugp_course_allotment.git
   cd project_fyugp_course_allotment
   ```

2. **Install Dependencies:**
   ```bash
   pip install django
   ```

3. **Database Setup:**
   ```bash
   python manage.py migrate
   python manage.py loaddata courses.json  # If initial data is available
   ```

4. **Run Server:**
   ```bash
   python manage.py runserver
   ```

---

## 📁 File Structure
*   `allotmentapp/views.py`: Contains the core allotment logic and paper allocation functions.
*   `allotmentapp/forms.py`: Handles dynamic form generation for different semesters.
*   `allotmentapp/models.py`: Database schema for Students, Batches, and Allotments.
*   `templates/`: HTML templates for Admin and Student interfaces.
*   `SYSTEM_WORKFLOW.txt`: Detailed technical breakdown of the backend logic.

---

## ⚖️ License
This project is developed for academic administration purposes.
