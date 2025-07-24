from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .forms import CustomerSignupForm, TrainerSignupForm
from .models import Trainer, Profile, Customer
from django.contrib.auth.models import User
import random

# views.py
import random, datetime
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib import messages

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import re
from .models import TrainerRegistration

from . import trainer_dashboard_views

from django.contrib.auth.decorators import login_required


@csrf_protect
def trainer_signup(request):
    """Handle trainer registration"""
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        
        # Validation
        errors = []
        
        # Username validation (letters and spaces only)
        if not re.match(r'^[a-zA-Z ]+$', username):
            errors.append("Username can only contain letters and spaces.")
        
        # Email validation
        try:
            validate_email(email)
            if not re.match(r'^[\w.-]+@(gmail|yahoo|hotmail)\.com$', email):
                errors.append("Email must be from gmail.com, yahoo.com, or hotmail.com")
        except ValidationError:
            errors.append("Please enter a valid email address.")
        
        # Password validation
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        
        if password != password2:
            errors.append("Passwords do not match.")
        
        # Phone validation
        if not re.match(r'^\+\d{1,4}\d{9,11}$', phone):
            errors.append("Phone number must start with country code (e.g. +92) and be up to 15 digits.")
        
        # Address validation
        if len(address) < 10:
            errors.append("Please enter a complete address (at least 10 characters).")
        
        # Check if email already exists
        if TrainerRegistration.objects.filter(email=email).exists():
            errors.append("This email is already registered. Please use a different email address.")
        
        # If there are validation errors, show them
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'signup_trainer.html', {
                'form_data': {
                    'username': username,
                    'email': email,
                    'phone': phone,
                    'address': address
                }
            })
        
        # If validation passes, save the registration
        try:
            trainer_registration = TrainerRegistration(
                email=email,
                username=username,
                phone=phone,
                address=address,
                password=password,  # Will be hashed in the model's save method
                status='pending'
            )
            trainer_registration.save()
            
            messages.success(
                request, 
                f"Registration successful! Your application has been submitted for review. "
                f"You will receive an email confirmation once approved."
            )
            return redirect('trainer_signup')  # Redirect to prevent resubmission
            
        except IntegrityError:
            messages.error(request, "This email is already registered.")
            return render(request, 'signup_trainer.html', {
                'form_data': {
                    'username': username,
                    'email': email,
                    'phone': phone,
                    'address': address
                }
            })
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'signup_trainer.html', {
                'form_data': {
                    'username': username,
                    'email': email,
                    'phone': phone,
                    'address': address
                }
            })
    
    # GET request - show the form
    return render(request, 'signup_trainer.html')


def check_email_availability(request):
    """AJAX endpoint to check if email is available"""
    if request.method == 'GET':
        email = request.GET.get('email', '').strip().lower()
        
        if email:
            exists = TrainerRegistration.objects.filter(email=email).exists()
            return JsonResponse({
                'available': not exists,
                'message': 'Email is already registered' if exists else 'Email is available'
            })
        
        return JsonResponse({
            'available': False,
            'message': 'Please enter an email address'
        })
    
    return JsonResponse({'error': 'Invalid request method'})


def registration_status(request):
    """Check registration status by email"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        try:
            registration = TrainerRegistration.objects.get(email=email)
            
            status_messages = {
                'pending': 'Your registration is pending admin approval.',
                'approved': 'Your registration has been approved! You can now log in.',
                'rejected': f'Your registration was rejected. Reason: {registration.rejection_reason or "Not specified"}'
            }
            
            return JsonResponse({
                'status': registration.status,
                'message': status_messages.get(registration.status, 'Unknown status'),
                'created_at': registration.created_at.strftime('%Y-%m-%d %H:%M'),
                'approval_date': registration.approval_date.strftime('%Y-%m-%d %H:%M') if registration.approval_date else None
            })
            
        except TrainerRegistration.DoesNotExist:
            return JsonResponse({
                'status': 'not_found',
                'message': 'No registration found with this email address.'
            })
    
    return render(request, 'check_status.html')


def pending_registrations_count(request):
    """API endpoint to get count of pending registrations (for admin)"""
    if request.user.is_staff:
        count = TrainerRegistration.objects.filter(status='pending').count()
        return JsonResponse({'count': count})
    
    return JsonResponse({'error': 'Unauthorized'}, status=403)


def home(request):
    return render(request, 'index.html')


def signup_customer(request):
    if request.method == 'POST':
        form = CustomerSignupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            # Save data in session instead of creating user
            request.session['signup_data'] = {
                'username': data['username'],
                'email': data['email'],
                'password': data['password'],
                'phone': data['phone'],
                'role': 'customer',
            }

            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp
            request.session['otp_expiry'] = (timezone.now() + datetime.timedelta(minutes=5)).isoformat()
            request.session['otp_attempts'] = 0

            send_mail(
                "Your OTP Code",
                f"Your OTP is {otp}",
                "noreply@yourdomain.com",
                [data['email']],
                fail_silently=False
            )
            messages.success(request, f"OTP sent to your email ({data['email']}).Your OTP is: {otp}")
            return redirect("verify_otp")

    else:
        form = CustomerSignupForm()
    return render(request, 'accounts/signup_customer.html', {'form': form})


def signup_trainer(request):
    if request.method == 'POST':
        form = TrainerSignupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            request.session['signup_data'] = {
                'username': data['username'],
                'email': data['email'],
                'password': data['password'],
                'phone': data['phone'],
                'address': data['address'],
                'role': 'trainer',
            }

            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp
            request.session['otp_expiry'] = (timezone.now() + datetime.timedelta(minutes=5)).isoformat()
            request.session['otp_attempts'] = 0

            send_mail(
                "Your OTP Code",
                f"Your OTP is {otp}",
                "noreply@yourdomain.com",
                [data['email']],
                fail_silently=False
            )
            messages.success(request, f"OTP sent to your email ({data['email']}).Your OTP is: {otp}")
            return redirect("verify_otp")

    else:
        form = TrainerSignupForm()
    return render(request, 'accounts/signup_trainer.html', {'form': form})


def verify_otp(request):
    data = request.session.get("signup_data")
    stored_otp = request.session.get("otp")
    expiry_str = request.session.get("otp_expiry")
    attempts = request.session.get("otp_attempts", 0)

    if not data or not stored_otp or not expiry_str:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect("select_signup")

    expiry = datetime.datetime.fromisoformat(expiry_str)

    if request.method == 'POST':
        entered_otp = request.POST.get("otp")

        if timezone.now() > expiry:
            messages.error(request, "OTP expired. Please resend OTP.")
            return redirect("verify_otp")

        if attempts >= 5:
            messages.error(request, "Too many failed attempts. Please start again.")
            return redirect("select_signup")

        if entered_otp == stored_otp:
             # Check if username or email already exists
            if User.objects.filter(username=data['username']).exists():
                messages.error(request, "Username already exists. Please choose another.")
                return redirect("select_signup")

            if User.objects.filter(email=data['email']).exists():
                messages.error(request, "Email already registered. Please login or use a different one.")
                return redirect("select_signup")
            # Create the user and profile
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password']
            )
            profile = Profile.objects.create(
                user=user,
                phone=data['phone'],
                role=data['role']
            )
            if data['role'] == 'customer':
                Customer.objects.create(profile=profile)
            elif data['role'] == 'trainer':
                Trainer.objects.create(profile=profile, address=data.get('address', ''))

            send_mail(
                "Welcome!",
                "Your account has been created successfully.",
                "noreply@yourdomain.com",
                [data['email']],
                fail_silently=False
            )

            for key in ['signup_data', 'otp', 'otp_expiry', 'otp_attempts']:
                request.session.pop(key, None)

            messages.success(request, "Account created successfully. Please login.")
            return redirect("login")
        else:
            request.session['otp_attempts'] = attempts + 1
            return render(request, "accounts/verify-otp.html", {
                "invalid_otp": True,
                "entered_otp": entered_otp,
                "otp_expiry": expiry_str,
                "user_email": data['email'],
            })
         # GET request - show form with timer
    return render(request, "accounts/verify-otp.html", {
        "otp_expiry": expiry_str,
        "user_email": data['email']
    })


def resend_otp(request):
    data = request.session.get("signup_data")
    if not data:
        messages.error(request, "Session expired.")
        return redirect("select_signup")
    otp = str(random.randint(100000, 999999))
    expiry = timezone.now() + datetime.timedelta(minutes=5)
    request.session["otp"] = otp
    request.session["otp_expiry"] = expiry.isoformat()
    request.session["otp_attempts"] = 0
    send_mail(
        "Your new OTP",
        f"Your OTP is: {otp}",
        "noreply@yourdomain.com",
        [data["email"]],
        fail_silently=False
    )
    messages.success(request, f"OTP sent to your email ({data['email']}).")
    return redirect("verify_otp")


def dashboard(request):
    role = request.user.profile.role
    if role == 'customer':
        return render(request, 'accounts/customer_dashboard.html')
    elif role == 'trainer':
        return render(request, 'accounts/trainer_dashboard.html')
    return redirect('login')


def logout_view(request):
    logout(request)
    return redirect('login')


def select_signup(request):
    return render(request, 'accounts/select_signup.html')


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if hasattr(user, "profile"):
                role = getattr(user.profile, "role", "")
                if role == "trainer":
                    trainer = getattr(user.profile, "trainer", None)
                    if trainer and not trainer.is_verified:
                        logout(request)
                        messages.error(request, "Your account is pending admin approval.")
                        return redirect("login")
                    return redirect("trainer_dashboard")
                elif role == "customer":
                    return redirect("customer_dashboard")
            return redirect("/")
        else:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

    return render(request, "accounts/login.html")
