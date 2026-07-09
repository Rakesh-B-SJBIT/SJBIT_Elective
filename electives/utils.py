"""
SJBIT Elective Allocation Engine
─────────────────────────────────
First-Come-First-Served allocation based on submission timestamp AND preference ranking.
Algorithm:
  1. Get all pending preferences sorted by: submission time (earliest first), then rank (1st choice first)
  2. For each preference in order:
     - If student already has 3 allocations (1 OPEN + 1 PROFESSIONAL + 1 ABILITY) → skip
     - If course has seats AND matches student's allocation needs → allocate
     - Else → waitlist
  3. Students get THREE confirmed allocations:
     - One OPEN elective (NOT from their own department)
     - One PROFESSIONAL elective (can be from any department)
     - One ABILITY ENHANCEMENT elective (can be from any department)
  4. Allocation priority:
     - Students submit up to 5 preferences (must include at least 1 OPEN, 1 PROFESSIONAL, 1 ABILITY)
     - System tries to allocate based on FCFS (submission time) and preference rank
     - Each student gets exactly 3 courses (1 of each type)
"""

from django.db import transaction
from django.utils import timezone
from .models import Preference, Allocation, Waitlist, AllocationRun, Course


def _get_preference_key(pref):
    """Return sorting key: (submission_time, rank)."""
    return (pref.submitted_at, pref.rank)


@transaction.atomic
def run_allocation(run_by='system', reset=False):
    if reset:
        Allocation.objects.all().delete()
        Waitlist.objects.all().delete()
        Course.objects.all().update(enrolled_count=0)
        Preference.objects.all().update(status='pending')

    allocated = waitlisted = rejected = 0
    
    # Sync enrolled counts with actual confirmed allocations BEFORE starting
    for course in Course.objects.filter(is_active=True):
        actual_count = Allocation.objects.filter(
            course=course,
            status='confirmed'
        ).count()
        course.enrolled_count = actual_count
        course.save(update_fields=['enrolled_count'])
    
    # Get all pending preferences sorted by submission time (FCFS) then rank
    all_pending = list(
        Preference.objects.filter(status='pending')
        .select_related('student', 'course')
        .order_by('submitted_at', 'rank')
    )
    
    # Track which students have been allocated and what types
    # Format: {student_id: {'open': bool, 'professional': bool, 'ability': bool}}
    student_allocations = {}
    
    # Track actual seat counts per course during allocation (in-memory tracking)
    course_seat_tracker = {}
    
    # Track waitlist positions per course
    waitlist_positions = {}
    
    for pref in all_pending:
        student = pref.student
        course = pref.course
        
        # Initialize course seat tracker if not exists
        if course.id not in course_seat_tracker:
            # Count actual confirmed allocations from database
            confirmed_count = Allocation.objects.filter(
                course=course,
                status='confirmed'
            ).count()
            course_seat_tracker[course.id] = confirmed_count
        
        # Initialize student allocation tracking if not exists
        if student.id not in student_allocations:
            student_allocations[student.id] = {'open': False, 'professional': False, 'ability': False}
        
        # Check if student already has all 3 allocations
        alloc_status = student_allocations[student.id]
        if alloc_status['open'] and alloc_status['professional'] and alloc_status['ability']:
            pref.status = 'rejected'
            pref.save(update_fields=['status'])
            rejected += 1
            continue
        
        # Check if student needs this type of course
        needs_open = not alloc_status['open'] and course.category == 'open'
        needs_professional = not alloc_status['professional'] and course.category == 'professional'
        needs_ability = not alloc_status['ability'] and course.category == 'ability'
        
        if not (needs_open or needs_professional or needs_ability):
            # Student doesn't need this type of course (already has one)
            pref.status = 'rejected'
            pref.save(update_fields=['status'])
            rejected += 1
            continue
        
        # For OPEN electives: Check if course is from student's own department
        if course.category == 'open' and student.department and course.department:
            if student.department.code == course.department.code:
                # Student trying to select OPEN elective from their own department - reject
                pref.status = 'rejected'
                pref.save(update_fields=['status'])
                rejected += 1
                continue
        
        # Check course availability using in-memory tracker (more accurate)
        current_enrolled = course_seat_tracker[course.id]
        if current_enrolled < course.total_seats:
            # Allocate to this course
            alloc, created = Allocation.objects.update_or_create(
                student=student, course=course,
                defaults=dict(
                    status='confirmed',
                    preference_rank=pref.rank,
                    priority_score=0,  # No priority score needed for FCFS
                    allocated_by='system',
                    allocated_at=timezone.now(),
                )
            )
            pref.status = 'allocated'
            pref.save(update_fields=['status'])
            
            # Increment in-memory tracker (prevents double allocation)
            course_seat_tracker[course.id] += 1
            
            # Update student allocation tracking
            if course.category == 'open':
                student_allocations[student.id]['open'] = True
            elif course.category == 'professional':
                student_allocations[student.id]['professional'] = True
            elif course.category == 'ability':
                student_allocations[student.id]['ability'] = True
            
            allocated += 1
        else:
            # Waitlist
            if course.id not in waitlist_positions:
                waitlist_positions[course.id] = Waitlist.objects.filter(course=course, is_active=True).count() + 1
            
            Allocation.objects.update_or_create(
                student=student, course=course,
                defaults=dict(
                    status='waitlisted',
                    preference_rank=pref.rank,
                    priority_score=0,
                    allocated_by='system'
                )
            )
            Waitlist.objects.get_or_create(
                student=student, course=course,
                defaults=dict(
                    position=waitlist_positions[course.id],
                    is_active=True
                )
            )
            waitlist_positions[course.id] += 1
            pref.status = 'waitlisted'
            pref.save(update_fields=['status'])
            waitlisted += 1
    
    # Final sync: Update all course enrolled_count fields with actual confirmed allocations
    for course in Course.objects.filter(is_active=True):
        actual_count = Allocation.objects.filter(
            course=course,
            status='confirmed'
        ).count()
        course.enrolled_count = actual_count
        course.save(update_fields=['enrolled_count'])
    
    return AllocationRun.objects.create(
        run_by=run_by,
        total_allocated=allocated,
        total_waitlisted=waitlisted,
        total_rejected=rejected,
    )


@transaction.atomic
def promote_waitlist(course):
    """
    Promote next eligible student in waitlist when a seat frees up.
    Checks for conflicts - won't promote if student already has that category allocated.
    """
    if course.available_seats <= 0:
        return None
    
    # Get all active waitlist entries for this course, ordered by position
    waitlist_entries = Waitlist.objects.filter(
        course=course, 
        is_active=True
    ).select_related('student').order_by('position')
    
    promoted_student = None
    
    for waitlist_entry in waitlist_entries:
        student = waitlist_entry.student
        
        # Check if student already has an allocation for this category
        existing_allocation = Allocation.objects.filter(
            student=student,
            course__category=course.category,
            status='confirmed'
        ).exclude(course=course).first()
        
        if existing_allocation:
            # Student already has this category allocated - skip to next in waitlist
            continue
        
        # Check for OPEN elective department conflict
        if course.category == 'open' and student.department and course.department:
            if student.department.code == course.department.code:
                # Student's own department - skip to next in waitlist
                continue
        
        # Student is eligible - promote them
        Allocation.objects.filter(student=student, course=course).update(
            status='confirmed', 
            allocated_by='waitlist', 
            allocated_at=timezone.now()
        )
        Preference.objects.filter(student=student, course=course).update(status='allocated')
        
        waitlist_entry.is_active = False
        waitlist_entry.promoted_at = timezone.now()
        waitlist_entry.save()
        
        course.enrolled_count = min(course.enrolled_count + 1, course.total_seats)
        course.save(update_fields=['enrolled_count'])
        
        promoted_student = student
        break  # Only promote one student per call
    
    # Re-number remaining waitlist positions
    for i, w in enumerate(Waitlist.objects.filter(course=course, is_active=True).order_by('position'), 1):
        w.position = i
        w.save(update_fields=['position'])
    
    return promoted_student


@transaction.atomic
def auto_promote_waitlist_on_seat_increase(course, old_seats, new_seats):
    """
    Automatically promote waitlisted students when course seats are increased.
    Promotes multiple students if multiple seats are added.
    Returns list of promoted students.
    """
    if new_seats <= old_seats:
        return []  # No increase, nothing to do
    
    seats_added = new_seats - old_seats
    promoted_students = []
    
    # Try to promote students for each new seat added
    for _ in range(seats_added):
        # Check if there are available seats and waitlisted students
        if course.available_seats <= 0:
            break
        
        promoted = promote_waitlist(course)
        if promoted:
            promoted_students.append(promoted)
        else:
            break  # No more eligible students in waitlist
    
    return promoted_students


def check_eligibility(student, course):
    """Return (ok: bool, reason: str)."""
    if student.semester not in course.semesters_list:
        return False, f'Course not available for Semester {student.semester}.'
    
    # For OPEN electives: Students cannot select courses from their own department
    if course.category == 'open' and student.department and course.department:
        if student.department.code == course.department.code:
            return False, f'OPEN electives must be from other departments. This course is from your own department ({course.department.code}).'
    
    from .models import CourseHistory
    hist = CourseHistory.objects.filter(student=student, course_code=course.code).first()
    if hist:
        if hist.hist_type == 'completed':
            return False, 'You have already completed this course.'
        if hist.hist_type == 'scheduled':
            return False, 'This course is already scheduled in a future semester.'
        if hist.hist_type == 'ongoing':
            return False, 'You are currently enrolled in this course.'
    if course.available_seats <= 0:
        return False, 'No seats available (you may still join the waitlist).'
    return True, 'Eligible'
