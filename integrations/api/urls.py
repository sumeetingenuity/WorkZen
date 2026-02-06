"""
API URL configuration.
"""
from django.urls import path
from integrations.api.views import api

urlpatterns = [
    path('v1/', api.urls),
]
