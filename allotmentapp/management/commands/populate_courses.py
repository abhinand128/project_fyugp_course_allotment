"""
Django Management Command: populate_vac_mdc_courses.py

Place this file at:
    allotmentapp/management/commands/populate_vac_mdc_courses.py

Make sure these directories exist with __init__.py files:
    allotmentapp/management/__init__.py
    allotmentapp/management/commands/__init__.py

Run with:
    python manage.py populate_vac_mdc_courses
"""

from django.core.management.base import BaseCommand
from allotmentapp.models import Course, Course_type, Department


# (course_type_name, course_code, course_name, seat_limit)
# Department is derived from the course code prefix (3-letter dept code)
# For VAC/MDC courses, department is resolved from the code segment.

DEPT_CODE_MAP = {
    "BOT": "Plant Science",
    "HIN": "Hindi",
    "ENG": "English",
    "COM": "Commerce",
    "PCH": "Polymer Chemistry",
    "HIS": "History",
    "MAL": "Malayalam",
}

COURSE_DATA = [
    # --- VAC (seat limit: 60) ---
    ("VAC", "KU3VACBOT122", "Conservation Biology",                          "BOT", 60),
    ("VAC", "KU3VACHIN102", "Hindi Sahitya Evam Manavadhikar",               "HIN", 60),
    ("VAC", "KU3VACENG201", "Recovering Nature",                             "ENG", 60),
    ("VAC", "KU3VACENG202", "Reconstructing Gender",                         "ENG", 60),
    ("VAC", "KU3VACCOM100", "Professional Ethics and Corporate Governance",  "COM", 60),
    ("VAC", "KU3VACPCH102", "Polymers and Polymer Composites",               "PCH", 60),
    ("VAC", "KU3DSCHIS103", "History of Human Rights Movements in India",    "HIS", 60),

    # --- MDC (seat limit: 80) ---
    ("MDC", "KU3MDCMAL103", "Keraleeyadhunikatha",                           "MAL", 80),
    ("MDC", "KU3MDCMAL105", "Lingapadaviyude Keraleeya Parisaram",           "MAL", 80),
    ("MDC", "KU3MDCENG201", "Kerala Knowledge Systems",                      "ENG", 80),
]

SEMESTER = 3


class Command(BaseCommand):
    help = "Populate the database with semester-3 VAC and MDC course data"

    def handle(self, *args, **kwargs):
        created_count = 0
        skipped_count = 0
        error_count   = 0

        for type_name, code, name, dept_code, seat_limit in COURSE_DATA:
            try:
                dept_name = DEPT_CODE_MAP.get(dept_code)
                if not dept_name:
                    raise ValueError(f"Unknown department code '{dept_code}'")

                dept = Department.objects.get(name__iexact=dept_name)

                course_type, _ = Course_type.objects.get_or_create(name=type_name)

                course, created = Course.objects.get_or_create(
                    course_code=code,
                    defaults={
                        "course_name": name,
                        "course_type": course_type,
                        "department":  dept,
                        "semester":    SEMESTER,
                        "seat_limit":  seat_limit,
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [CREATED]  {code} — {name}  ({dept_name} / {type_name} / seats:{seat_limit})"
                        )
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"  [SKIPPED]  {code} already exists")
                    )

            except Department.DoesNotExist:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  [ERROR]    Department '{dept_name}' not found in DB — skipping {code}"
                    )
                )
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"  [ERROR]    {code}: {e}")
                )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"  Created : {created_count}"))
        self.stdout.write(self.style.WARNING(f"  Skipped : {skipped_count}"))
        self.stdout.write(self.style.ERROR  (f"  Errors  : {error_count}"))
        self.stdout.write("=" * 60)
