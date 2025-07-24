# trainer_dashboard_views.py - Complete implementation for trainer dashboard functionality

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta, date

from .models import (
    Trainer, Customer, TrainerAssignment, Session, TrainerMessage,
    WorkoutProgress, Goal, Notification, Profile, User, Resource,
    CustomerSubscription, Payment
)

def get_trainer_or_redirect(user):
    """Helper function to get trainer or return redirect response"""
    try:
        if not hasattr(user, 'profile'):
            return None, redirect('login')
        
        if user.profile.role != 'trainer':
            return None, redirect('login')
        
        if not hasattr(user.profile, 'trainer'):
            return None, redirect('login')
        
        trainer = user.profile.trainer
        if not trainer.is_verified:
            return None, redirect('login')
        
        return trainer, None
    except Exception:
        return None, redirect('login')

@login_required
def trainer_dashboard(request):
    """Main trainer dashboard with statistics and overview"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        messages.error(request, "Access denied. Verified trainer account required.")
        return redirect_response
    
    try:
        # Get trainer's assigned customers
        assigned_customers = TrainerAssignment.objects.filter(
            trainer=trainer, 
            is_active=True
        ).select_related('customer__profile__user')
        
        # Calculate dashboard statistics
        total_clients = assigned_customers.count()
        active_subscriptions = 0
        
        # Count active subscriptions safely
        for assignment in assigned_customers:
            try:
                if hasattr(assignment.customer, 'subscription') and assignment.customer.subscription.is_active:
                    active_subscriptions += 1
            except:
                continue
        
        # Session statistics
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        sessions_today = Session.objects.filter(
            trainer=trainer,
            session_date=today
        ).count()
        
        sessions_this_week = Session.objects.filter(
            trainer=trainer,
            session_date__gte=week_start
        ).count()
        
        sessions_this_month = Session.objects.filter(
            trainer=trainer,
            session_date__gte=month_start
        ).count()
        
        upcoming_sessions = Session.objects.filter(
            trainer=trainer,
            session_date__gte=today,
            status__in=['scheduled', 'confirmed']
        ).order_by('session_date', 'session_time')[:5]
        
        # Recent messages and notifications
        recent_messages = TrainerMessage.objects.filter(
            trainer=trainer
        ).select_related('customer__profile__user').order_by('-created_at')[:5]
        
        # Recent client activity
        recent_progress = WorkoutProgress.objects.filter(
            customer__trainer_assignment__trainer=trainer,
            customer__trainer_assignment__is_active=True
        ).select_related('customer__profile__user').order_by('-created_at')[:5]
        
        # Calculate completion rates
        total_scheduled = Session.objects.filter(
            trainer=trainer,
            session_date__lt=today
        ).count()
        
        total_completed = Session.objects.filter(
            trainer=trainer,
            session_date__lt=today,
            status='completed'
        ).count()
        
        completion_rate = int((total_completed / total_scheduled) * 100) if total_scheduled > 0 else 0
        
        context = {
            'trainer': trainer,
            'user': request.user,
            'total_clients': total_clients,
            'active_subscriptions': active_subscriptions,
            'sessions_today': sessions_today,
            'sessions_this_week': sessions_this_week,
            'sessions_this_month': sessions_this_month,
            'upcoming_sessions': upcoming_sessions,
            'recent_messages': recent_messages,
            'recent_progress': recent_progress,
            'completion_rate': completion_rate,
            'today': today,
        }
        
        return render(request, 'accounts/dashboard/trainer_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Dashboard error: {str(e)}")
        return redirect('login')

@login_required
def trainer_clients(request):
    """Trainer clients management with search and pagination"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get all assignments for this trainer
    assignments = TrainerAssignment.objects.filter(
        trainer=trainer,
        is_active=True
    ).select_related(
        'customer__profile__user'
    ).prefetch_related(
        'customer__sessions',
        'customer__progress'
    )
    
    # Apply search filter
    if search_query:
        assignments = assignments.filter(
            Q(customer__profile__user__first_name__icontains=search_query) |
            Q(customer__profile__user__last_name__icontains=search_query) |
            Q(customer__profile__user__email__icontains=search_query) |
            Q(customer__profile__user__username__icontains=search_query)
        )
    
    # Calculate statistics
    total_clients = assignments.count()
    active_subscriptions = 0
    
    for assignment in assignments:
        try:
            if hasattr(assignment.customer, 'subscription') and assignment.customer.subscription.is_active:
                active_subscriptions += 1
        except:
            continue
    
    # Pagination
    paginator = Paginator(assignments, 9)  # 9 clients per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'trainer': trainer,
        'page_obj': page_obj,
        'search_query': search_query,
        'total_clients': total_clients,
        'active_subscriptions': active_subscriptions,
    }
    
    return render(request, 'accounts/dashboard/trainer_clients.html', context)

@login_required
def trainer_client_detail(request, client_id):
    """Detailed view of a specific client"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    # Get customer and verify trainer assignment
    customer = get_object_or_404(Customer, id=client_id)
    
    # Verify this trainer is assigned to this customer
    try:
        assignment = TrainerAssignment.objects.get(
            trainer=trainer,
            customer=customer,
            is_active=True
        )
    except TrainerAssignment.DoesNotExist:
        messages.error(request, "You are not assigned to this client.")
        return redirect('trainer_clients')
    
    # Get client data
    recent_sessions = Session.objects.filter(
        trainer=trainer,
        customer=customer
    ).order_by('-session_date', '-session_time')[:10]
    
    progress_entries = WorkoutProgress.objects.filter(
        customer=customer
    ).order_by('-date')[:10]
    
    active_goals = Goal.objects.filter(
        customer=customer,
        status='active'
    )[:5]
    
    # Statistics
    total_sessions = Session.objects.filter(
        trainer=trainer,
        customer=customer
    ).count()
    
    completed_sessions = Session.objects.filter(
        trainer=trainer,
        customer=customer,
        status='completed'
    ).count()
    
    context = {
        'trainer': trainer,
        'customer': customer,
        'assignment': assignment,
        'recent_sessions': recent_sessions,
        'progress_entries': progress_entries,
        'active_goals': active_goals,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
    }
    
    return render(request, 'accounts/dashboard/trainer_client_detail.html', context)

@login_required
def view_client_progress(request, client_id):
    """View detailed progress for a specific client"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    customer = get_object_or_404(Customer, id=client_id)
    
    # Verify trainer assignment
    try:
        assignment = TrainerAssignment.objects.get(
            trainer=trainer,
            customer=customer,
            is_active=True
        )
    except TrainerAssignment.DoesNotExist:
        messages.error(request, "You are not assigned to this client.")
        return redirect('trainer_clients')
    
    # Get progress data
    progress_entries = WorkoutProgress.objects.filter(
        customer=customer
    ).order_by('-date')
    
    goals = Goal.objects.filter(customer=customer).order_by('-created_at')
    
    context = {
        'trainer': trainer,
        'customer': customer,
        'assignment': assignment,
        'progress_entries': progress_entries,
        'goals': goals,
    }
    
    return render(request, 'accounts/dashboard/trainer_client_progress.html', context)

@login_required
def trainer_sessions(request):
    """Trainer sessions management with filtering"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date_range', '')
    
    # Base queryset
    sessions = Session.objects.filter(
        trainer=trainer
    ).select_related('customer__profile__user').order_by('-session_date', '-session_time')
    
    # Apply status filter
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    # Apply date filter
    today = timezone.now().date()
    if date_filter == 'today':
        sessions = sessions.filter(session_date=today)
    elif date_filter == 'week':
        week_start = today - timedelta(days=today.weekday())
        sessions = sessions.filter(session_date__gte=week_start)
    elif date_filter == 'month':
        month_start = today.replace(day=1)
        sessions = sessions.filter(session_date__gte=month_start)
    
    # Calculate statistics
    total_sessions = sessions.count()
    completed_sessions = sessions.filter(status='completed').count()
    upcoming_sessions = sessions.filter(
        session_date__gte=today,
        status__in=['scheduled', 'confirmed']
    ).count()
    
    # Pagination
    paginator = Paginator(sessions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'trainer': trainer,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'upcoming_sessions': upcoming_sessions,
    }
    
    return render(request, 'accounts/dashboard/trainer_sessions.html', context)

@login_required
def trainer_schedule(request):
    """Trainer schedule management"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        # Handle new session scheduling
        try:
            customer_id = request.POST.get('customer_id')
            session_date = request.POST.get('session_date')
            session_time = request.POST.get('session_time')
            session_type = request.POST.get('session_type', 'personal')
            duration_minutes = int(request.POST.get('duration_minutes', 60))
            notes = request.POST.get('notes', '')
            
            # Get customer and verify assignment
            customer = get_object_or_404(Customer, id=customer_id)
            try:
                TrainerAssignment.objects.get(
                    trainer=trainer,
                    customer=customer,
                    is_active=True
                )
            except TrainerAssignment.DoesNotExist:
                messages.error(request, "You are not assigned to this client.")
                return redirect('trainer_schedule')
            
            # Parse dates
            parsed_date = datetime.strptime(session_date, '%Y-%m-%d').date()
            parsed_time = datetime.strptime(session_time, '%H:%M').time()
            
            # Check for conflicting sessions
            existing_session = Session.objects.filter(
                trainer=trainer,
                session_date=parsed_date,
                session_time=parsed_time,
                status__in=['scheduled', 'confirmed']
            ).exists()
            
            if existing_session:
                messages.error(request, "You already have a session scheduled at this time.")
                return redirect('trainer_schedule')
            
            # Create session
            session = Session.objects.create(
                trainer=trainer,
                customer=customer,
                session_date=parsed_date,
                session_time=parsed_time,
                duration_minutes=duration_minutes,
                session_type=session_type,
                status='scheduled',
                notes=notes
            )
            
            # Create notification for customer
            Notification.objects.create(
                customer=customer,
                title="New Session Scheduled",
                message=f"Your trainer has scheduled a {session_type} session for {session_date} at {session_time}.",
                notification_type='session'
            )
            
            messages.success(request, "Session scheduled successfully!")
            
        except ValueError as e:
            messages.error(request, "Invalid date or time format.")
        except Exception as e:
            messages.error(request, f"Error scheduling session: {str(e)}")
        
        return redirect('trainer_schedule')
    
    # Get assigned customers for scheduling
    assigned_customers = Customer.objects.filter(
        trainer_assignment__trainer=trainer,
        trainer_assignment__is_active=True
    ).select_related('profile__user')
    
    # Get upcoming sessions for calendar view
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    upcoming_sessions = Session.objects.filter(
        trainer=trainer,
        session_date__gte=today
    ).select_related('customer__profile__user').order_by('session_date', 'session_time')
    
    context = {
        'trainer': trainer,
        'assigned_customers': assigned_customers,
        'upcoming_sessions': upcoming_sessions,
        'today': today,
        'tomorrow': tomorrow,
    }
    
    return render(request, 'accounts/dashboard/trainer_schedule.html', context)

@login_required
def trainer_messages(request):
    """Trainer messages management"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        # Handle sending new message
        try:
            customer_id = request.POST.get('customer_id')
            subject = request.POST.get('subject')
            message_content = request.POST.get('message')
            
            customer = get_object_or_404(Customer, id=customer_id)
            
            # Verify trainer assignment
            try:
                TrainerAssignment.objects.get(
                    trainer=trainer,
                    customer=customer,
                    is_active=True
                )
            except TrainerAssignment.DoesNotExist:
                messages.error(request, "You are not assigned to this client.")
                return redirect('trainer_messages')
            
            # Create message
            TrainerMessage.objects.create(
                trainer=trainer,
                customer=customer,
                subject=subject,
                message=message_content
            )
            
            # Create notification
            Notification.objects.create(
                customer=customer,
                title="New Message from Trainer",
                message=f"You have a new message from your trainer: {subject}",
                notification_type='message'
            )
            
            messages.success(request, "Message sent successfully!")
            
        except Exception as e:
            messages.error(request, f"Error sending message: {str(e)}")
        
        return redirect('trainer_messages')
    
    # Get sent messages
    sent_messages = TrainerMessage.objects.filter(
        trainer=trainer
    ).select_related('customer__profile__user').order_by('-created_at')
    
    # Get assigned customers for messaging
    assigned_customers = Customer.objects.filter(
        trainer_assignment__trainer=trainer,
        trainer_assignment__is_active=True
    ).select_related('profile__user')
    
    # Pagination
    paginator = Paginator(sent_messages, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'trainer': trainer,
        'page_obj': page_obj,
        'assigned_customers': assigned_customers,
    }
    
    return render(request, 'accounts/dashboard/trainer_messages.html', context)

@login_required
def trainer_progress(request):
    """Trainer progress tracking dashboard"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    # Get all clients' progress
    client_progress = WorkoutProgress.objects.filter(
        customer__trainer_assignment__trainer=trainer,
        customer__trainer_assignment__is_active=True
    ).select_related('customer__profile__user').order_by('-date')[:20]
    
    # Get clients for filtering
    assigned_customers = Customer.objects.filter(
        trainer_assignment__trainer=trainer,
        trainer_assignment__is_active=True
    ).select_related('profile__user')
    
    context = {
        'trainer': trainer,
        'client_progress': client_progress,
        'assigned_customers': assigned_customers,
    }
    
    return render(request, 'accounts/dashboard/trainer_progress.html', context)

@login_required
def trainer_resources(request):
    """Trainer resources management"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    # Get available resources
    resources = Resource.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'trainer': trainer,
        'resources': resources,
    }
    
    return render(request, 'accounts/dashboard/trainer_resources.html', context)

@login_required
def trainer_reports(request):
    """Trainer reports and analytics"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    # Calculate various metrics
    total_clients = TrainerAssignment.objects.filter(
        trainer=trainer,
        is_active=True
    ).count()
    
    total_sessions = Session.objects.filter(trainer=trainer).count()
    completed_sessions = Session.objects.filter(
        trainer=trainer,
        status='completed'
    ).count()
    
    # Monthly statistics
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    monthly_sessions = Session.objects.filter(
        trainer=trainer,
        session_date__gte=month_start
    ).count()
    
    monthly_completed = Session.objects.filter(
        trainer=trainer,
        session_date__gte=month_start,
        status='completed'
    ).count()
    
    context = {
        'trainer': trainer,
        'total_clients': total_clients,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'monthly_sessions': monthly_sessions,
        'monthly_completed': monthly_completed,
    }
    
    return render(request, 'accounts/dashboard/trainer_reports.html', context)

@login_required
def trainer_profile(request):
    """Trainer profile management"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        # Handle profile updates
        try:
            user = request.user
            profile = user.profile
            
            # Update user fields
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            
            # Update profile fields
            profile.phone = request.POST.get('phone', '')
            
            # Update trainer fields
            trainer.bio = request.POST.get('bio', '')
            trainer.specializations = request.POST.get('specializations', '')
            trainer.experience_years = int(request.POST.get('experience_years', 0))
            trainer.hourly_rate = request.POST.get('hourly_rate') or None
            trainer.address = request.POST.get('address', '')
            
            # Handle profile picture upload
            if 'profile_picture' in request.FILES:
                profile.profile_picture = request.FILES['profile_picture']
            
            user.save()
            profile.save()
            trainer.save()
            
            messages.success(request, "Profile updated successfully!")
            
        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")
        
        return redirect('trainer_profile')
    
    context = {
        'trainer': trainer,
        'user': request.user,
    }
    
    return render(request, 'accounts/dashboard/trainer_profile.html', context)

# AJAX/API endpoints

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_session_status(request, session_id):
    """Update session status via AJAX"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    try:
        data = json.loads(request.body)
        status = data.get('status')
        
        if status not in ['scheduled', 'confirmed', 'completed', 'cancelled']:
            return JsonResponse({'success': False, 'error': 'Invalid status'})
        
        session = get_object_or_404(Session, id=session_id, trainer=trainer)
        session.status = status
        session.save()
        
        # Create notification for customer
        Notification.objects.create(
            customer=session.customer,
            title=f"Session {status.title()}",
            message=f"Your session scheduled for {session.session_date} has been {status}.",
            notification_type='session'
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_session_notes(request, session_id):
    """Add notes to session via AJAX"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    try:
        data = json.loads(request.body)
        notes = data.get('notes', '')
        
        session = get_object_or_404(Session, id=session_id, trainer=trainer)
        session.trainer_notes = notes
        session.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def trainer_dashboard_updates(request):
    """Get real-time dashboard updates via AJAX"""
    trainer, redirect_response = get_trainer_or_redirect(request.user)
    if redirect_response:
        return JsonResponse({'error': 'Unauthorized'})
    
    try:
        today = timezone.now().date()
        
        # Get counts
        sessions_today = Session.objects.filter(
            trainer=trainer,
            session_date=today
        ).count()
        
        upcoming_sessions = Session.objects.filter(
            trainer=trainer,
            session_date__gte=today,
            status__in=['scheduled', 'confirmed']
        ).count()
        
        total_clients = TrainerAssignment.objects.filter(
            trainer=trainer,
            is_active=True
        ).count()
        
        return JsonResponse({
            'sessions_today': sessions_today,
            'upcoming_sessions': upcoming_sessions,
            'total_clients': total_clients,
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)})