# dashboard/views.py

from rest_framework.response import Response
from rest_framework.views import APIView

from auth_core.permissions import IsAdminRole
from .services import DashboardService
from .serializers import DashboardOverviewSerializer


class DashboardOverviewView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        data       = DashboardService.get_overview()
        serializer = DashboardOverviewSerializer(data)
        return Response(serializer.data)