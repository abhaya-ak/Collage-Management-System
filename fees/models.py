from django.db import models
from students.models import Student
# 10) FeeStructure
class FeeStructure(models.Model):
    course = models.CharField(max_length=100)
    year = models.IntegerField()
    
    # Always use DecimalField for money! FloatField can cause weird rounding 
    # errors in databases (like 99.9999999 instead of 100.00).
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.course} (Year {self.year}) - Rs. {self.amount}"

class StudentFee(models.Model):
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('due', 'Due'),
        ('overdue', 'Overdue'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='due')

    def __str__(self):
        return f"{self.student.roll_no} - Total: Rs.{self.total_amount} | Due: Rs.{self.due_amount} ({self.get_status_display()})"

class Payment(models.Model):
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE)
    
    # upload_to specifies the folder inside your MEDIA_ROOT where images will be saved
    screenshot = models.ImageField(upload_to='payment_receipts/')
    
    # remark is text, but we use blank=True, null=True so the student isn't forced to write one
    remark = models.TextField(blank=True, null=True)
    verified = models.BooleanField(default=False)

    def __str__(self):
        status = "Verified" if self.verified else "Pending Verification"
        return f"Payment for {self.student_fee.student.roll_no} - {status}"