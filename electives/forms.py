from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Student, Department, Course


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Student ID / Username','autofocus':True}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Password'}))


class RegisterForm(forms.ModelForm):
    student_id = forms.CharField(max_length=20,
        widget=forms.TextInput(attrs={'class':'form-control','placeholder':'e.g. 1RV22CS001'}))
    department = forms.ModelChoiceField(queryset=Department.objects.all(),
        widget=forms.Select(attrs={'class':'form-select'}))
    semester = forms.ChoiceField(choices=[(i,f'Semester {i}') for i in range(1,9)],
        widget=forms.Select(attrs={'class':'form-select'}))
    cgpa = forms.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10,
        widget=forms.NumberInput(attrs={'class':'form-control','placeholder':'e.g. 8.75','step':'0.01'}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Create password'}))
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class':'form-control','placeholder':'Confirm password'}))

    class Meta:
        model  = User
        fields = ['first_name','last_name','username','email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class':'form-control','placeholder':'First name'}),
            'last_name':  forms.TextInput(attrs={'class':'form-control','placeholder':'Last name'}),
            'username':   forms.TextInput(attrs={'class':'form-control','placeholder':'Choose a username'}),
            'email':      forms.EmailInput(attrs={'class':'form-control','placeholder':'College email'}),
        }

    def clean_student_id(self):
        sid = self.cleaned_data['student_id']
        if Student.objects.filter(student_id=sid).exists():
            raise ValidationError('This Student ID is already registered.')
        return sid

    def clean_username(self):
        u = self.cleaned_data['username']
        if User.objects.filter(username=u).exists():
            raise ValidationError('Username already taken.')
        return u

    def clean(self):
        cd = super().clean()
        if cd.get('password') != cd.get('confirm_password'):
            raise ValidationError('Passwords do not match.')
        return cd


# ─── Course filters ───────────────────────────────────────────────────────────

class CourseFilterForm(forms.Form):
    q          = forms.CharField(required=False,
        widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Search courses, skills, roles…'}))
    category   = forms.ChoiceField(required=False,
        choices=[('','All Categories'),('professional','Professional'),('open','Open Elective'),('ability','Ability Enhancement')],
        widget=forms.Select(attrs={'class':'form-select'}))
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False, empty_label='All Departments',
        widget=forms.Select(attrs={'class':'form-select'}))
    level      = forms.ChoiceField(required=False,
        choices=[('','All Levels'),('beginner','Beginner'),('intermediate','Intermediate'),('advanced','Advanced')],
        widget=forms.Select(attrs={'class':'form-select'}))
    seats      = forms.BooleanField(required=False,
        widget=forms.CheckboxInput(attrs={'class':'form-check-input'}))

# ─── CSV Upload ───────────────────────────────────────────────────────────────

class CSVUploadForm(forms.Form):
    """Form for uploading CSV files"""
    IMPORT_CHOICES = [
        ('departments', 'Departments'),
        ('students', 'Students'),
        ('courses', 'Courses'),
        ('admins', 'Admin Users'),
    ]
    
    import_type = forms.ChoiceField(
        choices=IMPORT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        help_text='Upload a CSV file. Maximum size: 5MB'
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        if csv_file:
            # Check file size (5MB limit)
            if csv_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must be less than 5MB')
            
            # Check file extension
            if not csv_file.name.endswith('.csv'):
                raise forms.ValidationError('File must be a CSV file')
        
        return csv_file