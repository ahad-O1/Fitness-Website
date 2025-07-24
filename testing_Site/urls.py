from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render, redirect

def smart_home(request):
    if request.user.is_authenticated:
        # Redirect logged-in users to their appropriate dashboard
        if hasattr(request.user, 'profile'):
            if request.user.profile.role == 'customer':
                return redirect('customer_dashboard')
            elif request.user.profile.role == 'trainer':
                return redirect('trainer_dashboard')
        return redirect('customer_dashboard')  # Default fallback
    else:
        # Show landing page for non-logged-in users
        return render(request, 'index.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.url')),
    path('', smart_home, name='home'),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)