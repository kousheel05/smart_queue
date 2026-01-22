from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from accounts.models import UserProfile
from queue_app.models import Counter, Token
from datetime import date
#from queue_app.views import auto_complete_tokens
# ---------------- ADMIN CREDENTIALS ----------------
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"


# ---------------- HOME ----------------
def home(request):
    return render(request, 'accounts/home.html')


# ---------------- USER SIGNUP ----------------
def user_signup(request):
    if request.method == 'POST':
        name = request.POST['name']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        phone = request.POST['phone']

        if not phone.startswith('+'):
            phone = '+91' + phone

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('login')

        if User.objects.filter(username=email).exists():
            messages.error(request, "Email already registered")
            return redirect('login')

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )

        UserProfile.objects.create(
            user=user,
            phone_number=phone
        )
        
        login(request, user)
        return redirect('user_dashboard')

    return redirect('login')


# ---------------- USER LOGIN ----------------
def user_login(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']

        print("LOGIN ATTEMPT:", email)  # 👈 DEBUG

        user = authenticate(request, username=email, password=password)

        if user:
            print("LOGIN SUCCESS")     # 👈 DEBUG
            login(request, user)
            return redirect('user_dashboard')
        else:
            print("LOGIN FAILED")      # 👈 DEBUG
            messages.error(request, "Invalid login credentials")
            return redirect('login')

    return render(request, 'accounts/login.html')



# ---------------- FORGOT PASSWORD ----------------
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST['email']

        if User.objects.filter(email=email).exists():
            messages.success(request, "Password reset link will be sent (demo)")
        else:
            messages.error(request, "Email not registered")

    return redirect('login')


# ---------------- ADMIN LOGIN (HARDCODED) ----------------
def admin_login(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            request.session['is_admin'] = True
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid admin credentials")

    return render(request, 'accounts/admin_login.html')



def admin_dashboard(request):
    if not request.session.get('is_admin'):
        return redirect('admin_login')

    # 🔥 THIS LINE IS CRITICAL
   

    today = date.today()

    counters = Counter.objects.all()

    serving_tokens = Token.objects.filter(
        queue_date=today,
        status='SERVING'
    ).select_related('counter')

    waiting_tokens = Token.objects.filter(
        queue_date=today,
        status='WAITING'
    )

    return render(request, 'accounts/admin_dashboard.html', {
        'counters': counters,
        'serving_tokens': serving_tokens,
        'waiting_tokens': waiting_tokens,
    })


# ---------------- USER DASHBOARD ----------------
@login_required
def user_dashboard(request):
    auto_complete_tokens()
    return render(request, 'accounts/user_dashboard.html')


# ---------------- LOGOUT ----------------
def logout_view(request):
    request.session.flush()   # clears admin session
    logout(request)           # clears user session
    return redirect('home')


from queue_app.models import Token

@login_required
def user_dashboard(request):
    # Get latest NON-DONE token only
    token = Token.objects.filter(
        user=request.user
    ).exclude(status='DONE').order_by('-created_at').first()

    queue_position = None
    wait_time = None

    if token and token.status == 'WAITING':
        queue_position = Token.objects.filter(
            status='WAITING',
            created_at__lt=token.created_at
        ).count() + 1
        wait_time = queue_position * 2

    return render(request, 'accounts/user_dashboard.html', {
        'token': token,
        'queue_position': queue_position,
        'wait_time': wait_time
    })
