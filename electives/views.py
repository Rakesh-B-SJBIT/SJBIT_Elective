import csv
import json
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from .models import (
    Student, Department, Course, Preference,
    Allocation, Waitlist, AllocationRun, CourseHistory
)
from .forms import LoginForm, RegisterForm, CourseFilterForm, CSVUploadForm
from .utils import run_allocation, check_eligibility, promote_waitlist

# Import CSV processing functions
try:
    from .csv_import import process_csv_import
except ImportError:
    process_csv_import = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_student(request):
    try:
        return request.user.student
    except Exception:
        return None


# ─── Public views ─────────────────────────────────────────────────────────────

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    stats = {
        'courses':    Course.objects.filter(is_active=True).count(),
        'students':   Student.objects.count(),
        'depts':      Department.objects.count(),
        'allocations':Allocation.objects.filter(status='confirmed').count(),
    }
    featured = Course.objects.filter(is_active=True).order_by('?')[:6]
    return render(request, 'electives/home.html', {'stats': stats, 'featured': featured})


def catalog(request):
    qs = Course.objects.filter(is_active=True).select_related('department')
    form = CourseFilterForm(request.GET or None)

    if form.is_valid():
        q    = form.cleaned_data.get('q')
        cat  = form.cleaned_data.get('category')
        dept = form.cleaned_data.get('department')
        lvl  = form.cleaned_data.get('level')
        only_seats = form.cleaned_data.get('seats')
        if q:
            qs = qs.filter(Q(title__icontains=q)|Q(code__icontains=q)|
                           Q(description__icontains=q)|Q(job_perspectives__icontains=q))
        if cat:  qs = qs.filter(category=cat)
        if dept: qs = qs.filter(department=dept)
        if lvl:  qs = qs.filter(level=lvl)
        if only_seats:
            qs = [c for c in qs if c.available_seats > 0]

    my_pref_ids = []
    if request.user.is_authenticated:
        s = _get_student(request)
        if s:
            my_pref_ids = list(Preference.objects.filter(student=s).values_list('course_id', flat=True))

    depts = Department.objects.all()
    return render(request, 'electives/catalog.html', {
        'courses': qs, 'form': form,
        'departments': depts, 'my_pref_ids': my_pref_ids,
    })


def course_detail(request, code):
    course = get_object_or_404(Course, code=code, is_active=True)
    in_prefs = False
    eligible, reason = True, ''
    student = None
    if request.user.is_authenticated:
        student = _get_student(request)
        if student:
            in_prefs = Preference.objects.filter(student=student, course=course).exists()
            eligible, reason = check_eligibility(student, course)
    related = Course.objects.filter(department=course.department, is_active=True).exclude(id=course.id)[:4]
    wl_count = Waitlist.objects.filter(course=course, is_active=True).count()
    return render(request, 'electives/course_detail.html', {
        'course': course, 'related': related,
        'in_prefs': in_prefs, 'eligible': eligible, 'reason': reason,
        'wl_count': wl_count,
    })


# ─── Auth ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request,
                            username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])
        if user:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(request.GET.get('next', 'dashboard'))
        messages.error(request, 'Invalid credentials – please try again.')
    return render(request, 'electives/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out successfully.')
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()
        Student.objects.create(
            user=user,
            student_id=form.cleaned_data['student_id'],
            department=form.cleaned_data['department'],
            semester=int(form.cleaned_data['semester']),
            cgpa=form.cleaned_data['cgpa'],
        )
        login(request, user)
        messages.success(request, 'Account created! Welcome to SJBIT Elective System.')
        return redirect('dashboard')
    return render(request, 'electives/register.html', {'form': form})


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    student = _get_student(request)
    if not student:
        if request.user.is_staff:
            return redirect('admin_panel')
        messages.error(request, 'No student profile found.')
        return redirect('home')
    prefs   = Preference.objects.filter(student=student).select_related('course','course__department').order_by('rank')
    allocs  = Allocation.objects.filter(student=student).select_related('course','course__department')
    wl      = Waitlist.objects.filter(student=student, is_active=True).select_related('course')
    confirmed_allocs = allocs.filter(status='confirmed')
    
    # Separate OPEN, PROFESSIONAL, and ABILITY allocations
    open_allocation = confirmed_allocs.filter(course__category='open').first()
    professional_allocation = confirmed_allocs.filter(course__category='professional').first()
    ability_allocation = confirmed_allocs.filter(course__category='ability').first()
    
    # Calculate total credits
    total_credits = sum(a.course.credits for a in confirmed_allocs)
    
    context = {
        'student': student,
        'prefs':   prefs,
        'allocs':  allocs,
        'confirmed': confirmed_allocs,
        'open_allocation': open_allocation,
        'professional_allocation': professional_allocation,
        'ability_allocation': ability_allocation,
        'waitlisted': allocs.filter(status='waitlisted'),
        'wl_entries': wl,
        'total_credits': total_credits,
    }
    return render(request, 'electives/dashboard.html', context)


# ─── Preferences AJAX ─────────────────────────────────────────────────────────

@login_required
def my_preferences(request):
    student = _get_student(request)
    if not student:
        return redirect('home')
    prefs = Preference.objects.filter(student=student).select_related('course','course__department').order_by('rank')
    return render(request, 'electives/preferences.html', {'student': student, 'prefs': prefs})


@login_required
@require_POST
def add_preference(request, course_id):
    student = _get_student(request)
    if not student:
        return JsonResponse({'ok': False, 'msg': 'No student profile.'})
    course = get_object_or_404(Course, id=course_id, is_active=True)

    # Check maximum 5 preferences
    current_prefs = Preference.objects.filter(student=student)
    if current_prefs.count() >= 5:
        return JsonResponse({'ok': False, 'msg': 'Maximum 5 preferences allowed.'})
    
    # Check if already in list
    if current_prefs.filter(course=course).exists():
        return JsonResponse({'ok': False, 'msg': 'Already in your list.'})

    # Check eligibility
    ok, reason = check_eligibility(student, course)
    if not ok and 'seats' not in reason.lower():   # seats warning ≠ hard block
        return JsonResponse({'ok': False, 'msg': reason})

    # Validate preference mix: Must have at least 1 OPEN, 1 PROFESSIONAL, and 1 ABILITY
    # Count current preferences by category
    open_count = current_prefs.filter(course__category='open').count()
    professional_count = current_prefs.filter(course__category='professional').count()
    ability_count = current_prefs.filter(course__category='ability').count()
    
    # If adding 5th preference, ensure we have at least 1 of each type
    if current_prefs.count() == 4:  # This will be the 5th preference
        if course.category == 'open':
            # Adding OPEN as 5th, check if we have at least 1 PROFESSIONAL and 1 ABILITY
            if professional_count == 0:
                return JsonResponse({'ok': False, 'msg': 'You must select at least 1 PROFESSIONAL elective. Please add a PROFESSIONAL elective first.'})
            if ability_count == 0:
                return JsonResponse({'ok': False, 'msg': 'You must select at least 1 ABILITY ENHANCEMENT elective. Please add an ABILITY ENHANCEMENT elective first.'})
        elif course.category == 'professional':
            # Adding PROFESSIONAL as 5th, check if we have at least 1 OPEN and 1 ABILITY
            if open_count == 0:
                return JsonResponse({'ok': False, 'msg': 'You must select at least 1 OPEN elective. Please add an OPEN elective first.'})
            if ability_count == 0:
                return JsonResponse({'ok': False, 'msg': 'You must select at least 1 ABILITY ENHANCEMENT elective. Please add an ABILITY ENHANCEMENT elective first.'})
        elif course.category == 'ability':
            # Adding ABILITY as 5th, check if we have at least 1 OPEN and 1 PROFESSIONAL
            if open_count == 0:
                return JsonResponse({'ok': False, 'msg': 'You must select at least 1 OPEN elective. Please add an OPEN elective first.'})
            if professional_count == 0:
                return JsonResponse({'ok': False, 'msg': 'You must select at least 1 PROFESSIONAL elective. Please add a PROFESSIONAL elective first.'})

    rank = current_prefs.count() + 1
    pref = Preference.objects.create(student=student, course=course, rank=rank)
    return JsonResponse({'ok': True, 'msg': f'"{course.title}" added at rank {rank}.', 'rank': rank, 'pref_id': pref.id})


@login_required
@require_POST
def remove_preference(request, pref_id):
    student = _get_student(request)
    pref    = get_object_or_404(Preference, id=pref_id, student=student)
    if pref.status == 'allocated':
        return JsonResponse({'ok': False, 'msg': 'Cannot remove an allocated preference.'})
    pref.delete()
    for i, p in enumerate(Preference.objects.filter(student=student).order_by('rank'), 1):
        p.rank = i; p.save(update_fields=['rank'])
    return JsonResponse({'ok': True, 'msg': 'Removed.'})


@login_required
@require_POST
def reorder_preferences(request):
    student = _get_student(request)
    try:
        order = json.loads(request.body).get('order', [])
    except Exception:
        return JsonResponse({'ok': False, 'msg': 'Bad data.'})
    prefs = {p.id: p for p in Preference.objects.filter(student=student)}
    for rank, pid in enumerate(order, 1):
        if pid in prefs:
            prefs[pid].rank = rank
            prefs[pid].save(update_fields=['rank'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def withdraw_from_waitlist(request, waitlist_id):
    """Allow students to withdraw themselves from a waitlist"""
    student = _get_student(request)
    if not student:
        return JsonResponse({'ok': False, 'msg': 'No student profile found.'})
    
    waitlist_entry = get_object_or_404(Waitlist, id=waitlist_id, student=student, is_active=True)
    course = waitlist_entry.course
    
    try:
        with transaction.atomic():
            # Mark waitlist entry as inactive
            waitlist_entry.is_active = False
            waitlist_entry.save(update_fields=['is_active'])
            
            # Update allocation status to cancelled
            Allocation.objects.filter(student=student, course=course, status='waitlisted').update(
                status='cancelled'
            )
            
            # Update preference status
            Preference.objects.filter(student=student, course=course, status='waitlisted').update(
                status='rejected'
            )
            
            # Re-number remaining waitlist positions
            for i, w in enumerate(Waitlist.objects.filter(course=course, is_active=True).order_by('position'), 1):
                w.position = i
                w.save(update_fields=['position'])
            
            return JsonResponse({
                'ok': True, 
                'msg': f'You have been removed from the waitlist for {course.title}.'
            })
    except Exception as e:
        return JsonResponse({'ok': False, 'msg': f'Error: {str(e)}'}, status=500)


@login_required
@require_POST
def increase_course_seats(request):
    """Admin endpoint to increase course seats and auto-promote waitlisted students"""
    if not request.user.is_staff:
        return JsonResponse({'ok': False, 'msg': 'Unauthorized'}, status=403)
    
    course_code = request.POST.get('course_code', '').strip().upper()
    try:
        new_seats = int(request.POST.get('new_seats', 0))
    except ValueError:
        return JsonResponse({'ok': False, 'msg': 'Invalid seat count'})
    
    if not course_code or new_seats <= 0:
        return JsonResponse({'ok': False, 'msg': 'Please provide course code and valid seat count'})
    
    try:
        course = Course.objects.get(code=course_code)
    except Course.DoesNotExist:
        return JsonResponse({'ok': False, 'msg': f'Course {course_code} not found'})
    
    old_seats = course.total_seats
    
    if new_seats <= old_seats:
        return JsonResponse({
            'ok': False, 
            'msg': f'New seat count ({new_seats}) must be greater than current ({old_seats})'
        })
    
    try:
        with transaction.atomic():
            # Update total seats
            course.total_seats = new_seats
            course.save(update_fields=['total_seats'])
            
            # Auto-promote waitlisted students
            from .utils import auto_promote_waitlist_on_seat_increase
            promoted_students = auto_promote_waitlist_on_seat_increase(course, old_seats, new_seats)
            
            # Get updated waitlist count
            remaining_waitlist = Waitlist.objects.filter(course=course, is_active=True).count()
            
            if promoted_students:
                student_names = ', '.join([s.student_id for s in promoted_students])
                return JsonResponse({
                    'ok': True,
                    'msg': f'Seats increased from {old_seats} to {new_seats}. '
                           f'{len(promoted_students)} student(s) promoted: {student_names}. '
                           f'{remaining_waitlist} still waitlisted.',
                    'promoted_count': len(promoted_students),
                    'remaining_waitlist': remaining_waitlist
                })
            else:
                return JsonResponse({
                    'ok': True,
                    'msg': f'Seats increased from {old_seats} to {new_seats}. '
                           f'No eligible students in waitlist to promote. '
                           f'{remaining_waitlist} waitlisted (may have conflicts).',
                    'promoted_count': 0,
                    'remaining_waitlist': remaining_waitlist
                })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'ok': False, 'msg': f'Error: {str(e)}'}, status=500)


# ─── Seat status AJAX ─────────────────────────────────────────────────────────

def seat_api(request, course_id):
    c = get_object_or_404(Course, id=course_id)
    
    # Get actual confirmed allocations from database for accuracy
    actual_enrolled = Allocation.objects.filter(
        course=c,
        status='confirmed'
    ).count()
    
    # Sync if mismatch detected
    if c.enrolled_count != actual_enrolled:
        c.enrolled_count = actual_enrolled
        c.save(update_fields=['enrolled_count'])
    
    available = max(0, c.total_seats - actual_enrolled)
    pct = min(100, int(actual_enrolled / c.total_seats * 100)) if c.total_seats > 0 else 0
    
    if pct >= 100:
        label = 'full'
    elif pct >= 80:
        label = 'almost_full'
    elif pct >= 50:
        label = 'filling'
    else:
        label = 'open'
    
    return JsonResponse({
        'available': available,
        'total':     c.total_seats,
        'enrolled':  actual_enrolled,
        'pct':       pct,
        'label':     label,
    })


def bulk_seat_api(request):
    ids = [int(x) for x in request.GET.get('ids','').split(',') if x]
    data = {}
    for c in Course.objects.filter(id__in=ids):
        # Get actual confirmed allocations from database
        actual_enrolled = Allocation.objects.filter(
            course=c,
            status='confirmed'
        ).count()
        
        # Sync if mismatch detected
        if c.enrolled_count != actual_enrolled:
            c.enrolled_count = actual_enrolled
            c.save(update_fields=['enrolled_count'])
        
        available = max(0, c.total_seats - actual_enrolled)
        pct = min(100, int(actual_enrolled / c.total_seats * 100)) if c.total_seats > 0 else 0
        
        if pct >= 100:
            label = 'full'
        elif pct >= 80:
            label = 'almost_full'
        elif pct >= 50:
            label = 'filling'
        else:
            label = 'open'
        
        data[str(c.id)] = {'available': available, 'pct': pct, 'label': label}
    return JsonResponse({'courses': data})


# ─── Allocation (Admin) ───────────────────────────────────────────────────────

@login_required
def admin_panel(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access required.')
        return redirect('home')
    
    # Sync all course seat counts before displaying
    from django.db import transaction
    with transaction.atomic():
        for course in Course.objects.filter(is_active=True):
            actual_count = Allocation.objects.filter(
                course=course,
                status='confirmed'
            ).count()
            if course.enrolled_count != actual_count:
                course.enrolled_count = actual_count
                course.save(update_fields=['enrolled_count'])
    
    courses = Course.objects.filter(is_active=True).annotate(
        conf=Count('allocations', filter=Q(allocations__status='confirmed')),
        wl=Count('waitlist', filter=Q(waitlist__is_active=True)),
    ).select_related('department').order_by('department__code','code')
    runs  = AllocationRun.objects.all()[:8]
    stats = {
        'students':    Student.objects.count(),
        'allocated':   Allocation.objects.filter(status='confirmed').count(),
        'waitlisted':  Waitlist.objects.filter(is_active=True).count(),
        'preferences': Preference.objects.count(),
    }
    return render(request, 'electives/admin_panel.html', {
        'courses': courses, 'runs': runs, 'stats': stats,
        'departments': Department.objects.all(),
    })


@login_required
@require_POST
def trigger_allocation(request):
    if not request.user.is_staff:
        return JsonResponse({'ok': False, 'msg': 'Unauthorized'}, status=403)
    
    reset = request.POST.get('reset', 'false').lower() == 'true'
    
    try:
        # Check if there are any preferences to allocate
        pref_count = Preference.objects.filter(status='pending').count()
        if pref_count == 0 and not reset:
            return JsonResponse({
                'ok': False, 
                'msg': 'No pending preferences found. Students need to submit preferences first.'
            })
        
        run = run_allocation(run_by=request.user.username, reset=reset)
        
        return JsonResponse({
            'ok': True,
            'msg': f'Allocation completed! {run.total_allocated} allocated · {run.total_waitlisted} waitlisted · {run.total_rejected} rejected.',
            'allocated': run.total_allocated, 
            'waitlisted': run.total_waitlisted,
            'rejected': run.total_rejected
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'ok': False, 'msg': f'Error: {str(e)}'}, status=500)


@login_required
@require_POST
def admin_override(request):
    if not request.user.is_staff:
        return JsonResponse({'ok': False, 'msg': 'Unauthorized'}, status=403)
    
    sid = request.POST.get('student_id', '').strip().upper()
    cid = request.POST.get('course_id', '').strip().upper()
    
    if not sid or not cid:
        return JsonResponse({'ok': False, 'msg': 'Please provide both Student ID and Course Code.'})
    
    try:
        student = Student.objects.get(student_id=sid)
    except Student.DoesNotExist:
        return JsonResponse({'ok': False, 'msg': f'Student ID "{sid}" not found.'})
    
    try:
        course = Course.objects.get(code=cid)
    except Course.DoesNotExist:
        return JsonResponse({'ok': False, 'msg': f'Course Code "{cid}" not found.'})
    
    try:
        # Check seat availability FIRST
        # if course.enrolled_count >= course.total_seats:
        #     return JsonResponse({
        #         'ok': False,
        #         'msg': f'❌ Course {cid} has no available seats ({course.enrolled_count}/{course.total_seats}). All seats are full.'
        #     })
        # Check actual confirmed allocations from database
        confirmed_count = Allocation.objects.filter(
            course=course,
            status='confirmed'
        ).count()

        if confirmed_count >= course.total_seats:
            return JsonResponse({
                'ok': False,
                'msg': f'❌ Course {cid} has no available seats ({confirmed_count}/{course.total_seats}). All seats are full.'
            })
        
        # Check if already allocated
        existing = Allocation.objects.filter(student=student, course=course).first()
        if existing and existing.status == 'confirmed':
            return JsonResponse({
                'ok': False, 
                'msg': f'❌ {sid} is already allocated to {cid}.'
            })
        
        # Check how many allocations student already has
        confirmed_allocations = Allocation.objects.filter(student=student, status='confirmed')
        open_count = confirmed_allocations.filter(course__category='open').count()
        professional_count = confirmed_allocations.filter(course__category='professional').count()
        ability_count = confirmed_allocations.filter(course__category='ability').count()
        
        # Validate allocation rules
        if course.category == 'open':
            if open_count >= 1:
                return JsonResponse({
                    'ok': False,
                    'msg': f'❌ {sid} already has 1 OPEN elective allocated. Students can only have 1 OPEN elective.'
                })
            # Check if OPEN elective is from student's own department
            if student.department and course.department:
                if student.department.code == course.department.code:
                    return JsonResponse({
                        'ok': False,
                        'msg': f'❌ OPEN electives must be from other departments. {cid} is from student\'s own department ({course.department.code}).'
                    })
        elif course.category == 'professional':
            if professional_count >= 1:
                return JsonResponse({
                    'ok': False,
                    'msg': f'❌ {sid} already has 1 PROFESSIONAL elective allocated. Students can only have 1 PROFESSIONAL elective.'
                })
        elif course.category == 'ability':
            if ability_count >= 1:
                return JsonResponse({
                    'ok': False,
                    'msg': f'❌ {sid} already has 1 ABILITY ENHANCEMENT elective allocated. Students can only have 1 ABILITY ENHANCEMENT elective.'
                })
        
        # Check if student already has 3 allocations (1 OPEN + 1 PROFESSIONAL + 1 ABILITY)
        if open_count >= 1 and professional_count >= 1 and ability_count >= 1:
            return JsonResponse({
                'ok': False,
                'msg': f'❌ {sid} already has maximum allocations (1 OPEN + 1 PROFESSIONAL + 1 ABILITY). Cannot allocate more courses.'
            })
        # Create or update allocation
        alloc, created = Allocation.objects.update_or_create(
            student=student,
            course=course,
            defaults={
                'status': 'confirmed',
                'allocated_by': f'admin:{request.user.username}',
                'allocated_at': timezone.now(),
                'notes': f'Manual override by {request.user.username}',
                'priority_score': 0
            }
        )

        # Sync enrolled count with actual confirmed allocations
        actual_count = Allocation.objects.filter(
            course=course,
            status='confirmed'
        ).count()

        course.enrolled_count = actual_count
        course.save(update_fields=['enrolled_count'])
        # Create or update allocation
        # alloc, created = Allocation.objects.update_or_create(
        #     student=student, 
        #     course=course,
        #     defaults={
        #         'status': 'confirmed', 
        #         'allocated_by': f'admin:{request.user.username}',
        #         'allocated_at': timezone.now(), 
        #         'notes': f'Manual override by {request.user.username}',
        #         'priority_score': 0
        #     }
        # )
        
        # # Update enrolled count if needed
        # if created or (existing and existing.status != 'confirmed'):
        #     course.enrolled_count += 1
        #     course.save(update_fields=['enrolled_count'])
        
        # Update preference status if exists
        Preference.objects.filter(student=student, course=course).update(status='allocated')
        
        # Remove from waitlist if exists
        Waitlist.objects.filter(student=student, course=course, is_active=True).update(
            is_active=False, 
            promoted_at=timezone.now()
        )
        
        # Calculate new counts
        new_open = open_count + (1 if course.category == 'open' else 0)
        new_prof = professional_count + (1 if course.category == 'professional' else 0)
        new_ability = ability_count + (1 if course.category == 'ability' else 0)
        
        action = 'allocated' if created else 'updated'
        return JsonResponse({
            'ok': True, 
            'msg': f'✅ Success! {sid} has been {action} to {cid} ({course.title}). Student now has {new_open} OPEN + {new_prof} PROFESSIONAL + {new_ability} ABILITY elective(s).'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'ok': False, 'msg': f'Error: {str(e)}'}, status=500)


# ─── Export CSV ──────────────────────────────────────────────────────────────

@login_required
def export_csv(request):
    if not request.user.is_staff:
        messages.error(request, 'Admin access required.')
        return redirect('home')
    dept     = request.GET.get('department','')
    cat      = request.GET.get('category','')
    status   = request.GET.get('status','confirmed')
    qs = Allocation.objects.select_related(
        'student','student__department','student__user','course','course__department'
    ).order_by('course__code','-priority_score')
    if status:   qs = qs.filter(status=status)
    if dept:     qs = qs.filter(student__department__code=dept)
    if cat:      qs = qs.filter(course__category=cat)

    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="sjbit_elective_allocation_report.csv"'
    w = csv.writer(resp)
    w.writerow(['Student ID','Name','Dept','CGPA','Semester',
                'Course Code','Course Title','Course Dept','Category','Credits',
                'Status','Pref Rank','Priority Score','Allocated At','Allocated By'])
    for a in qs:
        w.writerow([
            a.student.student_id, a.student.user.get_full_name(),
            a.student.department.code if a.student.department else '',
            a.student.cgpa, a.student.semester,
            a.course.code, a.course.title,
            a.course.department.code if a.course.department else '',
            a.course.get_category_display(), a.course.credits,
            a.status, a.preference_rank or '', round(a.priority_score,2),
            a.allocated_at.strftime('%Y-%m-%d %H:%M:%S'), a.allocated_by,
        ])
    return resp


# ─── Analytics API ────────────────────────────────────────────────────────────

@login_required
def analytics_api(request):
    if not request.user.is_staff:
        return JsonResponse({'error':'Unauthorized'},status=403)
    courses = list(Course.objects.filter(is_active=True).values(
        'code','title','enrolled_count','total_seats'
    ).order_by('-enrolled_count')[:12])
    dept_data = list(
        Allocation.objects.filter(status='confirmed').values('student__department__code')
        .annotate(count=Count('id')).order_by('-count')
    )
    cat_data = list(
        Allocation.objects.filter(status='confirmed').values('course__category')
        .annotate(count=Count('id'))
    )
    return JsonResponse({'courses': courses, 'dept': dept_data, 'category': cat_data})


@login_required
def diagnostic_view(request):
    """Diagnostic page to check system status"""
    if not request.user.is_staff:
        messages.error(request, 'Admin access required.')
        return redirect('home')
    
    from django.db import connection
    
    diagnostics = {
        'database': {
            'connected': True,
            'tables': connection.introspection.table_names()[:10]
        },
        'counts': {
            'departments': Department.objects.count(),
            'students': Student.objects.count(),
            'courses': Course.objects.count(),
            'active_courses': Course.objects.filter(is_active=True).count(),
            'preferences': Preference.objects.count(),
            'pending_preferences': Preference.objects.filter(status='pending').count(),
            'allocations': Allocation.objects.count(),
            'confirmed_allocations': Allocation.objects.filter(status='confirmed').count(),
            'waitlist_entries': Waitlist.objects.filter(is_active=True).count(),
            'allocation_runs': AllocationRun.objects.count(),
        },
        'recent_activity': {
            'last_allocation_run': AllocationRun.objects.order_by('-run_at').first(),
            'recent_preferences': Preference.objects.order_by('-submitted_at')[:5],
            'recent_allocations': Allocation.objects.order_by('-allocated_at')[:5],
        },
        'system': {
            'user_is_staff': request.user.is_staff,
            'user_is_superuser': request.user.is_superuser,
            'user_username': request.user.username,
        }
    }
    
    return render(request, 'electives/diagnostic.html', {'diagnostics': diagnostics})

# ─── CSV Upload ───────────────────────────────────────────────────────────────

@login_required
def csv_upload_view(request):
    """CSV upload page for admin users"""
    if not request.user.is_staff:
        messages.error(request, 'Admin access required.')
        return redirect('home')
    
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            import_type = form.cleaned_data['import_type']
            csv_file = form.cleaned_data['csv_file']
            
            try:
                if process_csv_import:
                    # Process the CSV import
                    result = process_csv_import(import_type, csv_file, request)
                    
                    if result['success']:
                        messages.success(request, 
                            f"Import completed! {result['success_count']} {import_type} imported successfully.")
                        if result['skip_count'] > 0:
                            messages.info(request, f"{result['skip_count']} existing records were skipped.")
                    else:
                        messages.error(request, f"Import failed: {result.get('error', 'Unknown error')}")
                else:
                    messages.error(request, "CSV import functionality not available.")
                
                return redirect('csv_upload')
                
            except Exception as e:
                messages.error(request, f"Import failed: {str(e)}")
    else:
        form = CSVUploadForm()
    
    return render(request, 'electives/csv_upload.html', {
        'form': form,
    })


@login_required
def download_sample_csv(request, file_type):
    """Download CSV template files"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    import os
    from django.http import HttpResponse
    
    # Create template content on the fly
    templates = {
        'departments': 'code,name\nCSE,Computer Science & Engineering\nECE,Electronics & Communication Engineering\n',
        'students': 'student_id,first_name,last_name,email,department_code,semester,cgpa,password\n1RV22CS001,John,Doe,john@sjbit.edu.in,CSE,5,8.5,student123\n',
        'courses': 'code,title,description,department_code,category,level,credits,total_seats,for_semesters,instructor,prerequisites,job_perspectives\n23CST501,Machine Learning,Introduction to ML algorithms,CSE,professional,intermediate,3,60,"5,6",Dr. Smith,Python Programming,ML Engineer;Data Scientist\n',
        'admins': 'username,email,first_name,last_name,password\nadmin,admin@sjbit.edu.in,Admin,User,admin123\n'
    }
    
    if file_type not in templates:
        raise Http404("Template file not found")
    
    response = HttpResponse(
        templates[file_type],
        content_type='text/csv',
    )
    response['Content-Disposition'] = f'attachment; filename="{file_type}_template.csv"'
    return response


@login_required
def clear_data_view(request):
    """Clear all data (admin only)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        data_type = request.POST.get('data_type')
        
        try:
            if data_type == 'all':
                # Clear all data except admin users
                from django.db import transaction
                with transaction.atomic():
                    Allocation.objects.all().delete()
                    Waitlist.objects.all().delete()
                    Preference.objects.all().delete()
                    CourseHistory.objects.all().delete()
                    AllocationRun.objects.all().delete()
                    Course.objects.all().delete()
                    Student.objects.all().delete()
                    # Delete non-staff users
                    User.objects.filter(is_staff=False).delete()
                    Department.objects.all().delete()
                
                messages.success(request, 'All data cleared successfully.')
                
            elif data_type == 'allocations':
                Allocation.objects.all().delete()
                Waitlist.objects.all().delete()
                AllocationRun.objects.all().delete()
                # Reset enrolled counts
                Course.objects.update(enrolled_count=0)
                messages.success(request, 'All allocations cleared successfully.')
                
            elif data_type == 'preferences':
                Preference.objects.all().delete()
                messages.success(request, 'All preferences cleared successfully.')
                
            else:
                messages.error(request, 'Invalid data type.')
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            messages.error(request, f'Error clearing data: {str(e)}')
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)
# ─── PDF Generation ───────────────────────────────────────────────────────────

@login_required
def download_allocation_pdf(request):
    """Download student's allocation PDF"""
    student = _get_student(request)
    if not student:
        messages.error(request, 'No student profile found.')
        return redirect('home')
    
    from .pdf_generator import generate_student_pdf_response
    
    # Get student's allocations
    allocations = Allocation.objects.filter(
        student=student,
        status='confirmed'
    ).select_related('course', 'course__department')
    
    return generate_student_pdf_response(student, allocations)


@login_required
def download_summary_pdf(request):
    """Download allocation summary PDF (admin only)"""
    if not request.user.is_staff:
        messages.error(request, 'Admin access required.')
        return redirect('home')
    
    from .pdf_generator import generate_summary_pdf_response
    
    # Get filters from request
    dept = request.GET.get('department', '')
    category = request.GET.get('category', '')
    status = request.GET.get('status', 'confirmed')
    
    # Build queryset
    qs = Allocation.objects.select_related(
        'student', 'student__department', 'student__user',
        'course', 'course__department'
    ).order_by('course__code', '-priority_score')
    
    if status:
        qs = qs.filter(status=status)
    if dept:
        qs = qs.filter(student__department__code=dept)
    if category:
        qs = qs.filter(course__category=category)
    
    # Generate title
    title_parts = ["Allocation Report"]
    if status:
        title_parts.append(f"({status.title()})")
    if dept:
        title_parts.append(f"- {dept} Department")
    if category:
        title_parts.append(f"- {category.title()} Electives")
    
    title = " ".join(title_parts)
    
    return generate_summary_pdf_response(list(qs), title)


# ─── User Profile ────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    """User profile page with basic details"""
    student = _get_student(request)
    
    # Get allocation stats
    if student:
        confirmed_allocations = Allocation.objects.filter(student=student, status='confirmed')
        open_count = confirmed_allocations.filter(course__category='open').count()
        professional_count = confirmed_allocations.filter(course__category='professional').count()
        ability_count = confirmed_allocations.filter(course__category='ability').count()
        total_credits = sum(a.course.credits for a in confirmed_allocations)
        
        context = {
            'student': student,
            'open_count': open_count,
            'professional_count': professional_count,
            'ability_count': ability_count,
            'total_credits': total_credits,
        }
    else:
        context = {}
    
    return render(request, 'electives/profile.html', context)


@login_required
def edit_profile_view(request):
    """Edit user profile"""
    student = _get_student(request)
    if not student:
        messages.error(request, 'No student profile found.')
        return redirect('home')
    
    if request.method == 'POST':
        # Update user fields
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name = request.POST.get('last_name', '').strip()
        request.user.email = request.POST.get('email', '').strip()
        request.user.save()
        
        # Update student fields
        phone = request.POST.get('phone', '').strip()
        if phone:
            student.phone = phone
            student.save(update_fields=['phone'])
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'electives/edit_profile.html', {'student': student})


@login_required
def change_password_view(request):
    """Change user password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validate current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'electives/change_password.html')
        
        # Validate new password
        if len(new_password) < 6:
            messages.error(request, 'New password must be at least 6 characters long.')
            return render(request, 'electives/change_password.html')
        
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'electives/change_password.html')
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        # Re-authenticate user
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('profile')
    
    return render(request, 'electives/change_password.html')