"""
Management command to sync course enrolled_count with actual confirmed allocations
Usage: python manage.py sync_seat_counts
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from electives.models import Course, Allocation


class Command(BaseCommand):
    help = 'Synchronize course enrolled_count with actual confirmed allocations'

    def handle(self, *args, **options):
        self.stdout.write('Starting seat count synchronization...\n')
        
        updated_count = 0
        mismatches = []
        
        with transaction.atomic():
            for course in Course.objects.all():
                # Count actual confirmed allocations
                actual_count = Allocation.objects.filter(
                    course=course,
                    status='confirmed'
                ).count()
                
                # Check if there's a mismatch
                if course.enrolled_count != actual_count:
                    mismatches.append({
                        'code': course.code,
                        'title': course.title,
                        'old_count': course.enrolled_count,
                        'actual_count': actual_count,
                        'total_seats': course.total_seats
                    })
                    
                    # Update the enrolled count
                    course.enrolled_count = actual_count
                    course.save(update_fields=['enrolled_count'])
                    updated_count += 1
        
        # Display results
        if mismatches:
            self.stdout.write(self.style.WARNING(f'\nFound {len(mismatches)} course(s) with mismatched seat counts:\n'))
            for m in mismatches:
                self.stdout.write(
                    f"  • {m['code']} - {m['title']}\n"
                    f"    Old count: {m['old_count']} → Actual count: {m['actual_count']} "
                    f"(Total seats: {m['total_seats']})\n"
                )
            self.stdout.write(self.style.SUCCESS(f'\n✓ Updated {updated_count} course(s) successfully.\n'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ All course seat counts are already in sync. No updates needed.\n'))
