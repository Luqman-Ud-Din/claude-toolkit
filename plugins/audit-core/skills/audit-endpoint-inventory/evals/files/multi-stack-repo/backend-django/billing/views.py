from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Invoice
from .serializers import InvoiceSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_list(request):
    company_id = request.GET.get("company_id")
    rows = Invoice.objects.filter(company_id=company_id)
    return Response(InvoiceSerializer(rows, many=True).data)
