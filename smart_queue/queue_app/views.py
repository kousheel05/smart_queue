from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
from django.http import JsonResponse
from django.utils.timezone import now
from django.core.mail import send_mail
from .models import Token, Counter
from queue_app.sms import send_sms
from datetime import datetime
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from queue_app.sms import send_sms
from django.contrib import messages
from django.shortcuts import redirect
from .models import Token, Counter, CounterDelay
from django.db.models import Sum
from django.db.models import Sum
from .models import Token, Counter, CounterDelay
from django.shortcuts import render
import openpyxl
from django.http import HttpResponse
from django.db.models import Sum
from datetime import datetime, date, timedelta






# ===========================
# TIME ESTIMATION SETTINGS
# ===========================
AVG_SERVICE_TIME_PER_TOKEN = 10  # minutes per token




# ======================================================
# USER: BOOK TOKEN
# ======================================================
@login_required
def book_token(request):
    if request.method == 'POST':
        today = date.today()

        # Get last active token of today
        last_token = Token.objects.filter(
            queue_date=today
        ).order_by('-token_number').first()

        next_token_number = 1 if not last_token else last_token.token_number + 1

        # ✅ slot booking (optional)
        slot_start = request.POST.get("slot_start")  # "HH:MM"
        slot_start_time = None
        slot_end_time = None

        if slot_start:
            slot_start_time = datetime.strptime(slot_start, "%H:%M").time()
            slot_end_time = (datetime.combine(date.today(), slot_start_time) + timedelta(minutes=SLOT_MINUTES)).time()

            # Slot capacity validation
            booked = Token.objects.filter(
                queue_date=today,
                slot_start=slot_start_time
            ).exclude(status__in=['DONE', 'CANCELLED']).count()

            if booked >= SLOT_CAPACITY:
                messages.error(request, "Selected slot is full. Choose another slot.")
                return redirect("user_dashboard")

        # Create token
        token = Token.objects.create(
            user=request.user,
            token_number=next_token_number,
            status='WAITING',
            queue_date=today,
            slot_start=slot_start_time,
            slot_end=slot_end_time
        )

        profile = request.user.userprofile

        # EMAIL: Token Generated
        send_mail(
            subject='Smart Queue – Token Generated',
            message=(
                f'Hello {request.user.first_name},\n\n'
                f'Your token number is {token.token_number}.\n'
                f'Please wait until a counter is allocated.\n\n'
                f'Thank you,\nSmart Queue System'
            ),
            from_email=None,
            recipient_list=[request.user.email],
            fail_silently=True
        )

        # SMS: Token Generated
        send_sms(
            profile.phone_number,
            f"Smart Queue: Your token number is {token.token_number}. Please wait for counter allocation."
        )

        return redirect('user_dashboard')


# ======================================================
# ADMIN: CALL NEXT TOKEN
# ======================================================
def call_next_token(request):
    if request.method != 'POST':
        return redirect('admin_dashboard')

    
    today = date.today()

    # Find a free counter
    counter = Counter.objects.filter(is_free=True).first()
    if not counter:
        messages.error(request, "All counters are currently full")
        return redirect('admin_dashboard')

    # Find next waiting token
    token = Token.objects.filter(
        queue_date=today,
        status='WAITING'
    ).order_by('created_at').first()

    if not token:
        messages.warning(request, "No users waiting")
        return redirect('admin_dashboard')

    # Assign counter
    counter.is_free = False
    counter.save()

    token.status = 'SERVING'
    token.counter = counter
    token.served_at = now()
    token.save()

    messages.success(
        request,
        f"Token {token.token_number} assigned to {counter.name}"
    )

    profile = token.user.userprofile

    # EMAIL: Counter Allocated
    send_mail(
        subject='Smart Queue – Counter Allocated',
        message=(
            f'Hello {token.user.first_name},\n\n'
            f'Your token number {token.token_number} is now being served.\n'
            f'Please go to {counter.name}.\n\n'
            f'Thank you,\nSmart Queue System'
        ),
        from_email=None,
        recipient_list=[token.user.email],
        fail_silently=True
    )

    # SMS: Counter Allocated
    send_sms(
        profile.phone_number,
        f"Smart Queue: Token {token.token_number}. Please go to {counter.name}."
    )

    return redirect('admin_dashboard')


def free_counter(request, counter_id):
    if request.method != 'POST':
        return redirect('admin_dashboard')

    counter = Counter.objects.filter(id=counter_id).first()
    if counter:
        counter.is_free = True
        counter.save()

        # Remove serving token from that counter (optional safety)
        Token.objects.filter(counter=counter, status='SERVING').update(status='DONE', counter=None, served_at=None)

        messages.success(request, f"{counter.name} is now free.")

    return redirect('admin_dashboard')



# ======================================================
# USER: TOKEN STATUS (AJAX / POLLING)
# ======================================================
@login_required
def token_status(request):
    today = date.today()

    token = Token.objects.filter(
        user=request.user,
        queue_date=today
    ).order_by('-created_at').first()

    # No token or token completed
    if not token or token.status in ['DONE', 'CANCELLED']:
        return JsonResponse({'expired': True})

    queue_position = "--"
    wait_time = "--"
    expected_time = "--"
    near = False

    # ✅ WAITING
    if token.status == "WAITING":
        tokens_ahead = Token.objects.filter(
            queue_date=today,
            status="WAITING",
            token_number__lt=token.token_number
        ).count()

        queue_position = tokens_ahead + 1

        # ✅ Busy counters delay
        busy_counters = Counter.objects.filter(is_free=False)

        total_delay = CounterDelay.objects.filter(
            queue_date=today,
            counter__in=busy_counters
        ).aggregate(total=Sum("extra_minutes"))["total"] or 0

        wait_time = (tokens_ahead * AVG_SERVICE_TIME_PER_TOKEN) + total_delay

        expected_dt = datetime.now() + timedelta(minutes=wait_time)
        expected_time = expected_dt.strftime("%I:%M %p")

        # ✅ Feature 8: Near token alert
        near = tokens_ahead <= 2

        # ✅ send SMS only once
        if near and not token.near_alert_sent:
            profile = request.user.userprofile
            send_sms(
                profile.phone_number,
                f"Smart Queue Alert: Your token {token.token_number} will be served soon! Please be ready."
            )
            token.near_alert_sent = True
            token.save()

    # ✅ SERVING
    elif token.status == "SERVING":
        queue_position = 0
        wait_time = 0
        expected_time = "Now"
        near = False

    return JsonResponse({
        "token_number": token.token_number,
        "status": token.status,
        "counter": token.counter.name if token.counter else None,

        "queue_position": queue_position,
        "wait_time": wait_time,
        "expected_time": expected_time,

        # ✅ Feature 8
        "near": near
    })


# ======================================================
# SLOT SETTINGS (Feature 6)
# ======================================================
SLOT_START_HOUR = 10   # 10 AM
SLOT_END_HOUR = 17     # 5 PM
SLOT_MINUTES = 10      # 10 minute slot
SLOT_CAPACITY = 5      # max tokens per slot


def generate_slots():
    """
    Returns list of (slot_start, slot_end) time objects.
    """
    slots = []
    start = datetime.now().replace(hour=SLOT_START_HOUR, minute=0, second=0, microsecond=0)
    end = datetime.now().replace(hour=SLOT_END_HOUR, minute=0, second=0, microsecond=0)

    while start < end:
        slot_start = start.time()
        slot_end = (start + timedelta(minutes=SLOT_MINUTES)).time()
        slots.append((slot_start, slot_end))
        start += timedelta(minutes=SLOT_MINUTES)

    return slots


@login_required
def available_slots(request):
    """
    Returns available slots for the selected date.
    """
    selected_date = request.GET.get("date")
    if selected_date:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    else:
        selected_date = date.today()

    slots = generate_slots()
    slot_data = []

    for s, e in slots:
        booked = Token.objects.filter(
            queue_date=selected_date,
            slot_start=s,
        ).exclude(status__in=['CANCELLED', 'DONE']).count()

        slot_data.append({
            "slot_start": s.strftime("%H:%M"),
            "slot_end": e.strftime("%H:%M"),
            "booked": booked,
            "capacity": SLOT_CAPACITY,
            "available": booked < SLOT_CAPACITY
        })

    return JsonResponse({"date": str(selected_date), "slots": slot_data})


# ======================================================
# USER: CANCEL TOKEN (Feature 5)
# ======================================================
@login_required
def cancel_token(request):
    if request.method != "POST":
        return redirect("user_dashboard")

    today = date.today()

    token = Token.objects.filter(
        user=request.user,
        queue_date=today
    ).exclude(status__in=['DONE', 'CANCELLED']).order_by('-created_at').first()

    if not token:
        messages.error(request, "No active token found to cancel.")
        return redirect("user_dashboard")

    if token.status == 'SERVING':
        messages.error(request, "You cannot cancel while being served.")
        return redirect("user_dashboard")

    token.status = "CANCELLED"
    token.cancelled_at = now()
    token.save()

    messages.success(request, f"Token {token.token_number} cancelled successfully.")
    return redirect("user_dashboard")


# ======================================================
# USER: RESCHEDULE TOKEN (Feature 5 + 6)
# ======================================================
@login_required
def reschedule_token(request):
    """
    Reschedule active token to new date + slot.
    Expected POST:
    - date: YYYY-MM-DD
    - slot_start: HH:MM
    """
    if request.method != "POST":
        return redirect("user_dashboard")

    new_date = request.POST.get("date")
    slot_start = request.POST.get("slot_start")

    if not new_date or not slot_start:
        messages.error(request, "Please choose date and time slot.")
        return redirect("user_dashboard")

    new_date = datetime.strptime(new_date, "%Y-%m-%d").date()
    slot_start_time = datetime.strptime(slot_start, "%H:%M").time()

    # Find slot end
    slot_end_time = (datetime.combine(date.today(), slot_start_time) + timedelta(minutes=SLOT_MINUTES)).time()

    # Capacity check
    booked = Token.objects.filter(
        queue_date=new_date,
        slot_start=slot_start_time
    ).exclude(status__in=['CANCELLED', 'DONE']).count()

    if booked >= SLOT_CAPACITY:
        messages.error(request, "Selected slot is full. Choose another slot.")
        return redirect("user_dashboard")

    today = date.today()
    token = Token.objects.filter(
        user=request.user,
        queue_date=today
    ).exclude(status__in=['DONE', 'CANCELLED']).order_by('-created_at').first()

    if not token:
        messages.error(request, "No active token found to reschedule.")
        return redirect("user_dashboard")

    if token.status == "SERVING":
        messages.error(request, "You cannot reschedule while being served.")
        return redirect("user_dashboard")

    # Save old date
    token.rescheduled_from = token.queue_date

    # Update new schedule
    token.queue_date = new_date
    token.slot_start = slot_start_time
    token.slot_end = slot_end_time
    token.status = "WAITING"
    token.save()

    messages.success(request, f"Token rescheduled to {new_date} {slot_start}.")
    return redirect("user_dashboard")


# ======================================================
# ADMIN: ANALYTICS REPORT (Feature 7)
# ======================================================
def admin_analytics(request):
    """
    Returns queue analytics report (JSON).
    """
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    selected_date = request.GET.get("date")
    if selected_date:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    else:
        selected_date = date.today()

    tokens = Token.objects.filter(queue_date=selected_date)

    total = tokens.count()
    waiting = tokens.filter(status="WAITING").count()
    serving = tokens.filter(status="SERVING").count()
    done = tokens.filter(status="DONE").count()
    cancelled = tokens.filter(status="CANCELLED").count()

    # Peak slot
    peak_slot = (
        tokens.exclude(slot_start__isnull=True)
        .values("slot_start")
        .annotate(total=Count("id"))
        .order_by("-total")
        .first()
    )

    # Avg service time (DONE tokens: served_at - created_at)
    duration_expr = ExpressionWrapper(F("served_at") - F("created_at"), output_field=DurationField())
    avg_time = tokens.filter(status="DONE", served_at__isnull=False).annotate(d=duration_expr).aggregate(avg=Avg("d"))["avg"]

    return JsonResponse({
        "date": str(selected_date),
        "total_tokens": total,
        "waiting": waiting,
        "serving": serving,
        "done": done,
        "cancelled": cancelled,
        "peak_slot": peak_slot["slot_start"].strftime("%H:%M") if peak_slot else None,
        "avg_service_time": str(avg_time) if avg_time else None,
    })




@require_POST
def set_counter_status(request, counter_id):
    """
    Admin manually sets counter FREE or BUSY.
    If counter is set to FREE, mark serving token as DONE and send Thank You message.
    """
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    status = request.POST.get("status")  # "free" or "busy"

    counter = Counter.objects.filter(id=counter_id).first()
    if not counter:
        messages.error(request, "Counter not found.")
        return redirect("admin_dashboard")

    # -----------------------------------------
    # ✅ If Admin marks counter BUSY
    # -----------------------------------------
    if status == "busy":
        counter.is_free = False
        counter.save()
        messages.success(request, f"{counter.name} marked as BUSY.")
        return redirect("admin_dashboard")

    # -----------------------------------------
    # ✅ If Admin marks counter FREE
    # -----------------------------------------
    if status == "free":

    # Find currently serving token for this counter
        token = Token.objects.filter(counter=counter, status="SERVING").select_related("user").first()

    if token:
        profile = token.user.userprofile

        # Mark token done
        token.status = "DONE"
        token.counter = None
        token.served_at = None
        token.save()

        # ✅ EMAIL: Visit Completed
        send_mail(
            subject='Smart Queue – Visit Completed',
            message=(
                f'Hello {token.user.first_name},\n\n'
                f'Your visit for token number {token.token_number} has been completed.\n'
                f'Thank you for using Smart Queue.\n\n'
                f'Have a nice day!\n\n'
                f'Smart Queue Team'
            ),
            from_email=None,
            recipient_list=[token.user.email],
            fail_silently=True
        )

        # ✅ SMS: Visit Completed
        send_sms(
            profile.phone_number,
            "Smart Queue: Your visit is complete. Thank you and have a nice day!"
        )
    else:
        # ✅ No serving token exists, so don't crash
        messages.warning(request, f"{counter.name} has no active token to complete.")

    # ✅ Free counter always
    counter.is_free = True
    counter.save()

    # ✅ Reset delay after service completes / free click
    CounterDelay.objects.filter(counter=counter, queue_date=date.today()).update(extra_minutes=0)

    messages.success(request, f"{counter.name} marked as FREE.")
    return redirect("admin_dashboard")



    # -----------------------------------------
    # Invalid Status
    # -----------------------------------------
    messages.error(request, "Invalid status.")
    return redirect("admin_dashboard")
from django.views.decorators.http import require_POST

@require_POST
def add_counter_delay(request, counter_id):
    """
    Admin adds extra delay (+5 / +10 mins) to a counter.
    This delay will reflect in user dashboard wait time estimation.
    """
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    minutes = request.POST.get("minutes")
    try:
        minutes = int(minutes)
    except:
        minutes = 0

    if minutes not in [5, 10]:
        messages.error(request, "Invalid delay value.")
        return redirect("admin_dashboard")

    today = date.today()

    counter = Counter.objects.filter(id=counter_id).first()
    if not counter:
        messages.error(request, "Counter not found.")
        return redirect("admin_dashboard")

    delay_obj, created = CounterDelay.objects.get_or_create(
        counter=counter,
        queue_date=today,
        defaults={"extra_minutes": 0}
    )

    delay_obj.extra_minutes += minutes
    delay_obj.save()

    messages.success(request, f"{counter.name}: Extra {minutes} minutes added (Total Delay {delay_obj.extra_minutes} mins).")
    return redirect("admin_dashboard")


def display_board(request):
    return render(request, "display_board.html")


def display_data(request):
    today = date.today()

    serving = Token.objects.filter(queue_date=today, status="SERVING").select_related("counter").order_by("served_at")
    waiting = Token.objects.filter(queue_date=today, status="WAITING").order_by("created_at")[:12]

    serving_data = []
    for t in serving:
        serving_data.append({
            "token": t.token_number,
            "counter": t.counter.name if t.counter else "Counter"
        })

    waiting_list = [w.token_number for w in waiting]

    return JsonResponse({
        "serving": serving_data,
        "waiting": waiting_list
    })



def export_analytics_excel(request):
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    today = date.today()
    tokens = Token.objects.filter(queue_date=today).select_related("counter")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Analytics"

    ws.append(["Smart Queue Analytics Report"])
    ws.append(["Date", str(today)])
    ws.append([])

    ws.append(["Total", tokens.count()])
    ws.append(["Waiting", tokens.filter(status="WAITING").count()])
    ws.append(["Serving", tokens.filter(status="SERVING").count()])
    ws.append(["Done", tokens.filter(status="DONE").count()])
    ws.append(["Cancelled", tokens.filter(status="CANCELLED").count()])
    ws.append([])

    ws.append(["Token Number", "Status", "Counter"])
    for t in tokens:
        ws.append([t.token_number, t.status, t.counter.name if t.counter else "-"])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="analytics_{today}.xlsx"'
    wb.save(response)
    return response

@require_POST
def hold_token(request, token_id):
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    token = Token.objects.filter(id=token_id).select_related("counter").first()
    if token and token.status == "SERVING":
        token.status = "HOLD"
        token.save()
        messages.success(request, f"Token {token.token_number} put on HOLD.")
    return redirect("admin_dashboard")


@require_POST
def recall_token(request, token_id):
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    token = Token.objects.filter(id=token_id).select_related("counter", "user").first()
    if token and token.counter:
        profile = token.user.userprofile
        send_sms(profile.phone_number, f"Smart Queue Recall: Token {token.token_number}. Please go to {token.counter.name}.")
        send_mail(
            subject="Smart Queue – Recall",
            message=f"Hello {token.user.first_name},\n\nRecall: Please go to {token.counter.name} now.\nToken: {token.token_number}",
            from_email=None,
            recipient_list=[token.user.email],
            fail_silently=True
        )
        messages.success(request, f"Token {token.token_number} recalled.")
    return redirect("admin_dashboard")

@require_POST
def hold_token(request, token_id):
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    token = Token.objects.filter(id=token_id).select_related("counter").first()
    if token and token.status == "SERVING":
        token.status = "HOLD"
        token.save()
        messages.success(request, f"Token {token.token_number} put on HOLD.")
    return redirect("admin_dashboard")


@require_POST
def recall_token(request, token_id):
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    token = Token.objects.filter(id=token_id).select_related("counter", "user").first()
    if token and token.counter:
        profile = token.user.userprofile
        send_sms(profile.phone_number, f"Smart Queue Recall: Token {token.token_number}. Please go to {token.counter.name}.")
        send_mail(
            subject="Smart Queue – Recall",
            message=f"Hello {token.user.first_name},\n\nRecall: Please go to {token.counter.name} now.\nToken: {token.token_number}",
            from_email=None,
            recipient_list=[token.user.email],
            fail_silently=True
        )
        messages.success(request, f"Token {token.token_number} recalled.")
    return redirect("admin_dashboard")


@require_POST
def skip_token(request, token_id):
    if not request.session.get("is_admin"):
        return redirect("admin_login")

    token = Token.objects.filter(id=token_id).select_related("counter").first()
    if token and token.counter:
        counter = token.counter

        # mark token skipped
        token.status = "SKIPPED"
        token.counter = None
        token.served_at = None
        token.save()

        # free counter
        counter.is_free = True
        counter.save()

        messages.success(request, f"Token {token.token_number} skipped.")
    return redirect("admin_dashboard")

