"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from apps.pilgrims.api import (
    pilgrim_detail,
    pilgrim_list,
    pilgrim_stats,
    pilgrim_triage,
)
from apps.pilgrims.views import upload_test

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/live-translation/', include('apps.pilgrims.live_translation.urls')),
    path('api/pilgrims/', pilgrim_list, name='pilgrim_list'),
    # Must precede '<str:patient_id>/' so "stats" isn't captured as an id.
    path('api/pilgrims/stats/', pilgrim_stats, name='pilgrim_stats'),
    path('api/pilgrims/<str:patient_id>/triage/', pilgrim_triage, name='pilgrim_triage'),
    path('api/pilgrims/<str:patient_id>/', pilgrim_detail, name='pilgrim_detail'),
    path('', upload_test, name='upload_test'),
]
