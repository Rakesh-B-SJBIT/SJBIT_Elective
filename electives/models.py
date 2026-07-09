from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ─── Choices ────────────────────────────────────────────────────────────────

CATEGORY_CHOICES = [
    ('professional', 'Professional Elective'),
    ('open',         'Open Elective'),
    ('ability',      'Ability Enhancement'),
]

SEMESTER_CHOICES = [(i, f'Semester {i}') for i in range(1, 9)]

HISTORY_TYPE = [
    ('completed', 'Completed'),
    ('ongoing',   'Ongoing'),
    ('scheduled', 'Scheduled Future'),
]

PREF_STATUS = [
    ('pending',    'Pending'),
    ('allocated',  'Allocated'),
    ('waitlisted', 'Waitlisted'),
    ('rejected',   'Rejected'),
]

ALLOC_STATUS = [
    ('confirmed',  'Confirmed'),
    ('waitlisted', 'Waitlisted'),
    ('cancelled',  'Cancelled'),
]


# ─── Department ──────────────────────────────────────────────────────────────

class Department(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} – {self.name}"


# ─── Student Profile ─────────────────────────────────────────────────────────

class Student(models.Model):
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    student_id  = models.CharField(max_length=20, unique=True)
    department  = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='students')
    semester    = models.IntegerField(choices=SEMESTER_CHOICES, default=5)
    cgpa        = models.DecimalField(max_digits=4, decimal_places=2, default=0.00,
                                      validators=[MinValueValidator(0), MaxValueValidator(10)])
    phone       = models.CharField(max_length=15, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cgpa', 'student_id']

    def __str__(self):
        return f"{self.student_id} – {self.user.get_full_name()}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username


# ─── Course ──────────────────────────────────────────────────────────────────

LEVEL_CHOICES = [('beginner','Beginner'),('intermediate','Intermediate'),('advanced','Advanced')]

CARD_COLORS = [
    '#4361ee','#3a0ca3','#7209b7','#f72585','#4cc9f0',
    '#06d6a0','#fb8500','#e63946','#2ec4b6','#ff6b6b',
]

class Course(models.Model):
    department          = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    code                = models.CharField(max_length=20, unique=True)
    title               = models.CharField(max_length=200)
    credits             = models.IntegerField(default=3)
    category            = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='open')
    level               = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='intermediate')
    description         = models.TextField()
    job_perspectives    = models.TextField(help_text='One per line – career roles this course targets')
    prerequisites       = models.TextField(blank=True, help_text='One per line')
    total_seats         = models.IntegerField(default=60)
    enrolled_count      = models.IntegerField(default=0)
    is_active           = models.BooleanField(default=True)
    is_open_elective    = models.BooleanField(default=False)
    for_semesters       = models.CharField(max_length=30, default='5,6,7',
                                           help_text='Comma-separated semesters e.g. 5,6,7')
    instructor          = models.CharField(max_length=100, blank=True)
    card_color          = models.CharField(max_length=7, default='#4361ee')
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['department', 'code']

    def __str__(self):
        return f"{self.code} – {self.title}"

    @property
    def available_seats(self):
        return max(0, self.total_seats - self.enrolled_count)

    @property
    def occupancy_pct(self):
        if not self.total_seats:
            return 0
        return min(100, int(self.enrolled_count / self.total_seats * 100))

    @property
    def seat_label(self):
        pct = self.occupancy_pct
        if pct >= 100: return 'full'
        if pct >= 80:  return 'almost_full'
        if pct >= 50:  return 'filling'
        return 'open'

    @property
    def semesters_list(self):
        try:
            return [int(s.strip()) for s in self.for_semesters.split(',')]
        except Exception:
            return [5, 6, 7]

    @property
    def job_list(self):
        return [j.strip() for j in self.job_perspectives.splitlines() if j.strip()]

    @property
    def prereq_list(self):
        return [p.strip() for p in self.prerequisites.splitlines() if p.strip()]


# ─── Course History ──────────────────────────────────────────────────────────

class CourseHistory(models.Model):
    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='history')
    course_code  = models.CharField(max_length=20)
    course_title = models.CharField(max_length=200)
    semester     = models.IntegerField(choices=SEMESTER_CHOICES)
    hist_type    = models.CharField(max_length=20, choices=HISTORY_TYPE)
    grade        = models.CharField(max_length=5, blank=True)

    class Meta:
        unique_together = ['student', 'course_code']
        ordering = ['semester']

    def __str__(self):
        return f"{self.student.student_id} – {self.course_code} ({self.hist_type})"


# ─── Preference ──────────────────────────────────────────────────────────────

class Preference(models.Model):
    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='preferences')
    course       = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='preferences')
    rank         = models.IntegerField(default=1)
    submitted_at = models.DateTimeField(default=timezone.now)
    status       = models.CharField(max_length=20, choices=PREF_STATUS, default='pending')

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['student', 'rank']

    def __str__(self):
        return f"{self.student.student_id} → {self.course.code} (rank {self.rank})"


# ─── Allocation ──────────────────────────────────────────────────────────────

class Allocation(models.Model):
    student        = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='allocations')
    course         = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='allocations')
    status         = models.CharField(max_length=20, choices=ALLOC_STATUS, default='confirmed')
    preference_rank= models.IntegerField(null=True, blank=True)
    priority_score = models.FloatField(default=0.0)
    allocated_by   = models.CharField(max_length=20, default='system')
    allocated_at   = models.DateTimeField(default=timezone.now)
    notes          = models.TextField(blank=True)

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-allocated_at']

    def __str__(self):
        return f"{self.student.student_id} → {self.course.code} [{self.status}]"


# ─── Waitlist ────────────────────────────────────────────────────────────────

class Waitlist(models.Model):
    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='waitlist')
    course       = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='waitlist')
    position     = models.IntegerField()
    added_at     = models.DateTimeField(default=timezone.now)
    promoted_at  = models.DateTimeField(null=True, blank=True)
    is_active    = models.BooleanField(default=True)

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['course', 'position']

    def __str__(self):
        return f"{self.student.student_id} → {self.course.code} [#{self.position}]"


# ─── Allocation Run Log ───────────────────────────────────────────────────────

class AllocationRun(models.Model):
    run_at           = models.DateTimeField(default=timezone.now)
    run_by           = models.CharField(max_length=80, default='system')
    total_allocated  = models.IntegerField(default=0)
    total_waitlisted = models.IntegerField(default=0)
    total_rejected   = models.IntegerField(default=0)

    class Meta:
        ordering = ['-run_at']

    def __str__(self):
        return f"Run {self.run_at:%Y-%m-%d %H:%M} by {self.run_by}"
