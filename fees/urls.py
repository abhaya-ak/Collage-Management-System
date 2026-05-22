# fees/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FeeStructureViewSet,
    StudentFeeViewSet,
    PaymentViewSet,
)

router = DefaultRouter()
router.register(r'structures', FeeStructureViewSet, basename='fee-structure')
router.register(r'bills',      StudentFeeViewSet,   basename='student-fee')
router.register(r'payments',   PaymentViewSet,      basename='payment')

urlpatterns = [
    path('', include(router.urls)),
]