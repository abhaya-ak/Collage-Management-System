from rest_framework import serializers
from .models import Payment

class FeePaymentWriteSerializer(serializers.ModelSerializer):
    """
    Contract for POST /api/v1/fees/pay/
    Accepts: {"student": 5, "amount": 1500.00, "payment_method": "CARD", "transaction_id": "TXN98765"}
    """
    class Meta:
        model = Payment
        # Notice we exclude 'payment_date' and 'status'. 
        # The database handles the date, and the status should default to PENDING or COMPLETED 
        # via backend logic, not frontend input (to prevent users from hacking a "COMPLETED" status).
        fields = ['student', 'amount', 'payment_method', 'transaction_id']

class FeePaymentReadSerializer(serializers.ModelSerializer):
    """
    Contract for GET /api/v1/fees/student/{id}/
    Returns a clean receipt-style format for the UI.
    """
    # Converting the internal "CARD" code to a readable "Credit/Debit Card" for the UI
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'amount', 'payment_method_display', 'transaction_id', 'payment_date', 'status_display']