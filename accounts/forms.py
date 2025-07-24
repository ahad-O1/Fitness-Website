from django import forms
from django.contrib.auth.models import User
from .models import Profile, Trainer
from .models import Trainer, TrainerAssignment, TrainerMessage, Resource, Customer

class CustomerSignupForm(forms.ModelForm):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField()

    class Meta:
        model = Profile
        fields = ['phone']

    def save(self):
        # if('password' is 'password2'):
         user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            email=self.cleaned_data['email'],
         )
         profile = Profile.objects.create(user=user, role='customer', phone=self.cleaned_data['phone'])
         from .models import Customer
         Customer.objects.create(profile=profile)
         return user
        # else:
        #     raise forms.ValidationError("Password and Confirm Password do not match.")
class TrainerSignupForm(forms.ModelForm):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)
    address = forms.CharField(widget=forms.Textarea)
    email = forms.EmailField()

    class Meta:
        model = Profile
        fields = ['phone']

    def save(self):
    #  if('password' is 'password2'):
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password'],
            email=self.cleaned_data['email'],
        )
        profile = Profile.objects.create(user=user, role='trainer', phone=self.cleaned_data['phone'])
        Trainer.objects.create(profile=profile, address=self.cleaned_data['address'])
        return user
    #  else:
    #         raise forms.ValidationError("Password and Confirm Password do not match.")

class TrainerAssignmentForm(forms.ModelForm):
    trainer = forms.ModelChoiceField(
        queryset=Trainer.objects.filter(is_verified=True),
        empty_label="Select a trainer...",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Assignment notes, special instructions, etc.'
        })
    )

    class Meta:
        model = TrainerAssignment
        fields = ['trainer', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['trainer'].label_from_instance = self.trainer_label_from_instance

    def trainer_label_from_instance(self, trainer):
        active_clients = trainer.assigned_customers.filter(is_active=True).count()
        rating = trainer.average_rating or 0
        return f"{trainer.profile.user.get_full_name()} - {active_clients} clients - {rating:.1f}★"


class AdminMessageForm(forms.Form):
    sender = forms.ChoiceField(
        choices=[
            ('trainer', 'From Trainer to Customer'),
            ('customer', 'From Customer to Trainer'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Message subject'
        })
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Type your message here...'
        })
    )


class ResourceSharingForm(forms.Form):
    customers = forms.ModelMultipleChoiceField(
        queryset=Customer.objects.filter(
            subscription__is_active=True,
            subscription__plan__trainer_support=True
        ),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=True
    )
    
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional message to include with the resource...'
        }),
        label="Personal Message"
    )
    
    notify_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send email notification"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customers'].label_from_instance = self.customer_label_from_instance

    def customer_label_from_instance(self, customer):
        trainer_name = "No Trainer"
        try:
            if customer.trainer_assignment.is_active:
                trainer_name = customer.trainer_assignment.trainer.profile.user.get_full_name()
        except:
            pass
        return f"{customer.profile.user.get_full_name()} - {trainer_name}"