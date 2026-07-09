"""
Test script to verify seat allocation fix
This script tests that:
1. Courses with 1 seat only allocate to 1 student (not 2)
2. Seat counts are properly reflected in course catalog
3. Seat counts are dynamically updated
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sjbit_elective.settings')
django.setup()

from django.contrib.auth.models import User
from electives.models import Student, Department, Course, Preference, Allocation
from electives.utils import run_allocation
from django.utils import timezone
from datetime import timedelta


def cleanup_test_data():
    """Clean up any existing test data"""
    print("🧹 Cleaning up test data...")
    Allocation.objects.filter(student__student_id__startswith='TEST').delete()
    Preference.objects.filter(student__student_id__startswith='TEST').delete()
    Student.objects.filter(student_id__startswith='TEST').delete()
    User.objects.filter(username__startswith='test_student').delete()
    Course.objects.filter(code__startswith='TEST').delete()
    print("✓ Cleanup complete\n")


def create_test_data():
    """Create test data: 1 course with 1 seat, 2 students with preferences"""
    print("📝 Creating test data...")
    
    # Get or create a department
    dept, _ = Department.objects.get_or_create(
        code='TST',
        defaults={'name': 'Test Department'}
    )
    
    # Create a course with only 1 seat
    course = Course.objects.create(
        department=dept,
        code='TEST101',
        title='Test Course with 1 Seat',
        credits=3,
        category='professional',
        level='intermediate',
        description='Test course to verify allocation logic',
        job_perspectives='Test Job',
        total_seats=1,  # Only 1 seat!
        enrolled_count=0,
        is_active=True,
        for_semesters='5,6,7',
        instructor='Test Instructor'
    )
    print(f"  ✓ Created course: {course.code} with {course.total_seats} seat(s)")
    
    # Create 2 students
    students = []
    for i in range(1, 3):
        user = User.objects.create_user(
            username=f'test_student{i}',
            email=f'test{i}@test.com',
            first_name=f'Test{i}',
            last_name='Student',
            password='test123'
        )
        student = Student.objects.create(
            user=user,
            student_id=f'TEST00{i}',
            department=dept,
            semester=5,
            cgpa=8.0 + i * 0.5
        )
        students.append(student)
        print(f"  ✓ Created student: {student.student_id} (CGPA: {student.cgpa})")
    
    # Both students add the same course as their 2nd preference
    # Student 1 submits first (earlier timestamp)
    base_time = timezone.now() - timedelta(hours=2)
    
    pref1 = Preference.objects.create(
        student=students[0],
        course=course,
        rank=2,
        submitted_at=base_time,
        status='pending'
    )
    print(f"  ✓ Student {students[0].student_id} added {course.code} at rank 2 (submitted at {pref1.submitted_at})")
    
    # Student 2 submits 1 hour later
    pref2 = Preference.objects.create(
        student=students[1],
        course=course,
        rank=2,
        submitted_at=base_time + timedelta(hours=1),
        status='pending'
    )
    print(f"  ✓ Student {students[1].student_id} added {course.code} at rank 2 (submitted at {pref2.submitted_at})")
    
    print()
    return course, students


def run_test():
    """Run the allocation and verify results"""
    print("🚀 Running allocation algorithm...\n")
    
    result = run_allocation(run_by='test_script', reset=False)
    
    print(f"📊 Allocation Results:")
    print(f"  • Allocated: {result.total_allocated}")
    print(f"  • Waitlisted: {result.total_waitlisted}")
    print(f"  • Rejected: {result.total_rejected}\n")
    
    return result


def verify_results(course, students):
    """Verify that only 1 student got allocated"""
    print("🔍 Verifying allocation results...\n")
    
    # Refresh course from database
    course.refresh_from_db()
    
    # Count actual confirmed allocations
    confirmed_allocations = Allocation.objects.filter(
        course=course,
        status='confirmed'
    )
    
    confirmed_count = confirmed_allocations.count()
    
    print(f"Course: {course.code} ({course.title})")
    print(f"  • Total seats: {course.total_seats}")
    print(f"  • Enrolled count (DB field): {course.enrolled_count}")
    print(f"  • Actual confirmed allocations: {confirmed_count}")
    print(f"  • Available seats: {course.available_seats}\n")
    
    # Check each student's allocation status
    for student in students:
        alloc = Allocation.objects.filter(student=student, course=course).first()
        pref = Preference.objects.filter(student=student, course=course).first()
        
        if alloc:
            print(f"Student {student.student_id}:")
            print(f"  • Allocation status: {alloc.status}")
            print(f"  • Preference status: {pref.status if pref else 'N/A'}")
            print(f"  • Allocated at: {alloc.allocated_at}")
        else:
            print(f"Student {student.student_id}: No allocation")
        print()
    
    # Verify the fix worked
    print("=" * 60)
    if confirmed_count == 1 and course.enrolled_count == 1:
        print("✅ TEST PASSED!")
        print("   • Only 1 student was allocated (correct)")
        print("   • Enrolled count matches actual allocations (correct)")
        print("   • Seat count is properly reflected (correct)")
        return True
    else:
        print("❌ TEST FAILED!")
        if confirmed_count > 1:
            print(f"   • ERROR: {confirmed_count} students allocated to a course with 1 seat!")
        if course.enrolled_count != confirmed_count:
            print(f"   • ERROR: Enrolled count ({course.enrolled_count}) doesn't match actual allocations ({confirmed_count})")
        return False


def main():
    print("=" * 60)
    print("SEAT ALLOCATION FIX VERIFICATION TEST")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Cleanup
        cleanup_test_data()
        
        # Step 2: Create test data
        course, students = create_test_data()
        
        # Step 3: Run allocation
        run_test()
        
        # Step 4: Verify results
        success = verify_results(course, students)
        
        print("=" * 60)
        
        # Step 5: Cleanup
        print("\n🧹 Cleaning up test data...")
        cleanup_test_data()
        
        if success:
            print("\n🎉 All tests passed! The allocation fix is working correctly.")
        else:
            print("\n⚠️  Tests failed. Please review the allocation logic.")
        
    except Exception as e:
        print(f"\n❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
