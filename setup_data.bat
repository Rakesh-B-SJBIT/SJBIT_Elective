@echo off
echo Setting up SJBIT Elective System Data...
echo.

echo 1. Importing departments...
python manage.py import_csv departments your_departments.csv
echo.

echo 2. Importing admins...
python manage.py import_csv admins your_admins.csv
echo.

echo 3. Importing students...
python manage.py import_csv students your_students.csv
echo.

echo 4. Importing courses...
python manage.py import_csv courses your_courses.csv
echo.

echo Data import completed!
pause