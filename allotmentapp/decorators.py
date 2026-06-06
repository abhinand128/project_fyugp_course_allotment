from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from functools import wraps

def group_required(group_name):
    """Decorator to check if a user belongs to a specific group."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "You must be logged in to access this page.")
                return redirect('/login/')  # Redirect to login page
            
            if not request.user.groups.filter(name=group_name).exists():
                messages.error(request, "You are not authorized to access this page.")
                return redirect('/login/')  # Redirect to login page
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator
