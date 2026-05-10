from django.core.exceptions import ValidationError, ObjectDoesNotExist
from .models import Subject
from users.models import Teacher  # Assuming Teacher is in a users app or similar

def create_subject(*, name: str, course: str, code: str, teacher_id: int = None) -> Subject:
    """
    Creates a new Subject. Enforces unique code and validates the teacher.
    """
    # 1. Unique Code Check
    if Subject.objects.filter(code=code).exists():
        raise ValidationError({"code": f"A subject with the code '{code}' already exists."})

    # 2. Teacher Relation Handling
    teacher = None
    if teacher_id:
        try:
            teacher = Teacher.objects.get(id=teacher_id)
        except Teacher.DoesNotExist:
            raise ValidationError({"teacher": f"Teacher with ID {teacher_id} does not exist."})

    # 3. Creation
    subject = Subject.objects.create(
        name=name,
        course=course,
        code=code,
        teacher=teacher
    )
    
    return subject

def update_subject(*, subject: Subject, **data) -> Subject:
    """
    Partially updates a Subject. Validates code uniqueness and teacher existence.
    """
    # 1. Unique Code Check (Ensure we don't conflict with OTHER subjects)
    new_code = data.get('code')
    if new_code and new_code != subject.code:
        if Subject.objects.filter(code=new_code).exclude(id=subject.id).exists():
            raise ValidationError({"code": f"A subject with the code '{new_code}' already exists."})

    # 2. Teacher Relation Handling
    if 'teacher_id' in data:
        teacher_id = data.pop('teacher_id')
        if teacher_id is None:
            subject.teacher = None  # Allow unassigning a teacher
        else:
            try:
                subject.teacher = Teacher.objects.get(id=teacher_id)
            except Teacher.DoesNotExist:
                raise ValidationError({"teacher": f"Teacher with ID {teacher_id} does not exist."})

    # 3. Update remaining fields dynamically
    for field, value in data.items():
        if hasattr(subject, field):
            setattr(subject, field, value)

    # Save to database
    subject.save()
    
    return subject

def delete_subject(*, subject: Subject) -> None:
    """
    Deletes a Subject.
    """
    # You could add logic here (e.g., checking if the subject has active routines
    # before allowing deletion), but for now, we just delete it.
    subject.delete()

def get_subject(*, subject_id: int) -> Subject:
    """
    Fetches a single Subject by ID.
    """
    try:
        return Subject.objects.get(id=subject_id)
    except Subject.DoesNotExist:
        raise ObjectDoesNotExist(f"Subject with ID {subject_id} not found.")

def list_subjects() -> list[Subject]:
    """
    Returns a queryset of all subjects.
    """
    # Using select_related optimizes the database query by fetching 
    # the related teacher in the same SQL call, preventing N+1 query issues.
    return Subject.objects.select_related('teacher', 'teacher__user').all()

def get_subjects_by_teacher(*, teacher_id: int) -> list[Subject]:
    """
    Returns a queryset of subjects taught by a specific teacher.
    """
    return Subject.objects.select_related('teacher', 'teacher__user').filter(teacher_id=teacher_id)