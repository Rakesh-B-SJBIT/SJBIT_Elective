"""
CSV Import functionality for SJB Institute Elective System
Handles bulk import of departments, students, courses, and admin users
"""

import csv
import io
import pandas as pd
from django.contrib.auth.models import User
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
from .models import Department, Student, Course


class CSVImportError(Exception):
    """Custom exception for CSV import errors"""
    pass


class CSVImporter:
    """Handles CSV import operations with validation and error handling"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.skip_count = 0
    
    def validate_csv_structure(self, df, required_columns):
        """Validate that CSV has required columns"""
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            raise CSVImportError(f"Missing required columns: {', '.join(missing_columns)}")
    
    def clean_string(self, value):
        """Clean and validate string values"""
        if pd.isna(value):
            return ""
        return str(value).strip()
    
    def clean_email(self, email):
        """Clean and validate email"""
        email = self.clean_string(email).lower()
        if email and '@' not in email:
            raise ValidationError(f"Invalid email format: {email}")
        return email
    
    def clean_numeric(self, value, field_name, min_val=None, max_val=None):
        """Clean and validate numeric values"""
        if pd.isna(value):
            raise ValidationError(f"{field_name} is required")
        
        try:
            num_val = float(value)
            if min_val is not None and num_val < min_val:
                raise ValidationError(f"{field_name} must be >= {min_val}")
            if max_val is not None and num_val > max_val:
                raise ValidationError(f"{field_name} must be <= {max_val}")
            return num_val
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid {field_name}: {value}")
    
    @transaction.atomic
    def import_departments(self, csv_file):
        """Import departments from CSV"""
        try:
            df = pd.read_csv(csv_file)
            self.validate_csv_structure(df, ['code', 'name'])
            
            for index, row in df.iterrows():
                try:
                    code = self.clean_string(row['code']).upper()
                    name = self.clean_string(row['name'])
                    
                    if not code or not name:
                        self.errors.append(f"Row {index + 2}: Code and name are required")
                        continue
                    
                    dept, created = Department.objects.get_or_create(
                        code=code,
                        defaults={'name': name}
                    )
                    
                    if created:
                        self.success_count += 1
                    else:
                        self.skip_count += 1
                        self.warnings.append(f"Department {code} already exists, skipped")
                        
                except Exception as e:
                    self.errors.append(f"Row {index + 2}: {str(e)}")
            
            return self.success_count, self.skip_count, self.errors, self.warnings
            
        except Exception as e:
            raise CSVImportError(f"Failed to process departments CSV: {str(e)}")
    
    @transaction.atomic
    def import_students(self, csv_file):
        """Import students from CSV"""
        try:
            df = pd.read_csv(csv_file)
            required_cols = ['student_id', 'first_name', 'last_name', 'email', 'department_code', 'semester', 'cgpa']
            self.validate_csv_structure(df, required_cols)
            
            for index, row in df.iterrows():
                try:
                    student_id = self.clean_string(row['student_id']).upper()
                    first_name = self.clean_string(row['first_name'])
                    last_name = self.clean_string(row['last_name'])
                    email = self.clean_email(row['email'])
                    dept_code = self.clean_string(row['department_code']).upper()
                    semester = int(self.clean_numeric(row['semester'], 'semester', 1, 8))
                    cgpa = self.clean_numeric(row['cgpa'], 'CGPA', 0.0, 10.0)
                    password = self.clean_string(row.get('password', '')) or student_id.lower()
                    
                    if not all([student_id, first_name, last_name, email, dept_code]):
                        self.errors.append(f"Row {index + 2}: Required fields missing")
                        continue
                    
                    # Check if department exists
                    try:
                        department = Department.objects.get(code=dept_code)
                    except Department.DoesNotExist:
                        self.errors.append(f"Row {index + 2}: Department {dept_code} not found")
                        continue
                    
                    # Create or get user
                    username = student_id.lower()
                    user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'first_name': first_name,
                            'last_name': last_name,
                            'email': email,
                            'is_staff': False,
                            'is_active': True
                        }
                    )
                    
                    if user_created:
                        user.set_password(password)
                        user.save()
                    
                    # Create or get student
                    student, student_created = Student.objects.get_or_create(
                        user=user,
                        defaults={
                            'student_id': student_id,
                            'department': department,
                            'semester': semester,
                            'cgpa': cgpa
                        }
                    )
                    
                    if student_created:
                        self.success_count += 1
                    else:
                        self.skip_count += 1
                        self.warnings.append(f"Student {student_id} already exists, skipped")
                        
                except Exception as e:
                    self.errors.append(f"Row {index + 2}: {str(e)}")
            
            return self.success_count, self.skip_count, self.errors, self.warnings
            
        except Exception as e:
            raise CSVImportError(f"Failed to process students CSV: {str(e)}")
    
    @transaction.atomic
    def import_courses(self, csv_file):
        """Import courses from CSV"""
        try:
            df = pd.read_csv(csv_file)
            required_cols = ['code', 'title', 'description', 'department_code', 'category', 
                           'level', 'credits', 'total_seats', 'for_semesters']
            self.validate_csv_structure(df, required_cols)
            
            valid_categories = ['professional', 'open', 'ability']
            valid_levels = ['ug', 'pg']
            
            for index, row in df.iterrows():
                try:
                    code = self.clean_string(row['code']).upper()
                    title = self.clean_string(row['title'])
                    description = self.clean_string(row['description'])
                    dept_code = self.clean_string(row['department_code']).upper()
                    category = self.clean_string(row['category']).lower()
                    level = self.clean_string(row['level']).lower()
                    credits = int(self.clean_numeric(row['credits'], 'credits', 1, 4))
                    total_seats = int(self.clean_numeric(row['total_seats'], 'total_seats', 1))
                    for_semesters = self.clean_string(row['for_semesters'])
                    
                    # Optional fields
                    instructor = self.clean_string(row.get('instructor', ''))
                    prerequisites = self.clean_string(row.get('prerequisites', ''))
                    career_paths = self.clean_string(row.get('career_paths', ''))
                    
                    if not all([code, title, description, dept_code, category, level, for_semesters]):
                        self.errors.append(f"Row {index + 2}: Required fields missing")
                        continue
                    
                    if category not in valid_categories:
                        self.errors.append(f"Row {index + 2}: Invalid category '{category}'. Must be: {', '.join(valid_categories)}")
                        continue
                    
                    if level not in valid_levels:
                        self.errors.append(f"Row {index + 2}: Invalid level '{level}'. Must be: {', '.join(valid_levels)}")
                        continue
                    
                    # Check if department exists
                    try:
                        department = Department.objects.get(code=dept_code)
                    except Department.DoesNotExist:
                        self.errors.append(f"Row {index + 2}: Department {dept_code} not found")
                        continue
                    
                    # Validate for_semesters format
                    try:
                        semesters = [int(s.strip()) for s in for_semesters.split(',')]
                        if not all(1 <= s <= 8 for s in semesters):
                            raise ValueError("Semesters must be between 1 and 8")
                    except ValueError as e:
                        self.errors.append(f"Row {index + 2}: Invalid for_semesters format: {e}")
                        continue
                    
                    # Create or get course
                    course, created = Course.objects.get_or_create(
                        code=code,
                        defaults={
                            'title': title,
                            'description': description,
                            'department': department,
                            'category': category,
                            'level': level,
                            'credits': credits,
                            'total_seats': total_seats,
                            'enrolled_count': 0,
                            'for_semesters': for_semesters,
                            'instructor': instructor,
                            'prerequisites': prerequisites,
                            'job_perspectives': career_paths,
                            'is_active': True
                        }
                    )
                    
                    if created:
                        self.success_count += 1
                    else:
                        self.skip_count += 1
                        self.warnings.append(f"Course {code} already exists, skipped")
                        
                except Exception as e:
                    self.errors.append(f"Row {index + 2}: {str(e)}")
            
            return self.success_count, self.skip_count, self.errors, self.warnings
            
        except Exception as e:
            raise CSVImportError(f"Failed to process courses CSV: {str(e)}")
    
    @transaction.atomic
    def import_admins(self, csv_file):
        """Import admin users from CSV"""
        try:
            df = pd.read_csv(csv_file)
            required_cols = ['username', 'email', 'first_name', 'last_name', 'password']
            self.validate_csv_structure(df, required_cols)
            
            for index, row in df.iterrows():
                try:
                    username = self.clean_string(row['username']).lower()
                    email = self.clean_email(row['email'])
                    first_name = self.clean_string(row['first_name'])
                    last_name = self.clean_string(row['last_name'])
                    password = self.clean_string(row['password'])
                    
                    if not all([username, email, first_name, last_name, password]):
                        self.errors.append(f"Row {index + 2}: All fields are required")
                        continue
                    
                    # Create or get admin user
                    user, created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'email': email,
                            'first_name': first_name,
                            'last_name': last_name,
                            'is_staff': True,
                            'is_superuser': True,
                            'is_active': True
                        }
                    )
                    
                    if created:
                        user.set_password(password)
                        user.save()
                        self.success_count += 1
                    else:
                        self.skip_count += 1
                        self.warnings.append(f"Admin user {username} already exists, skipped")
                        
                except Exception as e:
                    self.errors.append(f"Row {index + 2}: {str(e)}")
            
            return self.success_count, self.skip_count, self.errors, self.warnings
            
        except Exception as e:
            raise CSVImportError(f"Failed to process admins CSV: {str(e)}")


def process_csv_import(import_type, csv_file, request=None):
    """
    Process CSV import and return results
    
    Args:
        import_type: 'departments', 'students', 'courses', or 'admins'
        csv_file: File object or file path
        request: Django request object for messages (optional)
    
    Returns:
        dict: Results with success_count, skip_count, errors, warnings
    """
    importer = CSVImporter()
    
    try:
        if import_type == 'departments':
            success, skip, errors, warnings = importer.import_departments(csv_file)
        elif import_type == 'students':
            success, skip, errors, warnings = importer.import_students(csv_file)
        elif import_type == 'courses':
            success, skip, errors, warnings = importer.import_courses(csv_file)
        elif import_type == 'admins':
            success, skip, errors, warnings = importer.import_admins(csv_file)
        else:
            raise CSVImportError(f"Invalid import type: {import_type}")
        
        # Add messages if request provided
        if request:
            if success > 0:
                messages.success(request, f"Successfully imported {success} {import_type}")
            if skip > 0:
                messages.warning(request, f"Skipped {skip} existing {import_type}")
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.error(request, error)
                if len(errors) > 5:
                    messages.error(request, f"... and {len(errors) - 5} more errors")
        
        return {
            'success': True,
            'success_count': success,
            'skip_count': skip,
            'errors': errors,
            'warnings': warnings,
            'total_processed': success + skip + len(errors)
        }
        
    except CSVImportError as e:
        if request:
            messages.error(request, str(e))
        return {
            'success': False,
            'error': str(e),
            'success_count': 0,
            'skip_count': 0,
            'errors': [str(e)],
            'warnings': []
        }
    except Exception as e:
        error_msg = f"Unexpected error during {import_type} import: {str(e)}"
        if request:
            messages.error(request, error_msg)
        return {
            'success': False,
            'error': error_msg,
            'success_count': 0,
            'skip_count': 0,
            'errors': [error_msg],
            'warnings': []
        }