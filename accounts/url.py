from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from . import dashboard_views
from . import trainer_dashboard_views

urlpatterns = [
    # Trainer registration (existing)
    path('signup/', views.trainer_signup, name='trainer_signup'),
    
    # AJAX endpoints (existing)
    path('check-email/', views.check_email_availability, name='check_email_availability'),
    path('registration-status/', views.registration_status, name='registration_status'),
    
    # Admin utilities (existing)
    path('api/pending-count/', views.pending_registrations_count, name='pending_registrations_count'),

    # Customer and Trainer Signup (existing)
    path("sign-up/customer/", views.signup_customer, name="signup_customer"),
    path("sign-up/trainer/", views.signup_trainer, name="signup_trainer"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("select-signup/", views.select_signup, name="select_signup"),
    
    # Authentication (existing)
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    
    # Password reset URLs (existing)
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    # CUSTOMER DASHBOARD URLs (existing)
    path('customer/dashboard/', dashboard_views.customer_dashboard, name='customer_dashboard'),
    path('customer/profile/', dashboard_views.customer_profile, name='customer_profile'),
    path('customer/change-password/', dashboard_views.change_password, name='change_password'),
    path('customer/delete-account/', dashboard_views.delete_account, name='delete_account'),
    path('customer/subscription/', dashboard_views.subscription_details, name='subscription_details'),
    path('customer/subscription/plans/', dashboard_views.subscription_plans, name='subscription_plans'),
    path('customer/subscription/subscribe/<int:plan_id>/', dashboard_views.subscribe_to_plan, name='subscribe_to_plan'),
    path('customer/subscription/toggle-auto-renew/', dashboard_views.toggle_auto_renew, name='toggle_auto_renew'),
    path('customer/subscription/cancel/', dashboard_views.cancel_subscription, name='cancel_subscription'),
    path('customer/subscription/invoice/<int:subscription_id>/', dashboard_views.download_invoice, name='download_invoice'),
    path('customer/payments/', dashboard_views.payment_history, name='payment_history'),
    path('customer/trainer/', dashboard_views.trainer_info, name='trainer_info'),
    path('customer/trainer/rate/<int:trainer_id>/', dashboard_views.rate_trainer, name='rate_trainer'),
    path('customer/trainer/schedule-session/', dashboard_views.schedule_session, name='schedule_session'),
    path('customer/trainer/request-workout-plan/', dashboard_views.request_workout_plan, name='request_workout_plan'),
    path('customer/trainer/request-change/', dashboard_views.request_trainer_change, name='request_trainer_change'),
    path('customer/progress/', dashboard_views.workout_progress, name='workout_progress'),
    path('customer/goals/', dashboard_views.goals_management, name='goals_management'),
    path('customer/resources/', dashboard_views.resources_downloads, name='resources_downloads'),
    path('customer/resources/download/<int:resource_id>/', dashboard_views.download_resource, name='download_resource'),
    path('customer/notifications/', dashboard_views.notifications_list, name='notifications_list'),
    # FIXED: Separate customer messages URL
    path('customer/messages/', dashboard_views.trainer_messages, name='customer_messages'),
    path('api/customer/notifications-count/', dashboard_views.api_notifications_count, name='api_notifications_count'),
    path('api/customer/subscription-status/', dashboard_views.api_subscription_status, name='api_subscription_status'),

    # TRAINER DASHBOARD URLs - Fixed URL names to avoid conflicts
    path('trainer/dashboard/', trainer_dashboard_views.trainer_dashboard, name='trainer_dashboard'),
    path('trainer/clients/', trainer_dashboard_views.trainer_clients, name='trainer_clients'),
    path('trainer/clients/<int:client_id>/', trainer_dashboard_views.trainer_client_detail, name='trainer_client_detail'),
    path('trainer/clients/<int:client_id>/progress/', trainer_dashboard_views.view_client_progress, name='view_client_progress'),
    path('trainer/sessions/', trainer_dashboard_views.trainer_sessions, name='trainer_sessions'),
    path('trainer/schedule/', trainer_dashboard_views.trainer_schedule, name='trainer_schedule'),
    path('trainer/sessions/<int:session_id>/update-status/', trainer_dashboard_views.update_session_status, name='update_session_status'),
    path('trainer/sessions/<int:session_id>/add-notes/', trainer_dashboard_views.add_session_notes, name='add_session_notes'),
    # FIXED: Trainer messages with different URL
    path('trainer/messages/', trainer_dashboard_views.trainer_messages, name='trainer_messages'),
    path('trainer/progress/', trainer_dashboard_views.trainer_progress, name='trainer_progress'),
    path('trainer/resources/', trainer_dashboard_views.trainer_resources, name='trainer_resources'),
    path('trainer/reports/', trainer_dashboard_views.trainer_reports, name='trainer_reports'),
    path('trainer/profile/', trainer_dashboard_views.trainer_profile, name='trainer_profile'),
    path('api/trainer/dashboard-updates/', trainer_dashboard_views.trainer_dashboard_updates, name='trainer_dashboard_updates'),
]
