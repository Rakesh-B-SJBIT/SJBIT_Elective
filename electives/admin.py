from django.contrib import admin
from .models import Department, Student, Course, Preference, Allocation, Waitlist, AllocationRun, CourseHistory


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display  = ['student_id', 'full_name', 'department', 'semester', 'cgpa']
    list_filter   = ['department', 'semester']
    search_fields = ['student_id', 'user__first_name', 'user__last_name']

    def full_name(self, obj): return obj.user.get_full_name()


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display  = ['code', 'title', 'department', 'category', 'total_seats', 'enrolled_count', 'is_active']
    list_filter   = ['category', 'department', 'is_active', 'level']
    search_fields = ['code', 'title']
    list_editable = ['is_active', 'total_seats']


@admin.register(Preference)
class PreferenceAdmin(admin.ModelAdmin):
    list_display  = ['student', 'course', 'rank', 'submitted_at', 'status']
    list_filter   = ['status', 'course__department']
    list_editable = ['status']


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display  = ['student', 'course', 'status', 'preference_rank', 'priority_score', 'allocated_by', 'allocated_at']
    list_filter   = ['status', 'allocated_by', 'course__department']
    list_editable = ['status']


@admin.register(Waitlist)
class WaitlistAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'position', 'added_at', 'is_active']
    list_filter  = ['is_active']


@admin.register(AllocationRun)
class AllocationRunAdmin(admin.ModelAdmin):
    list_display   = ['run_at', 'run_by', 'total_allocated', 'total_waitlisted', 'total_rejected']
    readonly_fields = ['run_at']


@admin.register(CourseHistory)
class CourseHistoryAdmin(admin.ModelAdmin):
    list_display = ['student', 'course_code', 'course_title', 'semester', 'hist_type']
    list_filter  = ['hist_type', 'semester']
