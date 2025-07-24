# admin.py - Enhanced version with trainer assignment functionality

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.core.mail import send_mail
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from .models import (
    Trainer, Customer, SubscriptionPlan, CustomerSubscription, Payment, 
    TrainerAssignment, WorkoutProgress, Goal, Resource, Notification, 
    TrainerMessage, Profile, User
)
from .forms import TrainerAssignmentForm


class SubscriptionFilter(SimpleListFilter):
    title = 'Subscription Status'
    parameter_name = 'subscription_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active Subscription'),
            ('expired', 'Expired Subscription'),
            ('no_subscription', 'No Subscription'),
            ('personal_training', 'Personal Training Plan'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(subscription__is_active=True)
        elif self.value() == 'expired':
            return queryset.filter(subscription__is_active=False)
        elif self.value() == 'no_subscription':
            return queryset.filter(subscription__isnull=True)
        elif self.value() == 'personal_training':
            return queryset.filter(
                subscription__is_active=True,
                subscription__plan__trainer_support=True
            )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_email', 'get_subscription_status', 
                   'get_trainer_status', 'trainer_assignment_actions')
    list_filter = (SubscriptionFilter, 'profile__role', 'trainer_assignment__is_active',
                   'trainer_assignment__trainer')  # Add trainer filter
    search_fields = ('profile__user__first_name', 'profile__user__last_name', 
                    'profile__user__email', 'profile__user__username')
    actions = ['assign_trainers_bulk', 'remove_trainer_assignments']
    
    # Add this to allow the lookup fields
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('profile__user', 'trainer_assignment__trainer__profile__user')
    
    # Override changelist_view to handle custom filtering
    def changelist_view(self, request, extra_context=None):
        # Check if we have trainer filtering parameters
        trainer_id = request.GET.get('trainer_assignment__trainer__id__exact')
        is_active = request.GET.get('trainer_assignment__is_active__exact')
        
        if trainer_id or is_active:
            # Create a custom queryset with the filtering
            return self.trainer_clients_view(request, trainer_id, is_active, extra_context)
        
        return super().changelist_view(request, extra_context)
    
    def trainer_clients_view(self, request, trainer_id=None, is_active=None, extra_context=None):
        """Custom view to show trainer's clients"""
        from django.contrib.admin.views.main import ChangeList
        from django.core.paginator import Paginator
        
        # Build the queryset
        queryset = self.get_queryset(request)
        
        if trainer_id:
            queryset = queryset.filter(trainer_assignment__trainer__id=trainer_id)
        if is_active:
            queryset = queryset.filter(trainer_assignment__is_active=bool(int(is_active)))
        
        # Get trainer info for context
        trainer = None
        if trainer_id:
            try:
                trainer = Trainer.objects.select_related('profile__user').get(id=trainer_id)
            except Trainer.DoesNotExist:
                pass
        
        # Set up context
        context = {
            'title': f'Clients for {trainer.profile.user.get_full_name() if trainer else "Trainer"}',
            'cl': type('MockChangeList', (), {
                'queryset': queryset,
                'opts': self.model._meta,
                'has_filters': True,
                'filtered': True,
            })(),
            'filtered_clients': queryset,
            'trainer': trainer,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request),
            'has_add_permission': self.has_add_permission(request),
            'has_delete_permission': self.has_delete_permission(request),
        }
        
        if extra_context:
            context.update(extra_context)
        
        return render(request, 'admin/trainer_clients_list.html', context)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('assign-trainer/<int:customer_id>/', 
                 self.admin_site.admin_view(self.assign_trainer_view), 
                 name='assign_trainer'),
            path('trainer-assignment-dashboard/', 
                 self.admin_site.admin_view(self.trainer_assignment_dashboard), 
                 name='trainer_assignment_dashboard'),
            path('send-message/<int:customer_id>/<int:trainer_id>/', 
                 self.admin_site.admin_view(self.send_message_view), 
                 name='send_admin_message'),
            path('trainer-clients/<int:trainer_id>/', 
                 self.admin_site.admin_view(self.view_trainer_clients), 
                 name='view_trainer_clients'),
        ]
        return custom_urls + urls
    
    def view_trainer_clients(self, request, trainer_id):
        """Dedicated view for trainer's clients"""
        try:
            trainer = Trainer.objects.select_related('profile__user').get(id=trainer_id)
        except Trainer.DoesNotExist:
            messages.error(request, "Trainer not found.")
            return redirect('admin:accounts_trainer_changelist')
        
        # Get trainer's clients
        clients = Customer.objects.filter(
            trainer_assignment__trainer=trainer,
            trainer_assignment__is_active=True
        ).select_related('profile__user', 'subscription__plan')
        
        context = {
            'title': f'Clients assigned to {trainer.profile.user.get_full_name()}',
            'trainer': trainer,
            'clients': clients,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request),
        }
        
        return render(request, 'admin/trainer_clients_detail.html', context)

    def get_full_name(self, obj):
        return obj.profile.user.get_full_name() or obj.profile.user.username
    get_full_name.short_description = 'Customer Name'

    def get_email(self, obj):
        return obj.profile.user.email
    get_email.short_description = 'Email'

    def get_subscription_status(self, obj):
        try:
            if hasattr(obj, 'subscription') and obj.subscription.is_active:
                plan = obj.subscription.plan
                color = 'green' if obj.subscription.days_remaining > 7 else 'orange'
                return format_html(
                    '<span style="color: {};">{} ({} days left)</span>',
                    color,
                    plan.name,
                    obj.subscription.days_remaining
                )
            else:
                return format_html('<span style="color: red;">No Active Subscription</span>')
        except:
            return format_html('<span style="color: red;">No Subscription</span>')
    get_subscription_status.short_description = 'Subscription'

    def get_trainer_status(self, obj):
        try:
            assignment = TrainerAssignment.objects.select_related(
                'trainer__profile__user'
            ).get(customer=obj, is_active=True)
            
            # Get trainer name safely
            trainer_name = (
                assignment.trainer.profile.user.get_full_name() or 
                assignment.trainer.profile.user.username or 
                f"User {assignment.trainer.profile.user.id}"
            )
            
            return format_html(
                '<span style="color: green;">Assigned to {}</span>',
                trainer_name
            )
            
        except TrainerAssignment.DoesNotExist:
            return format_html('<span style="color: red;">No Trainer Assigned</span>')
        except Exception as e:
            print(f"Error getting trainer status for customer {obj.id}: {e}")
            return format_html('<span style="color: red;">Error Loading Trainer</span>')

    def trainer_assignment_actions(self, obj):
        actions = []
        
        # Check if customer has personal training subscription
        has_personal_training = False
        try:
            if (hasattr(obj, 'subscription') and obj.subscription.is_active 
                and obj.subscription.plan.trainer_support):
                has_personal_training = True
        except:
            pass

        if has_personal_training:
            try:
                # Get assignment with proper select_related
                assignment = TrainerAssignment.objects.select_related(
                    'trainer__profile__user'
                ).get(customer=obj, is_active=True)
                
                # Get trainer name safely
                trainer_name = (
                    assignment.trainer.profile.user.get_full_name() or 
                    assignment.trainer.profile.user.username or 
                    f"User {assignment.trainer.profile.user.id}"
                )
                
                # Show trainer info and management options
                trainer_change_url = reverse('admin:assign_trainer', args=[obj.id])
                message_url = reverse('admin:send_admin_message', 
                                    args=[obj.id, assignment.trainer.id])
                actions.append(f'''
                    <div style="margin-bottom: 5px;">
                        <strong>Trainer:</strong> {trainer_name}
                    </div>
                    <a href="{trainer_change_url}" class="button" style="margin-right: 5px;">
                        Change Trainer
                    </a>
                    <a href="{message_url}" class="button" style="margin-right: 5px;">
                        Send Message
                    </a>
                ''')
                
            except TrainerAssignment.DoesNotExist:
                # No active assignment found
                assign_url = reverse('admin:assign_trainer', args=[obj.id])
                actions.append(f'<a href="{assign_url}" class="button">Assign Trainer</a>')
            except Exception as e:
                # Any other error
                print(f"Error getting trainer assignment for customer {obj.id}: {e}")
                assign_url = reverse('admin:assign_trainer', args=[obj.id])
                actions.append(f'<a href="{assign_url}" class="button">Assign Trainer</a>')
        else:
            actions.append('<span style="color: #666;">No Personal Training Plan</span>')

        return format_html(''.join(actions))

    # Keep all your other existing methods (assign_trainer_view, etc.)
    # ... (rest of the methods remain the same)

    def assign_trainer_view(self, request, customer_id):
        """Assign trainer to customer view"""
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Check if customer has personal training subscription
        if not (hasattr(customer, 'subscription') and customer.subscription.is_active 
                and customer.subscription.plan.trainer_support):
            messages.error(request, 'Customer does not have an active personal training subscription.')
            return redirect('admin:accounts_customer_changelist')

        if request.method == 'POST':
            trainer_id = request.POST.get('trainer')
            notes = request.POST.get('notes', '')
            
            if not trainer_id:
                messages.error(request, 'Please select a trainer.')
                return redirect(f'/admin/accounts/customer/assign-trainer/{customer_id}/')
            
            try:
                trainer = Trainer.objects.select_related('profile__user').get(id=trainer_id, is_verified=True)
            except Trainer.DoesNotExist:
                messages.error(request, 'Selected trainer not found or not verified.')
                return redirect(f'/admin/accounts/customer/assign-trainer/{customer_id}/')
            
            try:
                # Try to get existing assignment
                assignment = TrainerAssignment.objects.select_related('trainer__profile__user').get(customer=customer)
                
                # Update existing assignment
                assignment.trainer = trainer
                assignment.assigned_date = timezone.now()
                assignment.is_active = True
                assignment.notes = notes
                assignment.end_date = None  # Clear end date if it was set
                assignment.save()
                
                action_message = "updated"
                
            except TrainerAssignment.DoesNotExist:
                # Create new assignment if none exists
                assignment = TrainerAssignment.objects.create(
                    customer=customer,
                    trainer=trainer,
                    assigned_date=timezone.now(),
                    is_active=True,
                    notes=notes
                )
                
                action_message = "assigned"

            # Send notifications
            trainer_name = trainer.profile.user.get_full_name() or trainer.profile.user.username
            
            Notification.objects.create(
                customer=customer,
                title="Trainer Assignment Updated" if action_message == "updated" else "Trainer Assigned",
                message=f"You have been {action_message} to trainer {trainer_name}.",
                notification_type='trainer'
            )

            # Send email notification
            send_mail(
                subject=f"Trainer Assignment {action_message.title()} - FitnessHub",
                message=f"You have been {action_message} to trainer {trainer_name}. They will contact you soon to begin your training sessions.",
                from_email="noreply@fitnesshub.com",
                recipient_list=[customer.profile.user.email],
                fail_silently=True,
            )

            messages.success(request, f'Trainer {trainer_name} has been {action_message} to {customer.profile.user.get_full_name()}.')
            return redirect('admin:accounts_customer_changelist')

        # GET request - show the form
        # Get all trainers and add their statistics
        all_trainers = Trainer.objects.filter(is_verified=True).select_related('profile__user')
        available_trainers = []
        
        for trainer in all_trainers:
            # Calculate active client count
            active_clients_count = trainer.assigned_customers.filter(is_active=True).count()
            
            # Add attributes to trainer object - Make sure we have the name
            trainer.active_clients_count = active_clients_count
            trainer.display_name = trainer.profile.user.get_full_name() or trainer.profile.user.username
            trainer.display_email = trainer.profile.user.email
            
            # Ensure we have a valid display name
            if not trainer.display_name or trainer.display_name.strip() == '':
                trainer.display_name = f"User {trainer.profile.user.id}"
            
            # Calculate availability
            if active_clients_count < 5:
                trainer.availability_text = "High"
                trainer.availability_class = "high"
            elif active_clients_count < 10:
                trainer.availability_text = "Medium" 
                trainer.availability_class = "medium"
            else:
                trainer.availability_text = "Low"
                trainer.availability_class = "low"
            
            available_trainers.append(trainer)
        
        # Sort by active clients count (least busy first)
        available_trainers.sort(key=lambda t: t.active_clients_count)
        
        # Get current assignment for pre-filling form
        current_assignment = None
        selected_trainer_id = None
        assignment_notes = ""
        current_trainer_name = ""
        
        try:
            current_assignment = TrainerAssignment.objects.select_related(
                'trainer__profile__user'
            ).get(customer=customer)
            
            if current_assignment.is_active:
                selected_trainer_id = current_assignment.trainer.id
                assignment_notes = current_assignment.notes or ""
                current_trainer_name = (
                    current_assignment.trainer.profile.user.get_full_name() or 
                    current_assignment.trainer.profile.user.username or 
                    f"User {current_assignment.trainer.profile.user.id}"
                )
                
                # Add current trainer name to the assignment object for template
                current_assignment.trainer_display_name = current_trainer_name
                
        except TrainerAssignment.DoesNotExist:
            pass
        
        # Debug: Print trainer and assignment information
        print(f"Found {len(available_trainers)} trainers:")
        for trainer in available_trainers:
            print(f"- ID: {trainer.id}, Name: '{trainer.display_name}', Clients: {trainer.active_clients_count}")
        
        if current_assignment:
            print(f"Current assignment - Trainer: '{current_trainer_name}', ID: {selected_trainer_id}")
        
        context = {
            'title': f'Assign Trainer to {customer.profile.user.get_full_name()}',
            'customer': customer,
            'available_trainers': available_trainers,
            'current_assignment': current_assignment,
            'selected_trainer_id': selected_trainer_id,
            'assignment_notes': assignment_notes,
            'current_trainer_name': current_trainer_name,
            'opts': self.model._meta,
            'has_change_permission': True,
        }
        
        return render(request, 'admin/assign_trainer.html', context)

    def trainer_assignment_dashboard(self, request):
        """Dashboard view for trainer assignments"""
        # Get statistics
        total_customers = Customer.objects.filter(
            subscription__is_active=True,
            subscription__plan__trainer_support=True
        ).count()
        
        assigned_customers = TrainerAssignment.objects.filter(is_active=True).count()
        unassigned_customers = total_customers - assigned_customers
        
        active_trainers = Trainer.objects.filter(
            is_verified=True,
            assigned_customers__is_active=True
        ).distinct().count()

        # Get recent assignments
        recent_assignments = TrainerAssignment.objects.filter(
            is_active=True
        ).select_related(
            'customer__profile__user', 
            'trainer__profile__user'
        ).order_by('-assigned_date')[:10]

        # Get trainer workload
        trainer_workload = []
        for trainer in Trainer.objects.filter(is_verified=True).select_related('profile__user'):
            active_assignments = trainer.assigned_customers.filter(is_active=True).count()
            trainer_workload.append({
                'trainer': trainer,
                'active_clients': active_assignments,
                'availability': 'High' if active_assignments < 5 else 'Medium' if active_assignments < 10 else 'Low'
            })

        context = {
            'title': 'Trainer Assignment Dashboard',
            'total_customers': total_customers,
            'assigned_customers': assigned_customers,
            'unassigned_customers': unassigned_customers,
            'active_trainers': active_trainers,
            'recent_assignments': recent_assignments,
            'trainer_workload': trainer_workload,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/trainer_assignment_dashboard.html', context)

    def send_message_view(self, request, customer_id, trainer_id):
        """Send message between customer and trainer"""
        customer = get_object_or_404(Customer, id=customer_id)
        trainer = get_object_or_404(Trainer, id=trainer_id)
        
        if request.method == 'POST':
            subject = request.POST.get('subject')
            message = request.POST.get('message')
            sender = request.POST.get('sender')  # 'trainer' or 'customer'
            
            if sender == 'trainer':
                # Message from trainer to customer
                TrainerMessage.objects.create(
                    customer=customer,
                    trainer=trainer,
                    subject=subject,
                    message=message
                )
                
                # Create notification for customer
                Notification.objects.create(
                    customer=customer,
                    title="New Message from Trainer",
                    message=f"You have a new message from your trainer: {subject}",
                    notification_type='message'
                )
                
                recipient_email = customer.profile.user.email
                recipient_name = customer.profile.user.get_full_name()
            
            # Send email notification
            send_mail(
                subject=f"New Message: {subject}",
                message=f"You have received a new message.\n\nSubject: {subject}\nMessage: {message}",
                from_email="noreply@fitnesshub.com",
                recipient_list=[recipient_email],
                fail_silently=True,
            )
            
            messages.success(request, f'Message sent to {recipient_name} successfully.')
            return redirect('admin:accounts_customer_changelist')
        
        context = {
            'title': f'Send Message - {customer.profile.user.get_full_name()} & {trainer.profile.user.get_full_name()}',
            'customer': customer,
            'trainer': trainer,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/send_message.html', context)

    def assign_trainers_bulk(self, request, queryset):
        """Bulk assign trainers to selected customers"""
        personal_training_customers = queryset.filter(
            subscription__is_active=True,
            subscription__plan__trainer_support=True
        )
        
        if not personal_training_customers.exists():
            messages.error(request, "No customers with active personal training subscriptions selected.")
            return
        
        # Auto-assign trainers with lowest workload
        available_trainers = list(Trainer.objects.filter(is_verified=True))
        if not available_trainers:
            messages.error(request, "No verified trainers available.")
            return
        
        assigned_count = 0
        for customer in personal_training_customers:
            # Skip if already assigned
            try:
                if customer.trainer_assignment.is_active:
                    continue
            except:
                pass
            
            # Find trainer with lowest workload
            trainer_workloads = []
            for trainer in available_trainers:
                workload = trainer.assigned_customers.filter(is_active=True).count()
                trainer_workloads.append((trainer, workload))
            
            # Sort by workload and assign to trainer with least clients
            trainer_workloads.sort(key=lambda x: x[1])
            selected_trainer = trainer_workloads[0][0]
            
            # Create assignment
            TrainerAssignment.objects.create(
                customer=customer,
                trainer=selected_trainer,
                assigned_date=timezone.now(),
                is_active=True,
                notes=f"Auto-assigned by admin on {timezone.now().date()}"
            )
            
            # Send notification
            Notification.objects.create(
                customer=customer,
                title="Trainer Assigned",
                message=f"You have been assigned to trainer {selected_trainer.profile.user.get_full_name()}.",
                notification_type='trainer'
            )
            
            assigned_count += 1
        
        messages.success(request, f"Successfully assigned trainers to {assigned_count} customers.")
    
    assign_trainers_bulk.short_description = "Auto-assign trainers to selected customers"

    def remove_trainer_assignments(self, request, queryset):
        """Remove trainer assignments for selected customers"""
        removed_count = 0
        for customer in queryset:
            try:
                assignment = customer.trainer_assignment
                if assignment.is_active:
                    assignment.is_active = False
                    assignment.save()
                    removed_count += 1
            except:
                pass
        
        messages.success(request, f"Removed trainer assignments for {removed_count} customers.")
    
    remove_trainer_assignments.short_description = "Remove trainer assignments from selected customers"


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_email', 'is_verified', 'get_client_count', 
                   'average_rating', 'trainer_actions')
    list_filter = ('is_verified', 'experience_years')
    search_fields = ('profile__user__first_name', 'profile__user__last_name', 
                    'profile__user__email', 'specializations')
    actions = ['approve_trainers', 'reject_trainers']

    def get_full_name(self, obj):
        return obj.profile.user.get_full_name() or obj.profile.user.username
    get_full_name.short_description = 'Trainer Name'

    def get_email(self, obj):
        return obj.profile.user.email
    get_email.short_description = 'Email'

    def get_client_count(self, obj):
        active_count = obj.assigned_customers.filter(is_active=True).count()
        total_count = obj.assigned_customers.count()
        return f"{active_count} active / {total_count} total"
    get_client_count.short_description = 'Assigned Clients'

    def trainer_actions(self, obj):
        actions = []
        
        if obj.is_verified:
            # View assigned clients
            client_count = obj.assigned_customers.filter(is_active=True).count()
            actions.append(f'''
                <div style="margin-bottom: 5px;">
                    <strong>Status:</strong> <span style="color: green;">Verified</span>
                </div>
                <div style="margin-bottom: 5px;">
                    <strong>Active Clients:</strong> {client_count}
                </div>
            ''')
            
            if client_count > 0:
                # Use the custom URL instead of filter URL
                client_url = reverse('admin:view_trainer_clients', args=[obj.id])
                actions.append(f'''
                    <a href="{client_url}" 
                       class="button" style="margin-right: 5px;">
                        View Clients
                    </a>
                ''')
        else:
            actions.append('<span style="color: red;">Pending Verification</span>')

        return format_html(''.join(actions))
    trainer_actions.short_description = 'Actions'
    trainer_actions.allow_tags = True

    def approve_trainers(self, request, queryset):
        approved_count = 0
        for trainer in queryset:
            if not trainer.is_verified:
                trainer.is_verified = True
                trainer.profile.user.is_staff = True
                trainer.profile.user.save()
                trainer.save()
                
                send_mail(
                    subject="Trainer Account Approved",
                    message="Congratulations! Your trainer account has been approved. You can now log in and start working with clients.",
                    from_email="noreply@fitnesshub.com",
                    recipient_list=[trainer.profile.user.email],
                    fail_silently=True,
                )
                approved_count += 1
        
        messages.success(request, f"Approved {approved_count} trainers and sent notification emails.")
    approve_trainers.short_description = "Approve selected trainers"

    def reject_trainers(self, request, queryset):
        rejected_count = 0
        for trainer in queryset:
            email = trainer.profile.user.email
            trainer.profile.user.delete()
            
            send_mail(
                subject="Trainer Application Rejected",
                message="We regret to inform you that your trainer application has been rejected. Please contact support for more information.",
                from_email="noreply@fitnesshub.com",
                recipient_list=[email],
                fail_silently=True,
            )
            rejected_count += 1
        
        messages.success(request, f"Rejected {rejected_count} trainer applications and sent notifications.")
    reject_trainers.short_description = "Reject selected trainers"


@admin.register(TrainerAssignment)
class TrainerAssignmentAdmin(admin.ModelAdmin):
    list_display = ('get_customer', 'get_trainer', 'assigned_date', 'is_active', 'assignment_actions')
    list_filter = ('is_active', 'assigned_date')
    search_fields = ('customer__profile__user__first_name', 'customer__profile__user__last_name',
                    'trainer__profile__user__first_name', 'trainer__profile__user__last_name')
    date_hierarchy = 'assigned_date'

    def get_customer(self, obj):
        return obj.customer.profile.user.get_full_name()
    get_customer.short_description = 'Customer'

    def get_trainer(self, obj):
        return obj.trainer.profile.user.get_full_name()
    get_trainer.short_description = 'Trainer'

    def assignment_actions(self, obj):
        actions = []
        
        if obj.is_active:
            # Send message action
            message_url = reverse('admin:send_admin_message', 
                                args=[obj.customer.id, obj.trainer.id])
            actions.append(f'''
                <a href="{message_url}" class="button" style="margin-right: 5px;">
                    Send Message
                </a>
            ''')
            
            # View customer dashboard (if implemented)
            actions.append(f'''
                <a href="/admin/accounts/customer/{obj.customer.id}/change/" 
                   class="button" style="margin-right: 5px;">
                    View Customer
                </a>
            ''')
        else:
            actions.append('<span style="color: #666;">Inactive Assignment</span>')

        return format_html(''.join(actions))
    assignment_actions.short_description = 'Actions'
    assignment_actions.allow_tags = True


# Keep existing admin registrations
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'trainer_support', 'is_active', 'created_at')
    list_filter = ('is_active', 'trainer_support', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active', 'trainer_support')


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'plan', 'start_date', 'end_date', 'is_active', 'get_days_remaining')
    list_filter = ('is_active', 'plan', 'start_date')
    search_fields = ('customer__profile__user__username', 'customer__profile__user__email')
    readonly_fields = ('get_days_remaining', 'created_at')
    
    def get_days_remaining(self, obj):
        """Get days remaining for display"""
        try:
            days = obj.days_remaining
            if days == float('inf'):
                return "Unlimited"
            return f"{int(days)} days"
        except Exception as e:
            return "Error"
    get_days_remaining.short_description = "Days Remaining"
    get_days_remaining.admin_order_field = 'end_date'

# Keep other existing admin registrations as they were
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'amount', 'payment_method', 'status', 'payment_date')
    list_filter = ('status', 'payment_method', 'payment_date')
    search_fields = ('customer__profile__user__username', 'transaction_id')
    readonly_fields = ('transaction_id',)


@admin.register(WorkoutProgress)
class WorkoutProgressAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date', 'weight', 'bmi', 'sessions_attended')
    list_filter = ('date', 'customer')
    search_fields = ('customer__profile__user__username',)
    date_hierarchy = 'date'


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('customer', 'title', 'target_value', 'current_value', 'progress_percentage', 'status')
    list_filter = ('status', 'created_at')
    search_fields = ('customer__profile__user__username', 'title')
    readonly_fields = ('progress_percentage',)


# Update the ResourceAdmin class in admin.py

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'resource_type', 'is_premium', 'created_at', 'resource_actions')
    list_filter = ('resource_type', 'is_premium', 'created_at')
    search_fields = ('title', 'description')
    actions = ['share_with_customers']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('share-resource/<int:resource_id>/', 
                 self.admin_site.admin_view(self.share_resource_view), 
                 name='share_resource'),
        ]
        return custom_urls + urls

    def resource_actions(self, obj):
        """Actions for sharing resources"""
        share_url = reverse('admin:share_resource', args=[obj.id])
        return format_html(
            '<a href="{}" class="button">Share with Customers</a>',
            share_url
        )
    resource_actions.short_description = 'Actions'

    def share_resource_view(self, request, resource_id):
        """View for sharing resources with customers"""
        from .forms import ResourceSharingForm
        resource = get_object_or_404(Resource, id=resource_id)
        
        if request.method == 'POST':
            # Get customers with personal training subscriptions
            customer_ids = request.POST.getlist('customers')
            message = request.POST.get('message', '')
            notify_email = request.POST.get('notify_email') == 'on'
            
            if customer_ids:
                customers = Customer.objects.filter(
                    id__in=customer_ids,
                    subscription__is_active=True,
                    subscription__plan__trainer_support=True
                )
                
                shared_count = 0
                for customer in customers:
                    # Create notification for each customer
                    notification_message = f"New resource shared: {resource.title}"
                    if message:
                        notification_message += f"\n\nMessage from admin: {message}"
                    
                    Notification.objects.create(
                        customer=customer,
                        title="New Resource Shared",
                        message=notification_message,
                        notification_type='general'
                    )
                    
                    # Send email if requested
                    if notify_email:
                        self.send_resource_email(customer, resource, message)
                    
                    shared_count += 1
                
                messages.success(request, f'Resource shared with {shared_count} customers.')
                return redirect('admin:accounts_resource_changelist')
            else:
                messages.error(request, 'Please select at least one customer.')
                return redirect(f'/admin/accounts/resource/share-resource/{resource_id}/')
        
        # GET request - show form
        # Get customers with personal training subscriptions
        customers = Customer.objects.filter(
            subscription__is_active=True,
            subscription__plan__trainer_support=True
        ).select_related('profile__user', 'trainer_assignment__trainer__profile__user')
        
        context = {
            'title': f'Share Resource: {resource.title}',
            'resource': resource,
            'customers': customers,
            'opts': self.model._meta,
            'has_change_permission': True,
        }
        
        return render(request, 'admin/share_resource.html', context)
    
    def send_resource_email(self, customer, resource, admin_message):
        """Send email notification about shared resource"""
        email_content = f"""
        Hello {customer.profile.user.get_full_name()},

        A new resource has been shared with you: {resource.title}

        Description: {resource.description}
        
        You can access this resource from your dashboard under the Resources section.
        """
        
        if admin_message:
            email_content += f"\n\nMessage from admin:\n{admin_message}"
        
        email_content += "\n\nBest regards,\nFitnessHub Team"
        
        send_mail(
            subject=f"New Resource: {resource.title}",
            message=email_content,
            from_email="noreply@fitnesshub.com",
            recipient_list=[customer.profile.user.email],
            fail_silently=True,
        )

    def share_with_customers(self, request, queryset):
        """Bulk action to share resources with customers"""
        # For bulk action, redirect to the first resource's share page
        if queryset.count() == 1:
            resource = queryset.first()
            return redirect('admin:share_resource', resource_id=resource.id)
        else:
            messages.info(request, "Please select only one resource to share at a time.")
    share_with_customers.short_description = "Share selected resource with customers"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('customer', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('customer__profile__user__username', 'title')
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} notifications marked as read.")
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, f"{queryset.count()} notifications marked as unread.")
    mark_as_unread.short_description = "Mark selected notifications as unread"


@admin.register(TrainerMessage)
class TrainerMessageAdmin(admin.ModelAdmin):
    list_display = ('customer', 'trainer', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('customer__profile__user__username', 'trainer__profile__user__username', 'subject')
    readonly_fields = ('created_at',)