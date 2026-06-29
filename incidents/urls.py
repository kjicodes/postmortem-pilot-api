from django.urls import path, include
from rest_framework.routers import DefaultRouter
from incidents.views import IncidentViewSet, DocumentViewSet, PatternReportViewSet


router = DefaultRouter()
router.register('incidents', IncidentViewSet)
router.register('documents', DocumentViewSet)
router.register('patterns', PatternReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
]