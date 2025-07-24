from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

class TrainerRegistration(models.Model):
    # Email as primary key
    email = models.EmailField(primary_key=True, unique=True, max_length=255)
    
    # Basic Information
    username = models.CharField(
        max_length=100,
        validators=[RegexValidator(
            regex=r'^[a-zA-Z ]+$',
            message='Username can only contain letters and spaces.'
        )]
    )
    
    # Phone number with validation
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\+\d{1,4}\d{9,11}$',
            message='Phone number must start with country code (e.g. +92) and be up to 15 digits.'
        )]
    )
    
    # Address
    address = models.TextField(help_text="Complete address (minimum 10 characters)")
    
    # Password (hashed)
    password = models.CharField(max_length=128)  # Will store hashed password
    
    # Registration status
    REGISTRATION_STATUS = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=REGISTRATION_STATUS,
        default='pending'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Admin approval details
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_trainers'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Link to created user account (after approval)
    user_account = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='trainer_registration'
    )
    
    class Meta:
        db_table = 'trainer_registrations'
        verbose_name = 'Trainer Registration'
        verbose_name_plural = 'Trainer Registrations'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.email}) - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Hash password before saving if it's not already hashed
        from django.contrib.auth.hashers import make_password, check_password
        
        if self.password and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        
        super().save(*args, **kwargs)
    
    def set_password(self, raw_password):
        """Set password using Django's password hashing"""
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """Check password using Django's password verification"""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)
    
    def approve_registration(self, admin_user):
        """Approve trainer registration and create user account"""
        from django.contrib.auth.models import User
        
        if self.status == 'approved':
            return False, "Registration is already approved"
        
        try:
            # Create Django User account
            user = User.objects.create_user(
                username=self.email,  # Using email as username
                email=self.email,
                password=None  # We'll set this separately
            )
            
            # Set the hashed password from registration
            user.password = self.password
            user.first_name = self.username.split()[0] if self.username else ""
            user.last_name = " ".join(self.username.split()[1:]) if len(self.username.split()) > 1 else ""
            user.save()
            
            # Update registration status
            self.status = 'approved'
            self.approved_by = admin_user
            self.approval_date = timezone.now()
            self.user_account = user
            self.save()
            
            return True, "Trainer account created successfully"
            
        except Exception as e:
            return False, f"Error creating account: {str(e)}"
    
    def reject_registration(self, admin_user, reason=""):
        """Reject trainer registration"""
        self.status = 'rejected'
        self.approved_by = admin_user
        self.approval_date = timezone.now()
        self.rejection_reason = reason
        self.save()
        
        return True, "Registration rejected successfully"


class TrainerProfile(models.Model):
    """Extended profile for approved trainers"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='trainer_profile')
    registration = models.OneToOneField(TrainerRegistration, on_delete=models.CASCADE, related_name='profile')
    
    # Additional trainer-specific fields
    specializations = models.TextField(blank=True, help_text="Training specializations")
    experience_years = models.PositiveIntegerField(default=0)
    certifications = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/trainers/', null=True, blank=True)
    
    # Availability
    is_available = models.BooleanField(default=True)
    
    # Ratings and reviews
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'trainer_profiles'
        verbose_name = 'Trainer Profile'
        verbose_name_plural = 'Trainer Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Trainer Profile"


class Profile(models.Model):
    """Base profile model for all users"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\+\d{1,4}\d{9,11}$',
            message='Phone number must start with country code (e.g. +92) and be up to 15 digits.'
        )]
    )
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('trainer', 'Trainer'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class Customer(models.Model):
    """Customer-specific profile"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='customer')
    
    # Customer-specific fields
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10, 
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], 
        blank=True
    )
    height = models.FloatField(help_text="Height in cm", null=True, blank=True)
    weight = models.FloatField(help_text="Weight in kg", null=True, blank=True)
    fitness_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced')
        ],
        default='beginner'
    )
    fitness_goals = models.TextField(blank=True, null=True)
    medical_conditions = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
    
    def __str__(self):
        return f"Customer: {self.profile.user.username}"
    
    @property
    def get_full_name(self):
        return self.profile.user.get_full_name() or self.profile.user.username


class Trainer(models.Model):
    """Trainer-specific profile (legacy model)"""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='trainer')
    address = models.TextField(help_text="Trainer's address")
    is_verified = models.BooleanField(default=False, help_text="Whether the trainer is verified by admin")
    bio = models.TextField(blank=True, null=True)
    specializations = models.TextField(blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'trainers'
        verbose_name = 'Trainer'
        verbose_name_plural = 'Trainers'
    
    def __str__(self):
        return f"Trainer: {self.profile.user.username}"
    
    @property
    def get_full_name(self):
        return self.profile.user.get_full_name() or self.profile.user.username


class SubscriptionPlan(models.Model):
    """Available subscription plans"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(help_text="Plan duration in days")
    features = models.JSONField(default=dict, help_text="Plan features as JSON")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    trial_days = models.PositiveIntegerField(default=0)
    
    # Feature flags for easy template access
    workout_videos = models.BooleanField(default=False)
    meal_plans = models.BooleanField(default=False)
    trainer_support = models.BooleanField(default=False)
    progress_tracking = models.BooleanField(default=True)
    live_sessions = models.BooleanField(default=False)
    personal_sessions = models.BooleanField(default=False)
    nutrition_guidance = models.BooleanField(default=False)
    premium_content = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['price']
    
    @property
    def monthly_equivalent(self):
        """Calculate monthly equivalent price"""
        return (self.price * 30) / self.duration_days
    
    def __str__(self):
        return f"{self.name} - ${self.price}"


class CustomerSubscription(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)  # Add this field if missing
    
    class Meta:
        db_table = 'customer_subscriptions'
        verbose_name = 'Customer Subscription'
        verbose_name_plural = 'Customer Subscriptions'
    
    def __str__(self):
        return f"{self.customer.profile.user.username} - {self.plan.name}"
    
    @property
    def is_expired(self):
        """Check if the subscription is expired"""
        if self.end_date is None:
            return False  # If no end_date is set, subscription never expires
        return timezone.now() > self.end_date
    
    @property
    def days_remaining(self):
        """Calculate days remaining in subscription"""
        if self.end_date is None:
            return float('inf')  # Infinite days for subscriptions without end date
        
        remaining = (self.end_date - timezone.now()).days
        return max(0, remaining)
    
    def save(self, *args, **kwargs):
        """Override save to set end_date based on plan duration"""
        if not self.pk and self.plan:  # New subscription
            if self.plan.duration_days and self.plan.duration_days > 0:
                # Only set end_date if plan has a duration
                self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        
        # Update is_active based on expiration
        if self.end_date and self.is_expired:
            self.is_active = False
        
        super().save(*args, **kwargs)
    
    def extend_subscription(self, days):
        """Extend the subscription by specified days"""
        if self.end_date:
            self.end_date += timedelta(days=days)
        else:
            # If no end_date was set, set it from now
            self.end_date = timezone.now() + timedelta(days=days)
        
        self.is_active = True
        self.save()
    
    def cancel_subscription(self):
        """Cancel the subscription"""
        self.is_active = False
        self.auto_renew = False
        self.save()


class Payment(models.Model):
    """Payment history"""
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD = [
        ('card', 'Credit/Debit Card'),
        ('paypal', 'PayPal'),
        ('bank', 'Bank Transfer'),
        ('stripe', 'Stripe'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(CustomerSubscription, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    transaction_id = models.CharField(max_length=255, unique=True)
    payment_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment ${self.amount} by {self.customer}"


class TrainerAssignment(models.Model):
    """Customer-Trainer assignment"""
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='trainer_assignment')
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name='assigned_customers')
    assigned_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.customer} assigned to {self.trainer}"


class WorkoutProgress(models.Model):
    """Customer workout progress tracking"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='progress')
    date = models.DateField(default=timezone.now)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    sessions_attended = models.PositiveIntegerField(default=0)
    trainer_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['customer', 'date']
    
    def __str__(self):
        return f"{self.customer} - {self.date}"


class Goal(models.Model):
    """Customer goals and milestones"""
    GOAL_STATUS = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ]
    
    GOAL_TYPES = [
        ('weight_loss', 'Weight Loss'),
        ('weight_gain', 'Weight Gain'),
        ('muscle_gain', 'Muscle Gain'),
        ('endurance', 'Endurance'),
        ('strength', 'Strength'),
        ('flexibility', 'Flexibility'),
        ('other', 'Other')
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=200)
    description = models.TextField()
    goal_type = models.CharField(max_length=20, choices=GOAL_TYPES, default='other')
    target_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=50, blank=True, help_text="e.g., kg, lbs, minutes")
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=GOAL_STATUS, default='active')
    is_active = models.BooleanField(default=True)  # For compatibility
    is_completed = models.BooleanField(default=False)  # For compatibility
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    @property
    def progress_percentage(self):
        if self.target_value and self.target_value > 0:
            return min(100, (float(self.current_value) / float(self.target_value)) * 100)
        return 0
    
    def save(self, *args, **kwargs):
        # Sync the boolean fields with status
        self.is_active = self.status == 'active'
        self.is_completed = self.status == 'completed'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.customer} - {self.title}"


class ResourceCategory(models.Model):
    """Resource categories"""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Resource Categories"

    def __str__(self):
        return self.name


class Resource(models.Model):
    """Training resources and downloads"""
    RESOURCE_TYPE = [
        ('video', 'Video'),
        ('pdf', 'PDF Document'),
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('link', 'External Link'),
        ('document', 'Document'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE)
    category = models.ForeignKey(ResourceCategory, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='resources/', null=True, blank=True)
    external_url = models.URLField(null=True, blank=True)
    file_url = models.URLField(null=True, blank=True)  # Alias for compatibility
    is_premium = models.BooleanField(default=False, help_text="Only for premium subscribers")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Sync file_url with external_url for compatibility
        if self.external_url and not self.file_url:
            self.file_url = self.external_url
        super().save(*args, **kwargs)
    
    def get_resource_type_display(self):
        return dict(self.RESOURCE_TYPE)[self.resource_type]
    
    def __str__(self):
        return self.title


class Notification(models.Model):
    """Customer notifications"""
    NOTIFICATION_TYPE = [
        ('subscription', 'Subscription'),
        ('session', 'Session'),
        ('message', 'Message'),
        ('payment', 'Payment'),
        ('general', 'General'),
        ('trainer', 'Trainer'),
        ('goal', 'Goal'),
        ('progress', 'Progress'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer} - {self.title}"


class TrainerMessage(models.Model):
    """Messages from trainer to customer"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='trainer_messages')
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name='sent_messages')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    content = models.TextField(blank=True)  # Alias for compatibility
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For compatibility with templates expecting sender/recipient
    @property
    def sender(self):
        return self.trainer.profile.user
    
    @property
    def recipient(self):
        return self.customer.profile.user
    
    def save(self, *args, **kwargs):
        # Sync content with message for compatibility
        if self.message and not self.content:
            self.content = self.message
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message from {self.trainer} to {self.customer}"


class Session(models.Model):
    """Training sessions"""
    SESSION_STATUS = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ]
    
    SESSION_TYPES = [
        ('personal', 'Personal Training'),
        ('group', 'Group Session'),
        ('consultation', 'Consultation'),
        ('assessment', 'Fitness Assessment')
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sessions')
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name='sessions')
    session_date = models.DateField()
    session_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='personal')
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='scheduled')
    notes = models.TextField(blank=True, null=True)
    trainer_notes = models.TextField(blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For compatibility - add these properties
    @property
    def scheduled_date(self):
        return self.session_date
    
    @property
    def scheduled_time(self):
        return self.session_time
    
    class Meta:
        unique_together = ('trainer', 'session_date', 'session_time')
        ordering = ['session_date', 'session_time']
    
    def __str__(self):
        return f"{self.customer} - {self.session_date} {self.session_time}"


class TrainerRating(models.Model):
    """Trainer ratings from customers"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='trainer_ratings')
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('customer', 'trainer')
    
    def __str__(self):
        return f"{self.customer} rated {self.trainer}: {self.rating} stars"