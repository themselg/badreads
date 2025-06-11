from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings

# --- UserManager ---
class UserManager(BaseUserManager):
    def create_user(self, username, display_name, password=None):
        if not username:
            raise ValueError('Users must have a username')
        if not display_name:
            raise ValueError('Users must have a display name')

        user = self.model(
            username=self.model.normalize_username(username),
            display_name=display_name,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, display_name, password=None):
        user = self.create_user(
            username,
            password=password,
            display_name=display_name,
        )
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

# --- User Model (Con nuevos campos para ajustes) ---
class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    registration_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    is_public_profile = models.BooleanField(default=True) # Visibilidad del perfil
    # Campo para la zona horaria, se usa el default de settings
    timezone = models.CharField(max_length=50, default=settings.TIME_ZONE)
    # Campos para preferencias de notificación
    notify_new_followers = models.BooleanField(default=True)
    notify_review_likes = models.BooleanField(default=True)
    notify_friend_activity = models.BooleanField(default=True)
    # Campo para el tema (true = oscuro, false = claro)
    is_dark_theme = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True, null=True) # Descripción del usuario

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['display_name']

    def __str__(self):
        return self.display_name

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin

# Modelos relacionados con Libros
class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class Format(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class Author(models.Model):
    name = models.CharField(max_length=255, unique=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self): return self.name

class Editorial(models.Model):
    name = models.CharField(max_length=255, unique=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self): return self.name

class Book(models.Model):
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=13, blank=True, null=True, unique=True)
    release_date = models.DateField(blank=True, null=True)
    edition_number = models.IntegerField(blank=True, null=True)
    cover = models.ImageField(upload_to='book_covers/', blank=True, null=True)

    authors = models.ManyToManyField('Author', through='WrittenBy')
    editorial = models.ForeignKey('Editorial', on_delete=models.SET_NULL, null=True, blank=True)
    language = models.ForeignKey('Language', on_delete=models.SET_NULL, null=True, blank=True)
    genres = models.ManyToManyField('Genre', through='BookGenre')
    formats = models.ManyToManyField('Format', through='BookFormat')

    original_book = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='editions')

    last_modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_books')
    last_modified_at = models.DateTimeField(auto_now=True, null=True, blank=True)


    def __str__(self):
        return self.title

class BookEdit(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='edit_history')
    editor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    edit_date = models.DateTimeField(auto_now_add=True)
    changes_summary = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-edit_date']

    def __str__(self):
        editor_name = self.editor.username if self.editor else "Unknown User"
        return f"Edit for '{self.book.title}' by {editor_name} on {self.edit_date.strftime('%Y-%m-%d %H:%M')}"

class HasRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    review = models.TextField(blank=True, null=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, validators=[MinValueValidator(0), MaxValueValidator(5)], blank=True, null=True)
    review_date = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(User, related_name='liked_reviews', blank=True)

    class Meta:
        unique_together = ('user', 'book')
        ordering = ['-review_date']

    def __str__(self):
        return f"{self.user.username} read {self.book.title}"

# Renombrado de FriendsWith a Follow
class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'followed')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.follower.username} follows {self.followed.username}"

# Chat para representar una conversación
class Chat(models.Model):
    # Relación ManyToMany para los participantes del chat
    participants = models.ManyToManyField(User, related_name='chats')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True) # Para ordenar chats

    class Meta:
        ordering = ['-last_message_at']

    def __str__(self):
        return f"Chat between {' and '.join([p.display_name for p in self.participants.all()])}"

    # Método para encontrar o crear un chat entre dos usuarios
    @classmethod
    def get_or_create_chat(cls, user1, user2):
        # Asegurarse de un orden consistente de los usuarios para la búsqueda
        users = sorted([user1, user2], key=lambda u: u.pk)
        
        # Buscar chats que tengan exactamente a estos dos participantes
        chat = cls.objects.annotate(num_participants=models.Count('participants')).filter(
            participants=users[0]
        ).filter(
            participants=users[1]
        ).filter(
            num_participants=2 # Asegura que solo sean los dos usuarios
        ).first()

        if not chat:
            chat = cls.objects.create()
            chat.participants.add(users[0], users[1])
            chat.save()
        return chat

# ChatMessage para los mensajes individuales
class ChatMessage(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.username} in Chat {self.chat.pk} at {self.timestamp.strftime('%H:%M')}"

class WantsToRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    since = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'book')
        ordering = ['-since']

    def __str__(self):
        return f"{self.user.username} wants to read {self.book.title}"

class WrittenBy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('book', 'author')

    def __str__(self):
        return f"{self.author.name} wrote {self.book.title}"

class BookGenre(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('book', 'genre')

    def __str__(self):
        return f"{self.book.title} is {self.genre.name}"

class BookFormat(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    format = models.ForeignKey(Format, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('book', 'format')

    def __str__(self):
        return f"{self.book.title} in {self.format.name}"

# Bloquear usuarios
class BlockedUser(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocking')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    blocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
        verbose_name = "Blocked User"
        verbose_name_plural = "Blocked Users"
        ordering = ['-blocked_at']

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"

# Notificaciones
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    link = models.URLField(max_length=200, blank=True, null=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Tipo de notificación para filtrado (e.g., 'like', 'follow', 'review')
    notification_type = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['-created_at'] # Las más nuevas primero

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:50]}..."

