from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, UserChangeForm as DjangoUserChangeForm, PasswordChangeForm
from .models import User, Author, Editorial, Language, Genre, Format, Book, ChatMessage
import pytz

class UserSignupForm(UserCreationForm):
    #display_name = forms.CharField(max_length=100, help_text='This will be your public display name.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('display_name',)
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control rounded-pill'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control rounded-pill'}),
            'password': forms.TextInput(attrs={'class': 'form-control rounded-pill'}),
        }

class BookForm(forms.ModelForm):
    authors_text = forms.CharField(
        max_length=1000,
        required=False,
        # help_text='Comma-separated list of authors (e.g., "Gabriel Garcia Marquez, Mario Vargas Llosa").'
    )
    genres_text = forms.CharField(
        max_length=1000,
        required=False,
        # help_text='Comma-separated list of genres (e.g., "Fantasy, Science Fiction").'
    )
    formats_text = forms.CharField(
        max_length=1000,
        required=False,
        # help_text='Comma-separated list of formats (e.g., "Hardcover, eBook, Audiobook").'
    )
    editorial_name = forms.CharField(
        max_length=255,
        required=False,
        # help_text='Name of the editorial (e.g., "Penguin Random House").'
    )
    language_name = forms.CharField(
        max_length=100,
        required=False,
        # help_text='Language of the book (e.g., "Spanish").'
    )

    class Meta:
        model = Book
        fields = [
            'title', 'isbn', 'release_date', 'edition_number',
            'authors_text', 'editorial_name', 'language_name',
            'genres_text', 'formats_text', 'original_book', 'cover'
        ]
        widgets = {
            # Aplicar clases de estilo a los campos de formulario
            'title': forms.TextInput(attrs={'class': 'form-control rounded-material'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control rounded-material'}),
            'release_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control rounded-material'}),
            'edition_number': forms.NumberInput(attrs={'class': 'form-control rounded-material'}),
            'authors_text': forms.TextInput(attrs={'class': 'form-control rounded-material'}), 
            'editorial_name': forms.TextInput(attrs={'class': 'form-control rounded-material'}),
            'language_name': forms.TextInput(attrs={'class': 'form-control rounded-material'}),
            'genres_text': forms.TextInput(attrs={'class': 'form-control rounded-material'}), 
            'formats_text': forms.TextInput(attrs={'class': 'form-control rounded-material'}),
            'original_book': forms.Select(attrs={'class': 'form-select rounded-material'}), # Para el select
            'cover': forms.ClearableFileInput(attrs={'class': 'form-control rounded-material'}), # Para el campo de archivo
        }

    def save(self, commit=True):
        book = super().save(commit=False)
        if commit:
            book.save()
        return book

class UserProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['display_name', 'profile_picture', 'bio', 'is_public_profile'] 
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-control rounded-material', 'placeholder': 'Your public display name'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control rounded-material'}), # Input para subir archivo
            'bio': forms.Textarea(attrs={'class': 'form-control rounded-material', 'placeholder': 'Tell us about yourself...', 'rows': 4}),
            'is_public_profile': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

# Formulario para enviar mensajes de chat
class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ['message']
        widgets = {
            'message': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Write your message...'}),
        }

# Formulario para cambiar nombre de usuario
class ChangeUsernameForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'New Username'}),
        }
    
    def clean_username(self):
        username = self.cleaned_data['username']
        # self.instance es el objeto User asociado al formulario (el usuario logueado)
        if User.objects.filter(username=username).exists() and self.instance.username != username:
            raise forms.ValidationError("This username is already taken. Please choose a different one.")
        return username

# El formulario para cambiar la contraseña ya lo proporciona Django: PasswordChangeForm

#Formulario para actualizar preferencias de notificación
class NotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['notify_new_followers', 'notify_review_likes', 'notify_friend_activity']
        widgets = {
            'notify_new_followers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_review_likes': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_friend_activity': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# Formulario para la visibilidad del perfil
class ProfileVisibilityForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['is_public_profile']
        widgets = {
            'is_public_profile': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

# Formulario para la zona horaria
class TimeZoneForm(forms.ModelForm):
    # Genera las opciones de zona horaria usando pytz
    timezone = forms.ChoiceField(
        choices=[(tz, tz) for tz in pytz.all_timezones],
        widget=forms.Select(attrs={'class': 'form-select rounded-pill'}),
        label="Select Time Zone"
    )

    class Meta:
        model = User
        fields = ['timezone']

# Formulario para el tema (claro/oscuro)
# class ThemeForm(forms.ModelForm):
#     class Meta:
#         model = User
#         fields = ['is_dark_theme']
#         widgets = {
#             'is_dark_theme': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
#         }
