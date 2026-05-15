from django.db import models 

class Notice(models.Model):
    TYPE_CHOICES = (
        ('fee', 'Fee'),
        ('exam', 'Exam'),
        ('holiday', 'Holiday'),
        ('emergency', 'Emergency'),
    )
    
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    content = models.TextField()
    
    # auto_now_add=True automatically sets this to the exact date/time it was created
    date_posted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_type_display()}] {self.title}"