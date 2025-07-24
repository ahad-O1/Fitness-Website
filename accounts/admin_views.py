# admin_views.py - Create this new file for custom admin views

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Count, Q, Avg
from django.core.paginator import Paginator

from .models import (
    Customer, Trainer, TrainerAssignment, Resource, TrainerMessage, 
    Notification, SubscriptionPlan, CustomerSubscription
)
from .forms import TrainerAssignmentForm, AdminMessageForm, ResourceSharingForm


@method_decorator(staff_member_required, name='dispatch')
class AdminDashboardView(View):
    """Enhanced admin dashboard for trainer assignments"""
    
    def get(self, request):
        # Get comprehensive statistics
        stats = self.get_dashboard_stats()
        recent_assignments = self.get_recent_assignments()
        trainer_workload = self.get_trainer_workload()
        unassigned_customers = self.get_unassigned_customers()
        
        context = {
            'title': 'Trainer Assignment Dashboard',
            'stats': stats,
            'recent_assignments': recent_assignments,
            'trainer_workload': trainer_workload,
            'unassigned_customers': unassigned_customers,
        }
        
        return render(request, 'admin/trainer_assignment_dashboard.html', context)
    
    def get_dashboard_stats(self):
        """Calculate dashboard statistics"""
        personal_training_customers = Customer.objects.filter(
            subscription__is_active=True,
            subscription__plan__trainer_support=True
        )
        
        assigned_customers = TrainerAssignment.objects.filter(is_active=True).count()
        active_trainers = Trainer.objects.filter(
            is_verified=True,
            assigned_customers__is_active=True
        ).distinct().count()
        
        # Average clients per trainer
        avg_clients_per_trainer = 0
        if active_trainers > 0:
            avg_clients_per_trainer = assigned_customers / active_trainers
        
        return {
            'total_customers': personal_training_customers.count(),
            'assigned_customers': assigned_customers,
            'unassigned_customers': personal_training_customers.count() - assigned_customers,
            'active_trainers': active_trainers,
            'avg_clients_per_trainer': round(avg_clients_per_trainer, 1),
            'total_trainers': Trainer.objects.filter(is_verified=True).count(),
        }
    
    def get_recent_assignments(self, limit=10):
        """Get recent trainer assignments"""
        return TrainerAssignment.objects.filter(
            is_active=True
        ).select_related(
            'customer__profile__user',
            'trainer__profile__user'
        ).order_by('-assigned_date')[:limit]
    
    def get_trainer_workload(self):
        """Get trainer workload information"""
        trainers = Trainer.objects.filter(is_verified=True).annotate(
            active_clients=Count('assigned_customers', filter=Q(assigned_customers__is_active=True))
        ).select_related('profile__user').order_by('-active_clients')
        
        workload_data = []
        for trainer in trainers:
            availability = 'High'
            if trainer.active_clients >= 10:
                availability = 'Low'
            elif trainer.active_clients >= 5:
                availability = 'Medium'
            
            workload_data.append({
                'trainer': trainer,
                'active_clients': trainer.active_clients,
                'availability': availability,
                'average_rating': trainer.average_rating,
            })
        
        return workload_data
    
    def get_unassigned_customers(self, limit=5):
        """Get customers who need trainer assignment"""
        return Customer.objects.filter(
            subscription__is_active=True,
            subscription__plan__trainer_support=True
        ).exclude(
            trainer_assignment__is_active=True
        ).select_related('profile__user', 'subscription__plan')[:limit]


@method_decorator(staff_member_required, name='dispatch')
class AdminTrainerAssignmentView(View):
    """View for assigning trainers to customers"""
    
    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Verify customer has personal training subscription
        if not self.has_personal_training_subscription(customer):
            messages.error(request, 'Customer does not have an active personal training subscription.')
            return redirect('admin:accounts_customer_changelist')
        
        # Get form with existing assignment data
        initial_data = {}
        try:
            existing = customer.trainer_assignment
            initial_data = {
                'trainer': existing.trainer,
                'notes': existing.notes
            }
        except TrainerAssignment.DoesNotExist:
            pass
        
        form = TrainerAssignmentForm(initial=initial_data)
        available_trainers = self.get_available_trainers()
        
        context = {
            'title': f'Assign Trainer to {customer.profile.user.get_full_name()}',
            'customer': customer,
            'form': form,
            'available_trainers': available_trainers,
            'has_existing_assignment': hasattr(customer, 'trainer_assignment') and customer.trainer_assignment.is_active,
        }
        
        return render(request, 'admin/assign_trainer.html', context)
    
    def post(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        
        if not self.has_personal_training_subscription(customer):
            messages.error(request, 'Customer does not have an active personal training subscription.')
            return redirect('admin:accounts_customer_changelist')
        
        form = TrainerAssignmentForm(request.POST)
        if form.is_valid():
            trainer = form.cleaned_data['trainer']
            notes = form.cleaned_data['notes']
            
            # Deactivate existing assignment
            try:
                existing = customer.trainer_assignment
                existing.is_active = False
                existing.end_date = timezone.now()
                existing.save()
            except TrainerAssignment.DoesNotExist:
                pass
            
            # Create new assignment
            assignment = TrainerAssignment.objects.create(
                customer=customer,
                trainer=trainer,
                assigned_date=timezone.now(),
                is_active=True,
                notes=notes
            )
            
            # Send notifications
            self.send_assignment_notifications(customer, trainer)
            
            messages.success(
                request, 
                f'Successfully assigned {trainer.profile.user.get_full_name()} to {customer.profile.user.get_full_name()}'
            )
            return redirect('admin:accounts_customer_changelist')
        
        # Form is invalid, re-render with errors
        available_trainers = self.get_available_trainers()
        context = {
            'customer': customer,
            'form': form,
            'available_trainers': available_trainers,
        }
        return render(request, 'admin/assign_trainer.html', context)
    
    def has_personal_training_subscription(self, customer):
        """Check if customer has active personal training subscription"""
        try:
            return (hasattr(customer, 'subscription') and 
                   customer.subscription.is_active and 
                   customer.subscription.plan.trainer_support)
        except:
            return False
    
    def get_available_trainers(self):
        """Get list of available trainers with their workload"""
        return Trainer.objects.filter(is_verified=True).annotate(
            active_clients=Count('assigned_customers', filter=Q(assigned_customers__is_active=True))
        ).select_related('profile__user').order_by('active_clients')
    
    def send_assignment_notifications(self, customer, trainer):
        """Send notifications about the assignment"""
        # Notification to customer
        Notification.objects.create(
            customer=customer,
            title="Trainer Assigned",
            message=f"You have been assigned to trainer {trainer.profile.user.get_full_name()}. They will contact you soon to begin your training sessions.",
            notification_type='trainer'
        )
        
        # Email to customer
        send_mail(
            subject="New Trainer Assignment - FitnessHub",
            message=f"""
            Hello {customer.profile.user.get_full_name()},

            You have been assigned to trainer {trainer.profile.user.get_full_name()}.
            
            Your trainer will contact you soon to schedule your first session and discuss your fitness goals.
            
            Trainer Details:
            - Name: {trainer.profile.user.get_full_name()}
            - Experience: {trainer.experience_years} years
            - Specializations: {trainer.specializations or 'Not specified'}
            
            You can contact your trainer through your dashboard or they will reach out to you directly.
            
            Best regards,
            FitnessHub Team
            """,
            from_email="noreply@fitnesshub.com",
            recipient_list=[customer.profile.user.email],
            fail_silently=True,
        )
        
        # Email to trainer
        send_mail(
            subject="New Client Assignment - FitnessHub",
            message=f"""
            Hello {trainer.profile.user.get_full_name()},

            You have been assigned a new client: {customer.profile.user.get_full_name()}.
            
            Client Details:
            - Name: {customer.profile.user.get_full_name()}
            - Email: {customer.profile.user.email}
            - Phone: {customer.profile.phone or 'Not provided'}
            - Fitness Level: {customer.fitness_level.title()}
            - Goals: {customer.fitness_goals or 'Not specified'}
            
            Please log into your trainer dashboard to view more details and start scheduling sessions.
            
            Best regards,
            FitnessHub Team
            """,
            from_email="noreply@fitnesshub.com",
            recipient_list=[trainer.profile.user.email],
            fail_silently=True,
        )


@method_decorator(staff_member_required, name='dispatch')
class AdminResourceSharingView(View):
    """View for sharing resources with customers"""
    
    def get(self, request, resource_id):
        resource = get_object_or_404(Resource, id=resource_id)
        form = ResourceSharingForm()
        
        context = {
            'title': f'Share Resource: {resource.title}',
            'resource': resource,
            'form': form,
        }
        
        return render(request, 'admin/share_resource.html', context)
    
    def post(self, request, resource_id):
        resource = get_object_or_404(Resource, id=resource_id)
        form = ResourceSharingForm(request.POST)
        
        if form.is_valid():
            customers = form.cleaned_data['customers']
            message = form.cleaned_data['message']
            notify_email = form.cleaned_data['notify_email']
            
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
        
        context = {
            'resource': resource,
            'form': form,
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
            email_content += f"\n\nPersonal message from admin:\n{admin_message}"
        
        email_content += "\n\nBest regards,\nFitnessHub Team"
        
        send_mail(
            subject=f"New Resource: {resource.title}",
            message=email_content,
            from_email="noreply@fitnesshub.com",
            recipient_list=[customer.profile.user.email],
            fail_silently=True,
        )


@method_decorator(staff_member_required, name='dispatch')
class AdminMessageView(View):
    """View for facilitating messages between trainers and customers"""
    
    def get(self, request, customer_id, trainer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        trainer = get_object_or_404(Trainer, id=trainer_id)
        
        # Verify the assignment
        try:
            assignment = TrainerAssignment.objects.get(
                customer=customer,
                trainer=trainer,
                is_active=True
            )
        except TrainerAssignment.DoesNotExist:
            messages.error(request, 'No active assignment found between this customer and trainer.')
            return redirect('admin:accounts_customer_changelist')
        
        form = AdminMessageForm()
        recent_messages = self.get_recent_messages(customer, trainer)
        
        context = {
            'title': f'Send Message - {customer.profile.user.get_full_name()} & {trainer.profile.user.get_full_name()}',
            'customer': customer,
            'trainer': trainer,
            'assignment': assignment,
            'form': form,
            'recent_messages': recent_messages,
        }
        
        return render(request, 'admin/send_message.html', context)
    
    def post(self, request, customer_id, trainer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        trainer = get_object_or_404(Trainer, id=trainer_id)
        
        form = AdminMessageForm(request.POST)
        if form.is_valid():
            sender = form.cleaned_data['sender']
            subject = form.cleaned_data['subject']
            message_content = form.cleaned_data['message']
            
            if sender == 'trainer':
                # Message from trainer to customer
                TrainerMessage.objects.create(
                    customer=customer,
                    trainer=trainer,
                    subject=f"[Admin] {subject}",
                    message=f"Message facilitated by admin:\n\n{message_content}"
                )
                
                # Notification to customer
                Notification.objects.create(
                    customer=customer,
                    title="New Message from Trainer",
                    message=f"Your trainer sent you a message: {subject}",
                    notification_type='message'
                )
                
                recipient = customer
                recipient_email = customer.profile.user.email
                sender_name = trainer.profile.user.get_full_name()
            
            # Send email notification
            send_mail(
                subject=f"New Message: {subject}",
                message=f"""
                Hello {recipient.profile.user.get_full_name()},

                You have received a new message from {sender_name}.

                Subject: {subject}
                Message: {message_content}

                Please log into your dashboard to view and respond to this message.

                Best regards,
                FitnessHub Team
                """,
                from_email="noreply@fitnesshub.com",
                recipient_list=[recipient_email],
                fail_silently=True,
            )
            
            messages.success(request, 'Message sent successfully.')
            return redirect('admin:accounts_customer_changelist')
        
        recent_messages = self.get_recent_messages(customer, trainer)
        context = {
            'customer': customer,
            'trainer': trainer,
            'form': form,
            'recent_messages': recent_messages,
        }
        return render(request, 'admin/send_message.html', context)
    
    def get_recent_messages(self, customer, trainer, limit=5):
        """Get recent messages between customer and trainer"""
        return TrainerMessage.objects.filter(
            customer=customer,
            trainer=trainer
        ).order_by('-created_at')[:limit]


# Additional utility views

@staff_member_required
def bulk_assign_trainers_view(request):
    """Bulk assign trainers to multiple customers"""
    if request.method == 'POST':
        customer_ids = request.POST.getlist('customer_ids')
        assignment_method = request.POST.get('assignment_method')
        specific_trainer_id = request.POST.get('specific_trainer')
        notes = request.POST.get('notes', '')
        
        customers = Customer.objects.filter(
            id__in=customer_ids,
            subscription__is_active=True,
            subscription__plan__trainer_support=True
        )
        
        if assignment_method == 'auto':
            # Auto-assign with load balancing
            assigned_count = auto_assign_trainers(customers, notes)
        elif assignment_method == 'specific' and specific_trainer_id:
            # Assign to specific trainer
            trainer = get_object_or_404(Trainer, id=specific_trainer_id, is_verified=True)
            assigned_count = assign_to_specific_trainer(customers, trainer, notes)
        else:
            messages.error(request, 'Invalid assignment method.')
            return redirect('admin:accounts_customer_changelist')
        
        messages.success(request, f'Successfully assigned trainers to {assigned_count} customers.')
        return redirect('admin:accounts_customer_changelist')
    
    # GET request - show form
    customers = Customer.objects.filter(
        subscription__is_active=True,
        subscription__plan__trainer_support=True
    ).exclude(trainer_assignment__is_active=True)
    
    trainers = Trainer.objects.filter(is_verified=True)
    
    context = {
        'customers': customers,
        'trainers': trainers,
    }
    return render(request, 'admin/bulk_assign_trainers.html', context)


def auto_assign_trainers(customers, notes):
    """Auto-assign trainers with load balancing"""
    trainers = list(Trainer.objects.filter(is_verified=True))
    if not trainers:
        return 0
    
    assigned_count = 0
    for customer in customers:
        # Skip if already assigned
        if hasattr(customer, 'trainer_assignment') and customer.trainer_assignment.is_active:
            continue
        
        # Find trainer with lowest workload
        trainer_workloads = []
        for trainer in trainers:
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
            notes=notes or f"Auto-assigned on {timezone.now().date()}"
        )
        
        # Send notifications
        send_assignment_notifications(customer, selected_trainer)
        assigned_count += 1
    
    return assigned_count


def assign_to_specific_trainer(customers, trainer, notes):
    """Assign multiple customers to a specific trainer"""
    assigned_count = 0
    for customer in customers:
        # Skip if already assigned
        if hasattr(customer, 'trainer_assignment') and customer.trainer_assignment.is_active:
            continue
        
        # Create assignment
        TrainerAssignment.objects.create(
            customer=customer,
            trainer=trainer,
            assigned_date=timezone.now(),
            is_active=True,
            notes=notes or f"Bulk assigned on {timezone.now().date()}"
        )
        
        # Send notifications
        send_assignment_notifications(customer, trainer)
        assigned_count += 1
    
    return assigned_count


def send_assignment_notifications(customer, trainer):
    """Helper function to send notifications for new assignments"""
    # Customer notification
    Notification.objects.create(
        customer=customer,
        title="Trainer Assigned",
        message=f"You have been assigned to trainer {trainer.profile.user.get_full_name()}.",
        notification_type='trainer'
    )
    
    # Send emails (simplified version)
    send_mail(
        subject="New Trainer Assignment",
        message=f"You have been assigned to trainer {trainer.profile.user.get_full_name()}.",
        from_email="noreply@fitnesshub.com",
        recipient_list=[customer.profile.user.email],
        fail_silently=True,
    )