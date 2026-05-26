# dashboard/views.py

from rest_framework.response import Response
from rest_framework.views import APIView

from auth_core.permissions import IsAdminRole

from .services import DashboardService
from .serializers import DashboardOverviewSerializer


class DashboardOverviewView(APIView):
    """
    GET /api/v1/dashboard/overview/

    Admin-only. Returns aggregated metrics from all domain apps in one response.

    Query count: 5 (one per domain — students, attendance, fees, feedback, notices).
    No N+1. No raw SQL.
    """
    permission_classes = [IsAdminRole]

    def get(self, request):
        data       = DashboardService.get_overview()
        serializer = DashboardOverviewSerializer(data)
        return Response(serializer.data)
