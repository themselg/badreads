"""
-- Tabla: users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    registration_date DATE NOT NULL,
    password_hash TEXT NOT NULL
);

-- Tabla: authors
CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    birth_date DATE,
    country_id INTEGER,
    FOREIGN KEY (country_id) REFERENCES country(id) ON DELETE SET NULL 
);

-- Tabla: editorials
CREATE TABLE editorials (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country_id INTEGER,
    FOREIGN KEY (country_id) REFERENCES country(id) ON DELETE SET NULL
);

-- Tabla: languages
CREATE TABLE languages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Tabla: genre
CREATE TABLE genre (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Tabla: format
CREATE TABLE format (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Tabla: country
CREATE TABLE country (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Tabla: lsr (Lectura Semanal Recomendada)
CREATE TABLE lsr (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    book_id INTEGER UNIQUE NOT NULL,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    isbn INTEGER UNIQUE,
    release_date DATE,
    editorial_id INTEGER,
    language_id INTEGER,
    original_book_id INTEGER,
    edition_number INTEGER,
    FOREIGN KEY (editorial_id) REFERENCES editorials(id) ON DELETE SET NULL,
    FOREIGN KEY (language_id) REFERENCES languages(id) ON DELETE SET NULL,
    FOREIGN KEY (original_book_id) REFERENCES books(id) ON DELETE SET NULL
);

CREATE TABLE has_read (
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    review VARCHAR(100),
    rating NUMERIC(2,1) CHECK (rating >= 0 AND rating <= 5),
    review_date DATE NOT NULL,
    PRIMARY KEY (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE friends_with (
    user_id_1 INTEGER NOT NULL,
    user_id_2 INTEGER NOT NULL,
    since DATE NOT NULL,
    PRIMARY KEY (user_id_1, user_id_2),
    FOREIGN KEY (user_id_1) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id_2) REFERENCES users(id) ON DELETE CASCADE,
);

CREATE TABLE wants_to_read (
    user_id INTEGER NOT NULL, -- Mantener user_id para claridad
    book_id INTEGER NOT NULL, -- Mantener book_id para claridad
    since DATE NOT NULL,
    PRIMARY KEY (user_id, book_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE written_by (
    book_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    PRIMARY KEY (book_id, author_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE
);

CREATE TABLE book_genres (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genre(id) ON DELETE CASCADE,
    UNIQUE (book_id, genre_id)
);

CREATE TABLE book_formats (
    id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL,
    format_id INTEGER NOT NULL,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (format_id) REFERENCES format(id) ON DELETE CASCADE,
    UNIQUE (book_id, format_id)
);
"""

from django.db import models
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

# Modelos básicos

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Format(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# Modelos que dependen de los básicos

# --- Gestor de Usuarios Personalizado ---
class UserManager(BaseUserManager):
    def create_user(self, username, display_name, password=None, **extra_fields):
        """
        Crea y guarda un Usuario regular con el username y password dados.
        """
        if not username:
            raise ValueError('Users must have a username')
        if not display_name:
             raise ValueError('Users must have a display name')

        user = self.model(
            username=self.model.normalize_username(username),
            display_name=display_name,
            registration_date=extra_fields.pop('registration_date', timezone.now()),
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, display_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, display_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    registration_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    password = models.CharField('password', max_length=128, db_column='password_hash')

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['display_name']

    objects = UserManager()

    def get_full_name(self):
        return self.display_name

    def get_short_name(self):
        return self.username

    def __str__(self):
        return self.username

class Author(models.Model):
    name = models.CharField(max_length=100)
    birth_date = models.DateField(null=True, blank=True) # No se conoce la fecha de todos los autores
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL, # FOREIGN KEY ... ON DELETE SET NULL
        null=True, # Permite que la FK sea NULL en la DB
        blank=True # Permite que el campo sea opcional en formularios/admin
    )

    def __str__(self):
        return self.name

class Editorial(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL, # FOREIGN KEY ... ON DELETE SET NULL
        null=True, # Permite que la FK sea NULL en la DB
        blank=True # Permite que el campo sea opcional en formularios/admin
    )

    def __str__(self):
        return self.name

class Book(models.Model):
    title = models.CharField(max_length=255)
    isbn = models.IntegerField(unique=True, null=True, blank=True)
    release_date = models.DateField(null=True, blank=True)
    editorial = models.ForeignKey(
        Editorial,
        on_delete=models.SET_NULL, # FOREIGN KEY ... ON DELETE SET NULL
        null=True, # Permite que la FK sea NULL en la DB
        blank=True # Permite que el campo sea opcional
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL, # FOREIGN KEY ... ON DELETE SET NULL
        null=True, # Permite que la FK sea NULL en la DB
        blank=True # Permite que el campo sea opcional
    )

    # Relación recursiva: un libro puede tener un libro original (ej. una traducción)
    original_book = models.ForeignKey(
        'self', # Referencia a sí mismo
        on_delete=models.SET_NULL, # FOREIGN KEY ... ON DELETE SET NULL
        null=True, # Permite que la FK sea NULL
        blank=True # Permite que el campo sea opcional
    )

    edition_number = models.IntegerField(null=True, blank=True) # INTEGER, puede ser NULL
    authors = models.ManyToManyField(Author, through='WrittenBy', related_name='books')
    genres = models.ManyToManyField(Genre, through='BookGenre', related_name='books')
    formats = models.ManyToManyField(Format, through='BookFormat', related_name='books')

    def __str__(self):
        return self.title


class LSR(models.Model):
    date = models.DateField(unique=True)
    book = models.OneToOneField(Book, on_delete=models.CASCADE) # Solo 1 libro puede ser LSR, y un solo libro solo puede tener 1 LSR

    def __str__(self):
        return f"LSR - {self.date}"


class HasRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE
    book = models.ForeignKey(Book, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE
    review = models.CharField(max_length=100, null=True, blank=True) # VARCHAR, puede ser NULL
    rating = models.DecimalField(
        max_digits=2, # Corresponde a NUMERIC(2,1)
        decimal_places=1,
        null=True, # Rating puede ser NULL si no hay review?
        blank=True,
        validators=[ # Añadir validadores para la restricción CHECK
            MinValueValidator(0.0),
            MaxValueValidator(5.0)
        ]
    )
    review_date = models.DateField()

    class Meta:
        # PRIMARY KEY (user_id, book_id)
        unique_together = (('user', 'book'),)
        verbose_name_plural = "Has Read"

    def __str__(self):
        return f"{self.user.username} read {self.book.title}"

class FriendsWith(models.Model):
    user1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friends1' # Usar related_name para evitar conflictos
    )
    user2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='friends2' # Usar related_name para evitar conflictos
    )
    since = models.DateField(auto_now_add=True)

    class Meta:
        # PRIMARY KEY (user_id_1, user_id_2)
        unique_together = (('user1', 'user2'),)
        verbose_name_plural = "Friends With"

    def __str__(self):
        return f"{self.user1.username} is friends with {self.user2.username}"

class WantsToRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE
    book = models.ForeignKey(Book, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE
    since = models.DateField(auto_now_add=True)

    class Meta:
        # PRIMARY KEY (user_id, book_id)
        unique_together = (('user', 'book'),)
        verbose_name_plural = "Wants To Read"

    def __str__(self):
        return f"{self.user.username} wants to read {self.book.title}"

class WrittenBy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE
    author = models.ForeignKey(Author, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE

    class Meta:
        # PRIMARY KEY (book_id, author_id)
        unique_together = (('book', 'author'),)
        verbose_name_plural = "Written By"

    def __str__(self):
        return f"{self.book.title} by {self.author.name}"

class BookGenre(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE

    class Meta:
        # UNIQUE (book_id, genre_id)
        unique_together = (('book', 'genre'),)

    def __str__(self):
        return f"{self.book.title} - {self.genre.name}"

class BookFormat(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE
    format = models.ForeignKey(Format, on_delete=models.CASCADE) # FOREIGN KEY ... ON DELETE CASCADE

    class Meta:
        # UNIQUE (book_id, format_id)
        unique_together = (('book', 'format'),)

    def __str__(self):
        return f"{self.book.title} - {self.format.name}"

