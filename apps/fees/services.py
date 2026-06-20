"""
Fees service layer — all money mutations live here.

Key invariants (enforced here, not in models):
    paid_amount  = Σ (non-deleted) Payment.amount        (payments are the truth)
    due_amount   = max(payable - paid, 0)                 (never negative)
    payable      = total - discount - scholarship
    status       = PENDING | PARTIAL | PAID | OVERDUE | CANCELLED  (derived)

pay_fee() locks the StudentFee row (select_for_update) so concurrent payments
can't race the paid/due recomputation.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.enums import AuditEvent, FeeStatus, PaymentMethod
from apps.core.exceptions import InvalidOperation, ValidationException
from apps.core.services import log_audit
from apps.fees.models import (
    FeeComponent,
    FeeStructure,
    Payment,
    Receipt,
    StudentFee,
)

_ZERO = Decimal("0.00")


# =============================================================
# Internal: single source of truth for a StudentFee's money state
# =============================================================
def _recalculate(student_fee: StudentFee, *, save=True) -> StudentFee:
    """Recompute paid/due/status from the underlying payments. Returns the fee."""
    payable = student_fee.total_amount - student_fee.discount_amount - student_fee.scholarship_amount
    # Refunded payments don't count toward paid.
    paid = student_fee.payments.filter(is_refunded=False).aggregate(
        total=Sum("amount")
    )["total"] or _ZERO
    due = max(payable - paid, _ZERO)

    student_fee.paid_amount = paid
    student_fee.due_amount = due

    if student_fee.status != FeeStatus.CANCELLED:
        if payable > 0 and due == 0:
            student_fee.status = FeeStatus.PAID
        elif student_fee.due_date and student_fee.due_date < timezone.localdate():
            student_fee.status = FeeStatus.OVERDUE
        elif paid > 0:
            student_fee.status = FeeStatus.PARTIAL
        else:
            student_fee.status = FeeStatus.PENDING

    if save:
        student_fee.save(update_fields=["paid_amount", "due_amount", "status", "updated_at"])
    return student_fee


# =============================================================
# Fee structure & components
# =============================================================
def calculate_total_amount(fee_structure, *, save=True) -> Decimal:
    """Recompute total_amount = Σ (non-deleted) component amounts."""
    total = fee_structure.components.aggregate(t=Sum("amount"))["t"] or _ZERO
    if save and fee_structure.total_amount != total:
        fee_structure.total_amount = total
        fee_structure.save(update_fields=["total_amount", "updated_at"])
    return total


def _replace_components(structure, components):
    structure.components.all().delete()  # soft delete existing line items
    for comp in components:
        FeeComponent.objects.create(
            fee_structure=structure,
            name=comp["name"],
            amount=Decimal(str(comp["amount"])),
            is_optional=comp.get("is_optional", False),
        )


@transaction.atomic
def create_fee_structure(*, academic_year, program, semester, name, components=None,
                         description="", is_active=True, actor=None) -> FeeStructure:
    """Create a fee template + its components; total_amount = Σ components."""
    structure = FeeStructure.objects.create(
        academic_year=academic_year, program=program, semester=semester,
        name=name, description=description, is_active=is_active, total_amount=_ZERO,
    )
    _replace_components(structure, components or [])
    calculate_total_amount(structure)

    log_audit(action=AuditEvent.FEE_STRUCTURE_CREATED, actor=actor, instance=structure,
              metadata={"total": str(structure.total_amount), "components": len(components or [])})
    return structure


@transaction.atomic
def update_fee_structure(structure, *, name=None, description=None, is_active=None,
                         components=None, actor=None) -> FeeStructure:
    """Update structure fields and/or replace its components (recomputes total)."""
    changed = []
    if name is not None and name != structure.name:
        structure.name = name
        changed.append("name")
    if description is not None and description != structure.description:
        structure.description = description
        changed.append("description")
    if is_active is not None and is_active != structure.is_active:
        structure.is_active = is_active
        changed.append("is_active")
    structure.save()

    if components is not None:
        _replace_components(structure, components)
        calculate_total_amount(structure)
        changed.append("components")

    log_audit(action=AuditEvent.FEE_STRUCTURE_UPDATED, actor=actor, instance=structure,
              metadata={"changed": changed, "total": str(structure.total_amount)})
    return structure


# =============================================================
# Student fee generation
# =============================================================
@transaction.atomic
def generate_student_fee(*, student, fee_structure, due_date=None, actor=None) -> StudentFee:
    """Charge a fee structure to a student (snapshots the amount)."""
    # One fee record per term (academic_year + program + semester).
    if StudentFee.objects.filter(
        student=student,
        academic_year=fee_structure.academic_year,
        program=fee_structure.program,
        semester=fee_structure.semester,
    ).exists():
        raise InvalidOperation(
            "This student already has a fee for this academic year / program / semester."
        )

    fee = StudentFee.objects.create(
        student=student,
        academic_year=fee_structure.academic_year,
        program=fee_structure.program,
        semester=fee_structure.semester,
        fee_structure=fee_structure,
        total_amount=fee_structure.total_amount,
        due_date=due_date,
    )
    _recalculate(fee)  # sets due_amount = total, status = PENDING
    log_audit(action=AuditEvent.STUDENT_FEE_GENERATED, actor=actor, instance=fee,
              metadata={"student_id": student.student_id, "total": str(fee.total_amount)})
    return fee


# =============================================================
# Discounts & scholarships
# =============================================================
def _validate_reduction(fee, *, discount, scholarship):
    if discount < 0 or scholarship < 0:
        raise ValidationException("Amount cannot be negative.")
    if discount + scholarship > fee.total_amount:
        raise ValidationException("Discount + scholarship cannot exceed the total fee.")


@transaction.atomic
def apply_discount(student_fee: StudentFee, amount, actor=None) -> StudentFee:
    amount = Decimal(str(amount))
    _validate_reduction(student_fee, discount=amount, scholarship=student_fee.scholarship_amount)
    student_fee.discount_amount = amount
    student_fee.save(update_fields=["discount_amount", "updated_at"])
    _recalculate(student_fee)
    log_audit(action=AuditEvent.DISCOUNT_APPLIED, actor=actor, instance=student_fee,
              metadata={"discount": str(amount)})
    return student_fee


@transaction.atomic
def apply_scholarship(student_fee: StudentFee, amount, actor=None) -> StudentFee:
    amount = Decimal(str(amount))
    _validate_reduction(student_fee, discount=student_fee.discount_amount, scholarship=amount)
    student_fee.scholarship_amount = amount
    student_fee.save(update_fields=["scholarship_amount", "updated_at"])
    _recalculate(student_fee)
    log_audit(action=AuditEvent.SCHOLARSHIP_APPLIED, actor=actor, instance=student_fee,
              metadata={"scholarship": str(amount)})
    return student_fee


# =============================================================
# Receipt numbering — SERVICE-ONLY (RCPT-YYYY-XXXX)
# =============================================================
def generate_receipt_number(year: int) -> str:
    prefix = f"RCT-{year}-"
    last = (
        Receipt.all_objects.select_for_update()
        .filter(receipt_number__startswith=prefix)
        .order_by("-receipt_number")
        .first()
    )
    next_seq = (int(last.receipt_number.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{next_seq:04d}"


@transaction.atomic
def generate_receipt(payment, *, actor=None) -> Receipt:
    """Create the proof-of-payment receipt for a payment (RCT-YYYY-XXXX) + audit."""
    existing = Receipt.objects.filter(payment=payment).first()
    if existing:
        return existing
    receipt = Receipt.objects.create(
        payment=payment,
        receipt_number=generate_receipt_number(timezone.now().year),
        amount=payment.amount,
    )
    log_audit(action=AuditEvent.RECEIPT_GENERATED, actor=actor, instance=receipt,
              metadata={"payment_id": str(payment.pk), "amount": str(payment.amount),
                        "receipt": receipt.receipt_number})
    return receipt


# =============================================================
# pay_fee — the most important service
# =============================================================
@transaction.atomic
def pay_fee(*, student_fee, amount, payment_method, reference_number="", remarks="",
            actor=None) -> Payment:
    """
    Record a payment against a StudentFee:
      validate -> create Payment -> recompute paid/due/status -> generate Receipt -> audit
    """
    amount = Decimal(str(amount))

    # Lock the fee row so concurrent payments serialize.
    fee = StudentFee.objects.select_for_update().get(pk=student_fee.pk)

    if fee.status == FeeStatus.CANCELLED:
        raise InvalidOperation("This fee has been cancelled; payments are not allowed.")
    if amount <= 0:
        raise ValidationException("Payment amount must be greater than zero.")
    if payment_method not in PaymentMethod.values:
        raise ValidationException("Invalid payment method.")

    # Recompute current outstanding from truth, then guard overpayment.
    _recalculate(fee)
    if amount > fee.due_amount:
        raise ValidationException(
            f"Payment ({amount}) exceeds the outstanding due ({fee.due_amount})."
        )

    payment = Payment.objects.create(
        student_fee=fee,
        amount=amount,
        payment_method=payment_method,
        reference_number=reference_number,
        remarks=remarks,
        paid_by=actor if getattr(actor, "pk", None) else None,
        paid_at=timezone.now(),
    )

    _recalculate(fee)  # paid_amount += this payment, due/status updated

    log_audit(action=AuditEvent.PAYMENT_RECEIVED, actor=actor, instance=fee,
              metadata={"payment_id": str(payment.pk), "amount": str(amount),
                        "method": payment_method, "new_status": fee.status,
                        "due_after": str(fee.due_amount)})
    generate_receipt(payment, actor=actor)
    return payment


@transaction.atomic
def refund_payment(payment, *, reason="", actor=None) -> Payment:
    """Refund a payment: mark it refunded, recompute the fee, audit."""
    if payment.is_refunded:
        raise InvalidOperation("This payment has already been refunded.")

    payment.is_refunded = True
    payment.refunded_at = timezone.now()
    payment.refunded_by = actor if getattr(actor, "pk", None) else None
    payment.refund_reason = reason
    payment.save(update_fields=["is_refunded", "refunded_at", "refunded_by",
                                "refund_reason", "updated_at"])

    fee = StudentFee.objects.select_for_update().get(pk=payment.student_fee_id)
    _recalculate(fee)  # paid_amount drops by the refunded amount

    log_audit(action=AuditEvent.PAYMENT_REFUNDED, actor=actor, instance=fee,
              metadata={"payment_id": str(payment.pk), "amount": str(payment.amount),
                        "reason": reason, "new_status": fee.status})
    return payment


# =============================================================
# Maintenance: flag overdue fees (e.g. nightly cron)
# =============================================================
@transaction.atomic
def refresh_overdue():
    """Re-evaluate status for all open fees so past-due ones become OVERDUE."""
    open_fees = StudentFee.objects.filter(
        status__in=[FeeStatus.PENDING, FeeStatus.PARTIAL, FeeStatus.OVERDUE]
    )
    count = 0
    for fee in open_fees:
        before = fee.status
        _recalculate(fee)
        count += int(fee.status != before)
    return count
