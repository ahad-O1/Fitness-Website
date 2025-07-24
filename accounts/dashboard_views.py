# dashboard_views.py - Complete updated file compatible with existing models

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods
from django.contrib.auth import update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json
from datetime import datetime, timedelta

from .models import (
    Customer, SubscriptionPlan, CustomerSubscription, Payment, 
    TrainerAssignment, WorkoutProgress, Goal, Resource, ResourceCategory,
    Notification, TrainerMessage, Profile, Trainer, Session, TrainerRating
)

def get_customer_or_redirect(user):
    """Helper function to get customer or return redirect response"""
    try:
        if not hasattr(user, 'profile'):
            return None, redirect('login')
        
        if user.profile.role != 'customer':
            return None, redirect('login')
        
        if not hasattr(user.profile, 'customer'):
            return None, redirect('login')
        
        return user.profile.customer, None
    except Exception:
        return None, redirect('login')

@login_required
def customer_dashboard(request):
    """Main customer dashboard with calculated statistics"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        messages.error(request, "Access denied. Customer account required.")
        return redirect_response
    
    try:
        # Get related objects safely
        current_subscription = getattr(customer, 'subscription', None)
        trainer_assignment = getattr(customer, 'trainer_assignment', None)
        
        # Calculate statistics for dashboard
        # Active goals (limit to first 3 for display)
        active_goals = customer.goals.filter(status='active')[:3]
        active_goals_count = customer.goals.filter(status='active').count()
        
        # Recent progress (last 5 entries) 
        recent_progress = customer.progress.all()[:5]
        recent_progress_count = customer.progress.count()
        
        # Notifications (unread only, limit to 5)
        recent_notifications = customer.notifications.filter(is_read=False)[:5]
        unread_notifications_count = customer.notifications.filter(is_read=False).count()
        
        # Recent messages (unread only, limit to 3)
        recent_messages = customer.trainer_messages.filter(is_read=False)[:3]
        unread_messages_count = customer.trainer_messages.filter(is_read=False).count()
        
        context = {
            'customer': customer,
            'user': request.user,
            'current_subscription': current_subscription,
            'trainer_assignment': trainer_assignment,
            'active_goals': active_goals,
            'active_goals_count': active_goals_count,
            'recent_progress': recent_progress,
            'recent_progress_count': recent_progress_count,
            'recent_notifications': recent_notifications,
            'unread_notifications_count': unread_notifications_count,
            'recent_messages': recent_messages,
            'unread_messages_count': unread_messages_count,
        }
        
        return render(request, 'accounts/dashboard/customer_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Dashboard error: {str(e)}")
        return redirect('login')

@login_required
def customer_profile(request):
    """Customer profile management"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        # Update profile information
        user = request.user
        profile = user.profile
        
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        profile.phone = request.POST.get('phone', '')
        
        # Customer specific fields
        customer.date_of_birth = request.POST.get('date_of_birth') or None
        customer.gender = request.POST.get('gender', '')
        customer.height = request.POST.get('height') or None
        customer.weight = request.POST.get('weight') or None
        customer.fitness_level = request.POST.get('fitness_level', 'beginner')
        customer.fitness_goals = request.POST.get('fitness_goals', '')
        customer.medical_conditions = request.POST.get('medical_conditions', '')
        
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
        
        user.save()
        profile.save()
        customer.save()
        
        messages.success(request, "Profile updated successfully!")
        return redirect('customer_profile')
    
    # Calculate stats for the template
    try:
        total_goals = customer.goals.count()
        completed_goals = customer.goals.filter(status='completed').count()
        progress_entries = customer.progress.count()
        unread_notifications = customer.notifications.filter(is_read=False).count()
        current_subscription = getattr(customer, 'subscription', None)
    except Exception:
        total_goals = 0
        completed_goals = 0
        progress_entries = 0
        unread_notifications = 0
        current_subscription = None
    
    context = {
        'customer': customer,
        'user': request.user,
        'current_subscription': current_subscription,
        'total_goals': total_goals,
        'completed_goals': completed_goals,
        'progress_entries': progress_entries,
        'unread_notifications': unread_notifications,
    }
    
    return render(request, 'accounts/dashboard/customer_profile.html', context)

@login_required
def change_password(request):
    """Change password"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('customer_profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/dashboard/change_password.html', {'form': form, 'customer': customer})

@login_required
def subscription_details(request):
    """View subscription details"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    current_subscription = getattr(customer, 'subscription', None)
    available_plans = SubscriptionPlan.objects.filter(is_active=True)
    
    # Get subscription history
    subscription_history = CustomerSubscription.objects.filter(
        customer=customer
    ).exclude(id=current_subscription.id if current_subscription else None).order_by('-created_at')
    
    # Calculate monthly usage statistics if subscription exists
    monthly_sessions = 0
    monthly_downloads = 0
    monthly_messages = 0
    
    if current_subscription:
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        try:
            monthly_sessions = Session.objects.filter(
                customer=customer,
                session_date__gte=month_start.date(),
                status='completed'
            ).count()
            
            monthly_messages = TrainerMessage.objects.filter(
                customer=customer,
                created_at__gte=month_start
            ).count()
        except Exception:
            pass
    
    context = {
        'customer': customer,
        'current_subscription': current_subscription,
        'subscription_history': subscription_history,
        'available_plans': available_plans,
        'monthly_sessions': monthly_sessions,
        'monthly_downloads': monthly_downloads,
        'monthly_messages': monthly_messages,
    }
    
    return render(request, 'accounts/dashboard/subscription_details.html', context)

@login_required
def subscription_plans(request):
    """View and subscribe to plans"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    current_subscription = getattr(customer, 'subscription', None)
    
    context = {
        'customer': customer,
        'plans': plans,
        'current_subscription': current_subscription,
    }
    
    return render(request, 'accounts/dashboard/subscription_plans.html', context)

@login_required
def subscribe_to_plan(request, plan_id):
    """Subscribe to a plan"""
    if request.method != 'POST':
        return redirect('subscription_plans')
    
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    
    try:
        # Create or update subscription
        subscription, created = CustomerSubscription.objects.get_or_create(
            customer=customer,
            defaults={
                'plan': plan,
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=plan.duration_days),
                'is_active': True,
                'auto_renew': True,
            }
        )
        
        if not created:
            # Update existing subscription
            subscription.plan = plan
            subscription.start_date = timezone.now()
            subscription.end_date = timezone.now() + timedelta(days=plan.duration_days)
            subscription.is_active = True
            subscription.auto_renew = True
            subscription.save()
        
        # Create payment record
        payment = Payment.objects.create(
            customer=customer,
            subscription=subscription,
            amount=plan.price,
            payment_method='card',  # Default for demo
            status='completed',
            transaction_id=f"TXN_{timezone.now().strftime('%Y%m%d%H%M%S')}_{customer.id}",
        )
        
        # If plan includes trainer support, try to assign a trainer
        if plan.trainer_support:
            try:
                # Find available trainer with least assignments
                available_trainer = Trainer.objects.annotate(
                    assignment_count=Count('assigned_customers', filter=Q(assigned_customers__is_active=True))
                ).filter(
                    is_verified=True
                ).order_by('assignment_count').first()
                
                if available_trainer:
                    # Check if customer already has trainer assignment
                    trainer_assignment, assignment_created = TrainerAssignment.objects.get_or_create(
                        customer=customer,
                        defaults={
                            'trainer': available_trainer,
                            'assigned_date': timezone.now(),
                            'is_active': True,
                            'notes': f"Automatically assigned with {plan.name} subscription."
                        }
                    )
                    
                    if not assignment_created:
                        # Update existing assignment
                        trainer_assignment.trainer = available_trainer
                        trainer_assignment.is_active = True
                        trainer_assignment.notes = f"Reassigned with {plan.name} subscription upgrade."
                        trainer_assignment.save()
            except Exception:
                pass  # Continue even if trainer assignment fails
        
        # Create notification
        Notification.objects.create(
            customer=customer,
            title="Subscription Activated",
            message=f"Your {plan.name} subscription has been activated successfully!",
            notification_type='subscription',
        )
        
        messages.success(request, f"Successfully subscribed to {plan.name}!")
        
    except Exception as e:
        messages.error(request, f"Error processing subscription: {str(e)}")
    
    return redirect('subscription_details')

@login_required
def toggle_auto_renew(request):
    """Toggle auto-renewal for subscription"""
    if request.method != 'POST':
        return redirect('subscription_details')
    
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    subscription = getattr(customer, 'subscription', None)
    
    if subscription:
        subscription.auto_renew = not subscription.auto_renew
        subscription.save()
        
        status = "enabled" if subscription.auto_renew else "disabled"
        messages.success(request, f'Auto-renewal has been {status}.')
    else:
        messages.error(request, 'No active subscription found.')
    
    return redirect('subscription_details')

@login_required
def cancel_subscription(request):
    """Cancel current subscription"""
    if request.method != 'POST':
        return redirect('subscription_details')
    
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    subscription = getattr(customer, 'subscription', None)
    
    if subscription:
        subscription.auto_renew = False
        subscription.save()
        
        # Create notification about cancellation
        Notification.objects.create(
            customer=customer,
            title="Subscription Cancelled",
            message=f"Your {subscription.plan.name} subscription will not auto-renew. Access will continue until {subscription.end_date.date()}.",
            notification_type="subscription",
            is_read=False
        )
        
        messages.success(request, 'Your subscription has been cancelled. You will continue to have access until the end of your billing period.')
    else:
        messages.error(request, 'No active subscription found.')
    
    return redirect('subscription_details')

@login_required
def payment_history(request):
    """Payment history with pagination and statistics"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    payments = customer.payments.all().order_by('-payment_date')
    
    # Calculate payment statistics
    try:
        total_amount = payments.aggregate(total=Sum('amount'))['total'] or 0
        completed_count = payments.filter(status='completed').count()
        pending_count = payments.filter(status='pending').count()
        failed_count = payments.filter(status='failed').count()
        refunded_count = payments.filter(status='refunded').count()
    except Exception:
        total_amount = 0
        completed_count = 0
        pending_count = 0
        failed_count = 0
        refunded_count = 0
    
    paginator = Paginator(payments, 10)  # 10 payments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customer': customer,
        'page_obj': page_obj,
        'total_amount': total_amount,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'failed_count': failed_count,
        'refunded_count': refunded_count,
    }
    
    return render(request, 'accounts/dashboard/payment_history.html', context)

@login_required
def trainer_info(request):
    """View assigned trainer information"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    trainer_assignment = getattr(customer, 'trainer_assignment', None)
    current_subscription = getattr(customer, 'subscription', None)
    
    # Initialize context variables
    upcoming_sessions = []
    recent_messages = []
    total_sessions = 0
    monthly_sessions = 0
    attendance_rate = 0
    
    if trainer_assignment and trainer_assignment.is_active:
        try:
            # Get upcoming sessions
            upcoming_sessions = Session.objects.filter(
                customer=customer,
                trainer=trainer_assignment.trainer,
                session_date__gte=timezone.now().date(),
                status__in=['scheduled', 'confirmed']
            ).order_by('session_date', 'session_time')[:5]
            
            # Get recent messages with trainer
            recent_messages = TrainerMessage.objects.filter(
                customer=customer,
                trainer=trainer_assignment.trainer
            ).order_by('-created_at')[:5]
            
            # Calculate session statistics
            total_sessions = Session.objects.filter(
                customer=customer,
                trainer=trainer_assignment.trainer,
                status='completed'
            ).count()
            
            # Monthly sessions
            month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_sessions = Session.objects.filter(
                customer=customer,
                trainer=trainer_assignment.trainer,
                session_date__gte=month_start.date(),
                status='completed'
            ).count()
            
            # Calculate attendance rate
            scheduled_sessions = Session.objects.filter(
                customer=customer,
                trainer=trainer_assignment.trainer,
                session_date__lt=timezone.now().date()
            ).count()
            
            if scheduled_sessions > 0:
                attended_sessions = Session.objects.filter(
                    customer=customer,
                    trainer=trainer_assignment.trainer,
                    session_date__lt=timezone.now().date(),
                    status='completed'
                ).count()
                attendance_rate = int((attended_sessions / scheduled_sessions) * 100)
        except Exception:
            pass  # Keep default values
    
    context = {
        'customer': customer,
        'trainer_assignment': trainer_assignment,
        'current_subscription': current_subscription,
        'upcoming_sessions': upcoming_sessions,
        'recent_messages': recent_messages,
        'total_sessions': total_sessions,
        'monthly_sessions': monthly_sessions,
        'attendance_rate': attendance_rate,
    }
    
    return render(request, 'accounts/dashboard/trainer_info.html', context)

@login_required
def rate_trainer(request, trainer_id):
    """Rate and provide feedback for trainer"""
    if request.method != 'POST':
        return redirect('trainer_info')
    
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    trainer = get_object_or_404(Trainer, id=trainer_id)
    rating_value = request.POST.get('rating')
    feedback = request.POST.get('feedback', '')
    
    if rating_value:
        try:
            # Create or update rating
            rating, created = TrainerRating.objects.get_or_create(
                customer=customer,
                trainer=trainer,
                defaults={
                    'rating': int(rating_value),
                    'feedback': feedback,
                }
            )
            
            if not created:
                rating.rating = int(rating_value)
                rating.feedback = feedback
                rating.save()
            
            # Update trainer's average rating
            avg_rating = TrainerRating.objects.filter(trainer=trainer).aggregate(
                avg=Avg('rating')
            )['avg']
            trainer.average_rating = avg_rating or 0
            trainer.save()
            
            messages.success(request, 'Thank you for rating your trainer!')
        except Exception as e:
            messages.error(request, f'Error saving rating: {str(e)}')
    else:
        messages.error(request, 'Please provide a rating.')
    
    return redirect('trainer_info')

@login_required
def workout_progress(request):
    """Workout progress tracking with statistics"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        # Add new progress entry
        try:
            date = request.POST.get('date')
            weight = request.POST.get('weight')
            bmi = request.POST.get('bmi')
            sessions = request.POST.get('sessions_attended', 0)
            notes = request.POST.get('customer_notes', '')
            
            progress, created = WorkoutProgress.objects.get_or_create(
                customer=customer,
                date=datetime.strptime(date, '%Y-%m-%d').date(),
                defaults={
                    'weight': float(weight) if weight else None,
                    'bmi': float(bmi) if bmi else None,
                    'sessions_attended': int(sessions),
                    'customer_notes': notes,
                }
            )
            
            if not created:
                # Update existing progress
                if weight:
                    progress.weight = float(weight)
                if bmi:
                    progress.bmi = float(bmi)
                progress.sessions_attended = int(sessions)
                progress.customer_notes = notes
                progress.save()
            
            messages.success(request, "Progress updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating progress: {str(e)}")
        
        return redirect('workout_progress')
    
    # Get progress data for charts
    progress_data = customer.progress.all()[:30]  # Last 30 entries
    
    # Calculate progress statistics
    try:
        total_entries = customer.progress.count()
        total_sessions = customer.progress.aggregate(total=Sum('sessions_attended'))['total'] or 0
        latest_weight = None
        latest_bmi = None
        
        if progress_data:
            latest_entry = progress_data[0]
            latest_weight = latest_entry.weight
            latest_bmi = latest_entry.bmi
    except Exception:
        total_entries = 0
        total_sessions = 0
        latest_weight = None
        latest_bmi = None
    
    # Prepare chart data
    chart_data = {
        'dates': [p.date.strftime('%Y-%m-%d') for p in reversed(progress_data)],
        'weights': [float(p.weight) if p.weight else 0 for p in reversed(progress_data)],
        'bmis': [float(p.bmi) if p.bmi else 0 for p in reversed(progress_data)],
        'sessions': [p.sessions_attended for p in reversed(progress_data)],
    }
    
    context = {
        'customer': customer,
        'progress_data': progress_data,
        'chart_data': json.dumps(chart_data),
        'total_entries': total_entries,
        'total_sessions': total_sessions,
        'latest_weight': latest_weight,
        'latest_bmi': latest_bmi,
    }
    
    return render(request, 'accounts/dashboard/workout_progress.html', context)

@login_required
def goals_management(request):
    """Goals and milestones management"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            if action == 'create':
                Goal.objects.create(
                    customer=customer,
                    title=request.POST.get('title'),
                    description=request.POST.get('description'),
                    goal_type=request.POST.get('goal_type', 'other'),
                    target_value=float(request.POST.get('target_value', 0)) or None,
                    unit=request.POST.get('unit', ''),
                    target_date=datetime.strptime(request.POST.get('target_date'), '%Y-%m-%d').date() if request.POST.get('target_date') else None,
                )
                messages.success(request, "Goal created successfully!")
                
            elif action == 'update_progress':
                goal_id = request.POST.get('goal_id')
                current_value = request.POST.get('current_value')
                goal = get_object_or_404(Goal, id=goal_id, customer=customer)
                goal.current_value = float(current_value)
                
                # Check if goal is completed
                if goal.target_value and goal.current_value >= goal.target_value:
                    goal.status = 'completed'
                    goal.completed_at = timezone.now()
                    
                    # Create notification
                    Notification.objects.create(
                        customer=customer,
                        title="Goal Completed! 🎉",
                        message=f"Congratulations! You've completed your goal: {goal.title}",
                        notification_type='general',
                    )
                
                goal.save()
                messages.success(request, "Goal progress updated!")
            
            elif action in ['pause', 'resume', 'cancel']:
                goal_id = request.POST.get('goal_id')
                goal = get_object_or_404(Goal, id=goal_id, customer=customer)
                
                if action == 'pause':
                    goal.status = 'paused'
                elif action == 'resume':
                    goal.status = 'active'
                elif action == 'cancel':
                    goal.status = 'cancelled'
                
                goal.save()
                messages.success(request, f"Goal {action}d successfully!")
                
        except Exception as e:
            messages.error(request, f"Error processing request: {str(e)}")
        
        return redirect('goals_management')
    
    goals = customer.goals.all().order_by('-created_at')
    
    # Calculate goal statistics
    try:
        total_goals = goals.count()
        active_goals_count = goals.filter(status='active').count()
        completed_goals_count = goals.filter(status='completed').count()
        paused_goals_count = goals.filter(status='paused').count()
        cancelled_goals_count = goals.filter(status='cancelled').count()
        
        # Calculate average progress for active goals
        active_goals_with_targets = goals.filter(status='active', target_value__isnull=False)
        avg_progress = 0
        if active_goals_with_targets.exists():
            total_progress = sum([goal.progress_percentage for goal in active_goals_with_targets])
            avg_progress = total_progress / active_goals_with_targets.count()
    except Exception:
        total_goals = 0
        active_goals_count = 0
        completed_goals_count = 0
        paused_goals_count = 0
        cancelled_goals_count = 0
        avg_progress = 0
    
    context = {
        'customer': customer,
        'goals': goals,
        'total_goals': total_goals,
        'active_goals_count': active_goals_count,
        'completed_goals_count': completed_goals_count,
        'paused_goals_count': paused_goals_count,
        'cancelled_goals_count': cancelled_goals_count,
        'avg_progress': avg_progress,
    }
    
    return render(request, 'accounts/dashboard/goals_management.html', context)

@login_required
def resources_downloads(request):
    """Training resources and downloads"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    current_subscription = getattr(customer, 'subscription', None)
    has_active_subscription = current_subscription and current_subscription.is_active
    
    # Filter resources based on subscription
    if has_active_subscription and current_subscription.plan.premium_content:
        resources = Resource.objects.filter(is_active=True).order_by('-created_at')
    else:
        resources = Resource.objects.filter(is_active=True, is_premium=False).order_by('-created_at')
    
    # Get resource categories
    categories = ResourceCategory.objects.filter(is_active=True)
    
    context = {
        'customer': customer,
        'resources': resources,
        'categories': categories,
        'current_subscription': current_subscription,
        'has_active_subscription': has_active_subscription,
    }
    
    return render(request, 'accounts/dashboard/resources_downloads.html', context)

@login_required
def notifications_list(request):
    """View all notifications with statistics"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    notifications = customer.notifications.all().order_by('-created_at')
    
    # Mark as read if requested
    if request.GET.get('mark_read'):
        notification_id = request.GET.get('mark_read')
        try:
            notification = get_object_or_404(Notification, id=notification_id, customer=customer)
            notification.is_read = True
            notification.save()
            return JsonResponse({'status': 'success'})
        except Exception:
            return JsonResponse({'status': 'error'})
    
    # Calculate notification statistics
    try:
        total_count = notifications.count()
        unread_count = notifications.filter(is_read=False).count()
        today_count = notifications.filter(created_at__date=timezone.now().date()).count()
        week_start = timezone.now() - timedelta(days=7)
        week_count = notifications.filter(created_at__gte=week_start).count()
    except Exception:
        total_count = 0
        unread_count = 0
        today_count = 0
        week_count = 0
    
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customer': customer,
        'page_obj': page_obj,
        'total_count': total_count,
        'unread_count': unread_count,
        'today_count': today_count,
        'week_count': week_count,
    }
    
    return render(request, 'accounts/dashboard/notifications_list.html', context)

@login_required
def trainer_messages(request):
    """View messages from trainer with statistics"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    messages_list = customer.trainer_messages.all().order_by('-created_at')
    
    # Mark message as read
    if request.GET.get('mark_read'):
        message_id = request.GET.get('mark_read')
        try:
            message = get_object_or_404(TrainerMessage, id=message_id, customer=customer)
            message.is_read = True
            message.save()
            return JsonResponse({'status': 'success'})
        except Exception:
            return JsonResponse({'status': 'error'})
    
    # Calculate message statistics
    try:
        total_count = messages_list.count()
        unread_count = messages_list.filter(is_read=False).count()
        today_count = messages_list.filter(created_at__date=timezone.now().date()).count()
    except Exception:
        total_count = 0
        unread_count = 0
        today_count = 0
    
    paginator = Paginator(messages_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'customer': customer,
        'page_obj': page_obj,
        'total_count': total_count,
        'unread_count': unread_count,
        'today_count': today_count,
    }
    
    return render(request, 'accounts/dashboard/trainer_messages.html', context)

@login_required
def download_resource(request, resource_id):
    """Download resource file"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    resource = get_object_or_404(Resource, id=resource_id, is_active=True)
    
    # Check if customer has access
    subscription = getattr(customer, 'subscription', None)
    if resource.is_premium and (not subscription or not subscription.is_active or not subscription.plan.premium_content):
        messages.error(request, "Premium subscription required to access this resource.")
        return redirect('resources_downloads')
    
    if resource.file:
        try:
            response = HttpResponse(resource.file.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{resource.file.name.split("/")[-1]}"'
            return response
        except Exception:
            messages.error(request, "Error downloading file.")
            return redirect('resources_downloads')
    elif resource.external_url or resource.file_url:
        return redirect(resource.external_url or resource.file_url)
    else:
        messages.error(request, "Resource file not found.")
        return redirect('resources_downloads')

@login_required
def delete_account(request):
    """Delete customer account (with confirmation)"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        confirmation = request.POST.get('confirmation')
        if confirmation == 'DELETE':
            user = request.user
            logout(request)
            user.delete()  # This will cascade delete profile and customer
            messages.success(request, "Account deleted successfully.")
            return redirect('login')
        else:
            messages.error(request, "Please type 'DELETE' to confirm account deletion.")
    
    return render(request, 'accounts/dashboard/delete_account.html', {
        'customer': customer,
    })

# Additional placeholder views for URLs that might be referenced
@login_required
def schedule_session(request):
    """Schedule training session - placeholder"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    messages.info(request, "Session scheduling feature coming soon!")
    return redirect('trainer_info')

@login_required
def request_workout_plan(request):
    """Request workout plan - placeholder"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    messages.info(request, "Workout plan request feature coming soon!")
    return redirect('trainer_info')

@login_required
def request_trainer_change(request):
    """Request trainer change - placeholder"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    messages.info(request, "Trainer change request feature coming soon!")
    return redirect('trainer_info')

@login_required
def download_invoice(request, subscription_id):
    """Download invoice - placeholder"""
    customer, redirect_response = get_customer_or_redirect(request.user)
    if redirect_response:
        return redirect_response
    
    messages.info(request, "Invoice download feature coming soon!")
    return redirect('subscription_details')

# API endpoints for AJAX calls
@login_required
def api_notifications_count(request):
    """Get unread notifications count"""
    try:
        customer, redirect_response = get_customer_or_redirect(request.user)
        if redirect_response:
            return JsonResponse({'count': 0})
        
        count = customer.notifications.filter(is_read=False).count()
        return JsonResponse({'count': count})
    except Exception:
        return JsonResponse({'count': 0})

@login_required
def api_subscription_status(request):
    """Get subscription status"""
    try:
        customer, redirect_response = get_customer_or_redirect(request.user)
        if redirect_response:
            return JsonResponse({'has_subscription': False})
        
        subscription = getattr(customer, 'subscription', None)
        
        if subscription and subscription.is_active:
            return JsonResponse({
                'has_subscription': True,
                'plan_name': subscription.plan.name,
                'is_active': subscription.is_active,
                'days_remaining': subscription.days_remaining,
                'is_expired': subscription.is_expired,
            })
        
        return JsonResponse({'has_subscription': False})
    except Exception:
        return JsonResponse({'has_subscription': False})