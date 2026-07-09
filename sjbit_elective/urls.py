from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Admin site customization
admin.site.site_header = "SJB Institute of Technology - Elective Management"
admin.site.site_title = "SJBIT Electives Admin"
admin.site.index_title = "Elective Opt-In System Administration"

urlpatterns = [
    path('', include('electives.urls')),
    path('admin/', admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
