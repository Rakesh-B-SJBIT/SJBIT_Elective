import csv
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from electives.models import Department, Student, Course


class Command(BaseCommand):
    help = 'Import data from CSV files'

    def add_arguments(self, parser):
        parser.add_argument('model', type=str, help='Model to import: departments, students, courses, admins')
        parser.add_argument('file', type=str, help='Path to CSV file')

    def handle(self, *args, **options):
        model_type = options['model'].lower()
        file_path = options['file']

        try:
            if model_type == 'departments':
                self.import_departments(file_path)
            elif model_type == 'students':
                self.import_students(file_path)
            elif model_type == 'courses':
                self.import_courses(file_path)
            elif model_type == 'admins':
                self.import_admins(file_path)
            else:
                raise CommandError(f'Unknown model type: {model_type}. Use: departments, students, courses, or admins')
        except FileNotFoundError:
            raise CommandError(f'File not found: {file_path}')
        except Exception as e:
            raise CommandError(f'Error importing data: {str(e)}')

    def import_departments(self, file_path):
        """Import departments from CSV"""
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                dept, created = Department.objects.get_or_create(
                    code=row['code'].strip().upper(),
                    defaults={'name': row['name'].strip()}
                )
                if created:
                    count += 1
                    self.stdout.write(self.style.SUCCESS(f'Created department: {dept.code} - {dept.name}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Department already exists: {dept.code}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nImported {count} new departments'))

    def import_students(self, file_path):
        """Import students from CSV"""
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    dept = Department.objects.get(code=row['department_code'].strip().upper())
                    
                    # Create or get user
                    username = row['student_id'].strip().lower()
                    user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'first_name': row['first_name'].strip(),
                            'last_name': row['last_name'].strip(),
                            'email': row['email'].strip()
                        }
                    )
                    
                    if user_created:
                        # Set password (use provided password or student_id as default)
                        password = row.get('password', '').strip() or row['student_id'].strip()
                        user.set_password(password)
                        user.save()
                    
                    # Create or get student
                    student, created = Student.objects.get_or_create(
                        user=user,
                        defaults={
                            'student_id': row['student_id'].strip().upper(),
                            'department': dept,
                            'semester': int(row['semester']),
                            'cgpa': float(row['cgpa'])
                        }
                    )
                    
                    if created:
                        count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'Created student: {student.student_id} - {user.get_full_name()}'
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'Student already exists: {student.student_id}'
                        ))
                
                except Department.DoesNotExist:
                    self.stdout.write(self.style.ERROR(
                        f'Department not found: {row["department_code"]}. Skipping student {row["student_id"]}'
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'Error importing student {row.get("student_id", "unknown")}: {str(e)}'
                    ))
        
        self.stdout.write(self.style.SUCCESS(f'\nImported {count} new students'))

    def import_courses(self, file_path):
        """Import courses from CSV"""
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    dept = Department.objects.get(code=row['department_code'].strip().upper())
                    
                    course, created = Course.objects.get_or_create(
                        code=row['code'].strip().upper(),
                        defaults={
                            'title': row['title'].strip(),
                            'description': row['description'].strip(),
                            'department': dept,
                            'category': row['category'].strip().lower(),
                            'level': row['level'].strip().lower(),
                            'credits': int(row['credits']),
                            'total_seats': int(row['total_seats']),
                            'for_semesters': row['for_semesters'].strip(),
                            'instructor': row.get('instructor', '').strip(),
                            'prerequisites': row.get('prerequisites', '').strip(),
                            'job_perspectives': row.get('job_perspectives', '').strip()
                        }
                    )
                    
                    if created:
                        count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'Created course: {course.code} - {course.title}'
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'Course already exists: {course.code}'
                        ))
                
                except Department.DoesNotExist:
                    self.stdout.write(self.style.ERROR(
                        f'Department not found: {row["department_code"]}. Skipping course {row["code"]}'
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'Error importing course {row.get("code", "unknown")}: {str(e)}'
                    ))
        
        self.stdout.write(self.style.SUCCESS(f'\nImported {count} new courses'))

    def import_admins(self, file_path):
        """Import admin users from CSV"""
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    user, created = User.objects.get_or_create(
                        username=row['username'].strip().lower(),
                        defaults={
                            'first_name': row['first_name'].strip(),
                            'last_name': row['last_name'].strip(),
                            'email': row['email'].strip(),
                            'is_staff': True,
                            'is_superuser': True
                        }
                    )
                    
                    if created:
                        user.set_password(row['password'].strip())
                        user.save()
                        count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'Created admin: {user.username} - {user.get_full_name()}'
                        ))
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'Admin already exists: {user.username}'
                        ))
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'Error importing admin {row.get("username", "unknown")}: {str(e)}'
                    ))
        
        self.stdout.write(self.style.SUCCESS(f'\nImported {count} new admins'))
