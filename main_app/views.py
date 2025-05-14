from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm

from django.utils.translation import gettext as _
from django.utils.translation import get_language

from .forms import UserSignupForm

# Vista de Registro de Usuario
def signup_view(request):
    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, _("Account created successfully! Please log in."))
            return redirect(reverse('login'))
        else:
             messages.error(request, _("Please correct the errors below."))
    else:
        form = UserSignupForm()
    return render(request, 'main_app/signup.html', {'form': form})

# Vista de Inicio de Sesión
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, _(f"Welcome, {user.username}!"))
                return redirect(request.GET.get('next') or reverse('home'))
            else:
                messages.error(request, _("Invalid username or password."))
        else:
             messages.error(request, _("Invalid username or password."))
    else:
        form = AuthenticationForm()
    return render(request, 'main_app/login.html', {'form': form})

# Vista de Cierre de Sesión
def logout_view(request):
    logout(request)
    messages.info(request, _("You have been logged out successfully."))
    return redirect(reverse('login'))

# --- Placeholder para la vista de inicio o donde redirigir ---
def home_view(request):
    if request.user.is_authenticated:
        message = _(f"Hello, {request.user.display_name}!")
    else:
        message = _("Welcome to the site. Please log in or sign up.")

    current_language = get_language()

    return render(request, 'main_app/home.html', {
        'message': message,
        'current_language': current_language,
    })

