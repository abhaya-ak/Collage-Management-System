"""Permission maps (action -> permission code) for fees viewsets."""

FEE_STRUCTURE_PERMISSIONS = {
    "list": "view_fee_structure",
    "retrieve": "view_fee_structure",
    "create": "manage_fee_structure",
    "update": "manage_fee_structure",
    "partial_update": "manage_fee_structure",
    "destroy": "manage_fee_structure",
}

STUDENT_FEE_PERMISSIONS = {
    "list": "view_student_fee",
    "retrieve": "view_student_fee",
    "dashboard": "view_student_fee",
    "generate": "generate_student_fee",
    "apply_discount": "apply_scholarship",
    "apply_scholarship": "apply_scholarship",
}

PAYMENT_PERMISSIONS = {
    "list": "view_payment",
    "retrieve": "view_payment",
    "pay": "pay_fee",
    "refund": "refund_payment",
}

RECEIPT_PERMISSIONS = {
    "list": "view_receipt",
    "retrieve": "view_receipt",
}
