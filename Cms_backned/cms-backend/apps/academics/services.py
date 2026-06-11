"""
Services — write-side business logic for academics.

Generic create/update helpers cover the simple models; AcademicYear has a
special rule (only one row may be current) handled explicitly.
"""

from django.db import transaction

from apps.academics.models import AcademicYear


# --- generic helpers --------------------------------------------------------
@transaction.atomic
def create_instance(model, validated_data):
    return model.objects.create(**validated_data)


@transaction.atomic
def update_instance(instance, validated_data):
    for field, value in validated_data.items():
        setattr(instance, field, value)
    instance.save()
    return instance


# --- AcademicYear: enforce a single current year ----------------------------
@transaction.atomic
def create_academic_year(validated_data):
    if validated_data.get("is_current"):
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
    return AcademicYear.objects.create(**validated_data)


@transaction.atomic
def update_academic_year(instance, validated_data):
    if validated_data.get("is_current"):
        AcademicYear.objects.exclude(pk=instance.pk).filter(is_current=True).update(
            is_current=False
        )
    for field, value in validated_data.items():
        setattr(instance, field, value)
    instance.save()
    return instance
