from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('',                    views.home,              name='home'),
    path('catalog/',            views.catalog,           name='catalog'),
    path('courses/<str:code>/', views.course_detail,     name='course_detail'),
    # Auth
    path('login/',              views.login_view,        name='login'),
    path('logout/',             views.logout_view,       name='logout'),
    path('register/',           views.register_view,     name='register'),
    # Student
    path('dashboard/',          views.dashboard,         name='dashboard'),
    path('preferences/',        views.my_preferences,    name='my_preferences'),
    path('preferences/add/<int:course_id>/',    views.add_preference,    name='add_pref'),
    path('preferences/remove/<int:pref_id>/',  views.remove_preference, name='remove_pref'),
    path('preferences/reorder/', views.reorder_preferences, name='reorder_prefs'),
    # Waitlist
    path('waitlist/withdraw/<int:waitlist_id>/', views.withdraw_from_waitlist, name='withdraw_waitlist'),
    # Profile
    path('profile/',            views.profile_view,      name='profile'),
    path('profile/edit/',       views.edit_profile_view, name='edit_profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    # AJAX
    path('api/seats/<int:course_id>/', views.seat_api,      name='seat_api'),
    path('api/seats/',                 views.bulk_seat_api, name='bulk_seat_api'),
    # Admin
    path('admin-panel/',        views.admin_panel,       name='admin_panel'),
    path('admin/run/',          views.trigger_allocation,name='run_allocation'),
    path('admin/override/',     views.admin_override,    name='admin_override'),
    path('admin/increase-seats/', views.increase_course_seats, name='increase_seats'),
    path('admin/export/',       views.export_csv,        name='export_csv'),
    path('admin/analytics/',    views.analytics_api,     name='analytics_api'),
    path('admin/diagnostic/',   views.diagnostic_view,   name='diagnostic'),
    # CSV Upload
    path('admin/csv-upload/',   views.csv_upload_view,   name='csv_upload'),
    path('admin/sample/<str:file_type>/', views.download_sample_csv, name='download_sample'),
    path('admin/clear-data/',   views.clear_data_view,   name='clear_data'),
    # PDF Downloads
    path('download/allocation-pdf/', views.download_allocation_pdf, name='download_allocation_pdf'),
    path('admin/download/summary-pdf/', views.download_summary_pdf, name='download_summary_pdf'),
]
