from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Counter(models.Model):
    name = models.CharField(max_length=50)
    is_free = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Token(models.Model):
    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('SERVING', 'Serving'),
        ('DONE', 'Done'),
        ('CANCELLED', 'Cancelled'),
        ('MISSED', 'Missed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    counter = models.ForeignKey(Counter, on_delete=models.SET_NULL, null=True, blank=True)
    token_number = models.IntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='WAITING')
    queue_date = models.DateField(default=date.today)   # 🔥 DAILY RESET KEY
    near_alert_sent = models.BooleanField(default=False)

    # ✅ NEW FIELDS FOR SLOT BOOKING / RESCHEDULE
    slot_start = models.TimeField(null=True, blank=True)
    slot_end = models.TimeField(null=True, blank=True)

    # ✅ Cancellation & reschedule tracking
    cancelled_at = models.DateTimeField(null=True, blank=True)
    rescheduled_from = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    served_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Token {self.token_number} ({self.queue_date})"
class CounterDelay(models.Model):
    counter = models.ForeignKey(Counter, on_delete=models.CASCADE)
    queue_date = models.DateField(default=date.today)
    extra_minutes = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.counter.name} Delay {self.extra_minutes} mins ({self.queue_date})"

