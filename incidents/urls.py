from django.urls import path, include
from rest_framework.routers import DefaultRouter
from incidents.views import IncidentViewSet


router = DefaultRouter()
router.register('incidents', IncidentViewSet)


urlpatterns = [
    path('', include(router.urls)),
]