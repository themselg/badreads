from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import get_language
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import timedelta
from django.http import JsonResponse 
from django.db import transaction
import requests, os, json, pytz, re, base64

from io import BytesIO
from PIL import Image # Pillow para abrir la imagen
import pytesseract # La librería para interactuar con Tesseract (ocr)

from .forms import UserSignupForm, BookForm, UserProfileEditForm, ChatMessageForm, \
    ChangeUsernameForm, NotificationSettingsForm, ProfileVisibilityForm, TimeZoneForm, ThemeForm
from .models import Book, User, HasRead, Follow, WantsToRead, Author, Editorial, Language, Genre, Format, BookEdit, Chat, ChatMessage, BlockedUser, Notification


def create_notification(user, message, link=None, notification_type=None):
    """
    Crea una nueva notificación para un usuario dado.
    Verifica las preferencias de notificación del usuario antes de crearla.
    """
    if not user.is_authenticated:
        return # No crear notificaciones para usuarios no autenticados

    if notification_type == 'like' and not user.notify_review_likes:
        return
    if notification_type == 'follow' and not user.notify_new_followers:
        return

    Notification.objects.create(
        user=user,
        message=message,
        link=link,
        notification_type=notification_type
    )


#Vistas de Autenticación

def signup_view(request):
    if request.user.is_authenticated:
        return redirect(reverse('home'))

    if request.method == 'POST':
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, gettext("Account created successfully! Please log in."))
            return redirect(reverse('login'))
        else:
             messages.error(request, gettext("Please correct the errors below."))
    else:
        form = UserSignupForm()
    return render(request, 'main_app/signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect(reverse('home'))

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                messages.success(request, gettext(f"Welcome, {user.username}!"))
                login(request, user)
                return redirect(request.GET.get('next') or reverse('home'))
            else:
                messages.error(request, gettext("Invalid username or password."))
        else:
             messages.error(request, gettext("Invalid username or password."))
    else:
        form = AuthenticationForm()
    return render(request, 'main_app/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, gettext("You have been logged out successfully."))
    return redirect(reverse('login'))


def home_view(request):
    recommended_books = []
    # trending_books = []

    # if not Book.objects.exists():
    #     for i in range(1, 9):
    #         dummy_author = type('Author', (object,), {'name': gettext(f"Author {i}")})()
    #         recommended_books.append(
    #             type('Book', (object,), {'title': gettext(f"Recommended Book {i}"), 'author': dummy_author, 'pk': i, 'isbn': gettext(f'978-000000000{i}')})()
    #         )
    #         dummy_author_trend = type('Author', (object,), {'name': gettext(f"Trend Author {i}"), 'pk': i})()
    #         trending_books.append(
    #             type('Book', (object,), {'title': gettext(f"Trending Book {i}"), 'author': dummy_author_trend, 'pk': i+100, 'isbn': gettext(f'978-111111111{i}')})()
    #         )
    # else:
    #     recommended_books = Book.objects.all().order_by('?')[:8]
    #     trending_books = Book.objects.all().order_by('-release_date')[:8]

    # context = {
    #     'recommended_books': recommended_books,
    #     'trending_books': trending_books,
    # }

    recommended_books = []
    if request.user.is_authenticated:
        user_read_genres = HasRead.objects.filter(user=request.user).values_list('book__bookgenre__genre__pk', flat=True).distinct()

        if user_read_genres:
            
            read_book_ids = HasRead.objects.filter(user=request.user).values_list('book__pk', flat=True)
            
            recommended_books = Book.objects.filter(
                bookgenre__genre__pk__in=user_read_genres
            ).exclude(
                pk__in=read_book_ids
            ).distinct().order_by('?')[:10] 

    seven_days_ago = timezone.now() - timedelta(days=7)
    trending_books = Book.objects.filter(
        hasread__review_date__gte=seven_days_ago
    ).annotate(
        review_count=Count('hasread')
    ).order_by('-review_count')[:10]


    context = {
        
        'recommended_books': recommended_books,
        'trending_books': trending_books,
        'section_title': gettext("Welcome to BadReads"),
    }
    return render(request, 'main_app/home.html', context)


# Vistas de Perfil y Reseñas

@login_required
def user_profile_view(request, pk):
    profile_user = get_object_or_404(User, pk=pk)
    profile_user_reviews = HasRead.objects.filter(user=profile_user).order_by('-review_date')

    is_following = False
    is_followed_by_user = False
    is_friend = False
    is_blocked_by_me = False 

    if request.user.is_authenticated and request.user != profile_user:
        is_following = Follow.objects.filter(follower=request.user, followed=profile_user).exists()
        is_followed_by_user = Follow.objects.filter(follower=profile_user, followed=request.user).exists()

        if is_following and is_followed_by_user:
            is_friend = True

        is_blocked_by_me = BlockedUser.objects.filter(blocker=request.user, blocked=profile_user).exists()


    context = {
        'profile_user': profile_user,
        'profile_user_reviews': profile_user_reviews,
        'is_following': is_following,
        'is_friend': is_friend,
        'is_blocked_by_me': is_blocked_by_me, 
    }
    return render(request, 'main_app/profile.html', context)


@login_required
def edit_user_profile_view(request, pk):
    user_to_edit = get_object_or_404(User, pk=pk)

    if request.user != user_to_edit:
        messages.error(request, gettext("You are not authorized to edit this profile."))
        return redirect(reverse('user_profile', args=[request.user.pk]))

    if request.method == 'POST':
        # Instanciar el formulario con request.POST y request.FILES
        form = UserProfileEditForm(request.POST, request.FILES, instance=user_to_edit)
        if form.is_valid():
            # Manejar el campo de borrado de imagen
            if request.POST.get('profile_picture-clear'):
                user_to_edit.profile_picture.delete(save=False) # Elimina el archivo del storage
                user_to_edit.profile_picture = None # Establece el campo a null
            
            form.save()
            messages.success(request, gettext("Your profile has been updated successfully!"))
            return redirect(reverse('user_profile', args=[user_to_edit.pk]))
        else:
            messages.error(request, gettext("Please correct the errors below."))
    else:
        form = UserProfileEditForm(instance=user_to_edit)

    context = {
        'form': form,
        'profile_user': user_to_edit,
    }
    return render(request, 'main_app/edit_profile.html', context)


@login_required
def popular_reviews_view(request):
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    popular_reviews = HasRead.objects.filter(review_date__gte=seven_days_ago).annotate(
        num_likes=Count('likes')
    ).order_by('-num_likes', '-review_date')[:10]

    context = {
        'popular_reviews': popular_reviews,
        'user_reviews': None,
        'profile_user': None,
    }
    return render(request, 'main_app/reviews.html', context)

@login_required
def user_specific_reviews_view(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    user_reviews = HasRead.objects.filter(user=user_obj).order_by('-review_date')
    context = {
        'profile_user': user_obj,
        'user_reviews': user_reviews,
        'popular_reviews': None,
    }
    return render(request, 'main_app/reviews.html', context)

@login_required
def like_review_view(request, pk):
    if request.method == 'POST':
        review = get_object_or_404(HasRead, pk=pk)
        user = request.user

        if user in review.likes.all():
            review.likes.remove(user)
            messages.info(request, gettext("You unliked this review."))
        else:
            review.likes.add(user)
            messages.success(request, gettext("You liked this review!"))
            if review.user != user: 
                create_notification(
                    user=review.user,
                    message=gettext(f"{user.display_name} liked your review for '{review.book.title}'."),
                    link=reverse('book_detail', args=[review.book.pk]),
                    notification_type='like'
                )
        return redirect(request.META.get('HTTP_REFERER', reverse('home')))
    return redirect(reverse('home'))

# Vistas de Listas de Lectura

@login_required
def my_list_view(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.user != user_obj:
        messages.error(request, gettext("You are not authorized to view this list."))
        return redirect(reverse('home'))

    wants_to_read_list = WantsToRead.objects.filter(user=user_obj).select_related('book', 'book__editorial', 'book__language').order_by('-since')
    has_read_list = HasRead.objects.filter(user=user_obj).select_related('book', 'book__editorial', 'book__language').order_by('-review_date')

    context = {
        'profile_user': user_obj,
        'wants_to_read_list': wants_to_read_list,
        'has_read_list': has_read_list,
    }
    return render(request, 'main_app/my_list.html', context)

@login_required
def add_to_wants_to_read_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        if not WantsToRead.objects.filter(user=request.user, book=book).exists():
            WantsToRead.objects.create(user=request.user, book=book, since=timezone.now())
            messages.success(request, gettext(f"'{book.title}' added to your 'Wants to Read' list!"))
        else:
            messages.info(request, gettext(f"'{book.title}' is already in your 'Wants to Read' list."))
        return redirect(request.META.get('HTTP_REFERER', reverse('book_detail', args=[pk])))
    return redirect(reverse('book_detail', args=[pk]))

@login_required
def remove_from_wants_to_read_view(request, pk):
    wants_to_read_entry = get_object_or_404(WantsToRead, pk=pk, user=request.user)

    if request.method == 'POST':
        book_title = wants_to_read_entry.book.title
        wants_to_read_entry.delete()
        messages.success(request, gettext(f"'{book_title}' has been removed from your 'Wants to Read' list."))
        return redirect(reverse('my_list', args=[request.user.pk]))
    else:
        messages.error(request, gettext("Invalid request method."))
        return redirect(request.META.get('HTTP_REFERER', reverse('home')))


# Vistas de Amigos

@login_required
def friends_view(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    # Usuarios que sigue el usuario_obj
    following = Follow.objects.filter(follower=user_obj).select_related('followed').order_by('followed__display_name')
    # Usuarios que siguen al usuario_obj
    followers_queryset = Follow.objects.filter(followed=user_obj).select_related('follower').order_by('follower__display_name')

    # Encontrar amigos mutuos (usuarios que user_obj sigue Y que también siguen a user_obj)
    mutual_friends_ids = following.filter(followed__in=[f.follower for f in followers_queryset]).values_list('followed__pk', flat=True)
    mutual_friends = User.objects.filter(pk__in=mutual_friends_ids).order_by('display_name')

    followers_for_template = []
    for follow_entry in followers_queryset:
        is_currently_following = False
        if request.user.is_authenticated:
            is_currently_following = Follow.objects.filter(
                follower=request.user,
                followed=follow_entry.follower 
            ).exists()
        
        followers_for_template.append({
            'follower': follow_entry.follower,
            'is_currently_following': is_currently_following,
        })

    context = {
        'profile_user': user_obj,
        'following': following,
        'followers': followers_for_template, 
        'mutual_friends': mutual_friends,
        'is_my_profile': (request.user == user_obj),
    }
    return render(request, 'main_app/friends.html', context)

@login_required
def friends_search_view(request):
    query = request.GET.get('q', '')
    users_results = []

    if query:
        users_results_queryset = User.objects.filter(
            Q(username__icontains=query) |
            Q(display_name__icontains=query)
        ).exclude(pk=request.user.pk if request.user.is_authenticated else None)

        if request.user.is_authenticated:
            blocked_by_me_pks = BlockedUser.objects.filter(blocker=request.user).values_list('blocked__pk', flat=True)
            blocking_me_pks = BlockedUser.objects.filter(blocked=request.user).values_list('blocker__pk', flat=True)
            all_blocked_pks = list(set(list(blocked_by_me_pks) + list(blocking_me_pks)))
            users_results_queryset = users_results_queryset.exclude(pk__in=all_blocked_pks)

        final_users_results = []
        if request.user.is_authenticated:
            following_me = Follow.objects.filter(followed=request.user).values_list('follower__pk', flat=True)
            my_following = Follow.objects.filter(follower=request.user).values_list('followed__pk', flat=True)
            mutual_friends_pks = set(following_me).intersection(set(my_following))

            for user_found in users_results_queryset:
                if user_found.is_public_profile:
                    final_users_results.append(user_found)
                elif user_found.pk in mutual_friends_pks: 
                    final_users_results.append(user_found)
        else: 
            final_users_results = list(users_results_queryset.filter(is_public_profile=True))
        
        users_results = final_users_results[:10] 

        for user_found in users_results:
            user_found.is_following = Follow.objects.filter(follower=request.user, followed=user_found).exists()
            user_found.is_friend = (user_found.is_following and
                                    Follow.objects.filter(follower=user_found, followed=request.user).exists())

    context = {
        'query': query,
        'books': [], 
        'users': users_results,
    }
    return render(request, 'main_app/search_results.html', context)


@login_required
def follow_user_view(request, pk):
    user_to_follow = get_object_or_404(User, pk=pk)

    if request.user == user_to_follow:
        messages.error(request, gettext("You cannot follow yourself."))
        return redirect(reverse('user_profile', args=[pk]))
    
    if BlockedUser.objects.filter(blocker=user_to_follow, blocked=request.user).exists():
        messages.error(request, gettext(f"{user_to_follow.display_name} has blocked you. You cannot follow them."))
        return redirect(request.META.get('HTTP_REFERER', reverse('user_profile', args=[pk])))
    if BlockedUser.objects.filter(blocker=request.user, blocked=user_to_follow).exists():
        messages.error(request, gettext(f"You have blocked {user_to_follow.display_name}. Unblock them first to follow."))
        return redirect(request.META.get('HTTP_REFERER', reverse('user_profile', args=[pk])))


    if request.method == 'POST':
        follow_instance = Follow.objects.filter(follower=request.user, followed=user_to_follow)
        if follow_instance.exists():
            follow_instance.delete()
            messages.info(request, gettext(f"You are no longer following {user_to_follow.display_name}."))
        else:
            Follow.objects.create(follower=request.user, followed=user_to_follow)
            messages.success(request, gettext(f"You are now following {user_to_follow.display_name}!"))
            create_notification(
                user=user_to_follow,
                message=gettext(f"{request.user.display_name} started following you."),
                link=reverse('user_profile', args=[request.user.pk]),
                notification_type='follow'
            )
        
        return redirect(request.META.get('HTTP_REFERER', reverse('user_profile', args=[pk])))
    
    return redirect(reverse('user_profile', args=[pk])) # Redirigir si no es POST

# Listar chats del usuario
@login_required
def chat_list_view(request):
    # Obtener todos los chats donde el usuario actual es un participante
    user_chats = Chat.objects.filter(participants=request.user).prefetch_related('participants', 'messages').order_by('-last_message_at')

    # Para cada chat, encontrar al otro participante y el último mensaje
    chats_info = []
    for chat in user_chats:
        other_participant = chat.participants.exclude(pk=request.user.pk).first()
        last_message = chat.messages.last() # El último mensaje debido a ordering = ['timestamp']

        # Asegurarse de que el otro participante también sigue al usuario actual
        # Es decir, que sean amigos mutuos para que el chat sea válido
        are_friends = (
            Follow.objects.filter(follower=request.user, followed=other_participant).exists() and
            Follow.objects.filter(follower=other_participant, followed=request.user).exists()
        ) if other_participant else False

        is_blocked = False
        if other_participant:
            is_blocked = (
                BlockedUser.objects.filter(blocker=request.user, blocked=other_participant).exists() or
                BlockedUser.objects.filter(blocker=other_participant, blocked=request.user).exists()
            )

        if other_participant and are_friends and not is_blocked: # Solo mostrar chats con amigos mutuos no bloqueados
            chats_info.append({
                'chat': chat,
                'other_participant': other_participant,
                'last_message': last_message,
            })
    
    chats_info.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else timezone.datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)


    context = {
        'chats_info': chats_info,
    }
    return render(request, 'main_app/chat_list.html', context)

# Sala de chat para un usuario específico
@login_required
def chat_room_view(request, other_user_pk):
    other_user = get_object_or_404(User, pk=other_user_pk)

    if request.user == other_user:
        messages.error(request, gettext("You cannot chat with yourself."))
        return redirect(reverse('chat_list'))

    # Verificar si son amigos mutuos antes de permitir el chat
    are_friends = (
        Follow.objects.filter(follower=request.user, followed=other_user).exists() and
        Follow.objects.filter(follower=other_user, followed=request.user).exists()
    )

    is_blocked = (
        BlockedUser.objects.filter(blocker=request.user, blocked=other_user).exists() or
        BlockedUser.objects.filter(blocker=other_user, blocked=request.user).exists()
    )

    if not are_friends:
        messages.error(request, gettext(f"You can only chat with mutual friends. You are not mutual friends with {other_user.display_name}."))
        return redirect(reverse('chat_list'))
    
    if is_blocked:
        messages.error(request, gettext(f"You cannot chat with {other_user.display_name} because one of you has blocked the other."))
        return redirect(reverse('chat_list'))

    # Obtener o crear el chat entre los dos usuarios
    chat = Chat.get_or_create_chat(request.user, other_user)

    messages_in_chat = chat.messages.select_related('sender').order_by('timestamp')
    
    if request.method == 'POST':
        form = ChatMessageForm(request.POST)
        if form.is_valid():
            chat_message = form.save(commit=False)
            chat_message.chat = chat
            chat_message.sender = request.user
            chat_message.save()
            # Actualizar last_message_at del chat
            chat.last_message_at = timezone.now()
            chat.save()
            return redirect(reverse('chat_room', args=[other_user_pk])) # Redirigir para evitar reenvío del formulario
        else:
            messages.error(request, gettext("Your message could not be sent. Please try again."))
    else:
        form = ChatMessageForm()

    context = {
        'other_user': other_user,
        'chat': chat,
        'messages': messages_in_chat,
        'form': form,
    }
    return render(request, 'main_app/chat_room.html', context)


# Vistas de Añadir/Editar Libro/Reseña

@login_required
def add_book_or_review_view(request):
    return render(request, 'main_app/add_book_or_review.html')

@login_required
def add_book_view(request):
    form = BookForm(request.POST or None, request.FILES or None)
    book_data_for_preview = None
    show_preview_modal = False

    if request.method == 'POST':
        action = request.POST.get('action')

        if form.is_valid():
            book_data_for_preview = {
                'title': form.cleaned_data.get('title'),
                'isbn': form.cleaned_data.get('isbn'),
                'release_date': form.cleaned_data.get('release_date').strftime('%Y-%m-%d') if form.cleaned_data.get('release_date') else '',
                'edition_number': form.cleaned_data.get('edition_number'),
                'authors_text': form.cleaned_data.get('authors_text'),
                'genres_text': form.cleaned_data.get('genres_text'),
                'formats_text': form.cleaned_data.get('formats_text'),
                'editorial_name': form.cleaned_data.get('editorial_name'),
                'language_name': form.cleaned_data.get('language_name'),
                'cover_url': request.POST.get('cover_url_hidden')
            }

            if action == 'save':
                try:
                    book = form.save(commit=False)

                    authors_list = [a.strip() for a in form.cleaned_data['authors_text'].split(',') if a.strip()]
                    book_authors = [Author.objects.get_or_create(name=name)[0] for name in authors_list]

                    editorial_obj = None
                    if form.cleaned_data['editorial_name']:
                        editorial_obj, _ = Editorial.objects.get_or_create(name=form.cleaned_data['editorial_name'])
                    book.editorial = editorial_obj

                    language_obj = None
                    if form.cleaned_data['language_name']:
                        language_obj, _ = Language.objects.get_or_create(name=form.cleaned_data['language_name'])
                    book.language = language_obj

                    book_cover_file = request.FILES.get('cover')
                    if book_cover_file:
                        file_name = default_storage.save(gettext(f'book_covers/{book_cover_file.name}'), ContentFile(book_cover_file.read()))
                        book.cover = file_name
                    elif request.POST.get('cover_url_hidden'):
                        try:
                            image_url = request.POST.get('cover_url_hidden')
                            response = requests.get(image_url, stream=True)
                            if response.status_code == 200:
                                content_type = response.headers.get('Content-Type', '').lower()
                                ext = 'jpg'
                                if 'png' in content_type: ext = 'png'
                                elif 'gif' in content_type: ext = 'gif'
                                file_name = gettext(f"book_covers/{book.isbn or 'no_isbn'}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}")
                                saved_path = default_storage.save(file_name, ContentFile(response.content))
                                book.cover = saved_path
                        except Exception as e:
                            messages.warning(request, gettext("Could not download book cover from Open Library."))

                    book.last_modified_by = request.user
                    book.last_modified_at = timezone.now()
                    book.save()

                    genres_list = [g.strip() for g in form.cleaned_data['genres_text'].split(',') if g.strip()]
                    book_genres = [Genre.objects.get_or_create(name=name)[0] for name in genres_list]
                    book.genres.set(book_genres)

                    formats_list = [f.strip() for f in form.cleaned_data['formats_text'].split(',') if f.strip()]
                    book_formats = [Format.objects.get_or_create(name=name)[0] for name in formats_list]
                    book.formats.set(book_formats)

                    BookEdit.objects.create(
                        book=book,
                        editor=request.user,
                        changes_summary=gettext("Book added by {user}").format(user=request.user.username)
                    )

                    messages.success(request, gettext(f"'{book.title}' has been added successfully!"))
                    return redirect(reverse('book_detail', args=[book.pk]))

                except Exception as e:
                    messages.error(request, gettext(f"An error occurred while saving the book: {e}"))
            elif action == 'preview':
                show_preview_modal = True
                book_cover_file = request.FILES.get('cover')
                if book_cover_file:
                    from django.core.files.storage import FileSystemStorage
                    fs = FileSystemStorage()
                    temp_file_name = fs.save(book_cover_file.name, book_cover_file)
                    book_data_for_preview['temp_cover_url'] = fs.url(temp_file_name)
                elif request.POST.get('cover_url_hidden'):
                     book_data_for_preview['temp_cover_url'] = request.POST.get('cover_url_hidden')
        else:
            messages.error(request, gettext("Please correct the errors in the form."))
            book_data_for_preview = {
                'title': request.POST.get('title'),
                'isbn': request.POST.get('isbn'),
                'release_date': request.POST.get('release_date'),
                'edition_number': request.POST.get('edition_number'),
                'authors_text': request.POST.get('authors_text'),
                'genres_text': request.POST.get('genres_text'),
                'formats_text': request.POST.get('formats_text'),
                'editorial_name': request.POST.get('editorial_name'),
                'language_name': request.POST.get('language_name'),
                'cover_url': request.POST.get('cover_url_hidden')
            }
            book_cover_file = request.FILES.get('cover')
            if book_cover_file:
                from django.core.files.storage import FileSystemStorage
                fs = FileSystemStorage()
                temp_file_name = fs.save(book_cover_file.name, book_cover_file)
                book_data_for_preview['temp_cover_url'] = fs.url(temp_file_name)
            elif request.POST.get('cover_url_hidden'):
                 book_data_for_preview['temp_cover_url'] = request.POST.get('cover_url_hidden')

    context = {
        'form': form,
        'book_data_for_preview': book_data_for_preview,
        'show_preview_modal': show_preview_modal,
        'is_edit_mode': False,
    }
    return render(request, 'main_app/add_book.html', context)

@login_required
def edit_book_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    initial_data = {
        'authors_text': ", ".join([a.name for a in book.authors.all()]),
        'genres_text': ", ".join([g.name for g in book.genres.all()]),
        'formats_text': ", ".join([f.name for f in book.formats.all()]),
        'editorial_name': book.editorial.name if book.editorial else '',
        'language_name': book.language.name if book.language else '',
    }
    form = BookForm(request.POST or None, request.FILES or None, instance=book, initial=initial_data)

    book_data_for_preview = None
    show_preview_modal = False
    old_data = {
        'title': book.title,
        'isbn': book.isbn,
        'release_date': book.release_date.strftime('%Y-%m-%d') if book.release_date else None,
        'edition_number': book.edition_number,
        'authors_text': ", ".join([a.name for a in book.authors.all()]),
        'genres_text': ", ".join([g.name for g in book.genres.all()]),
        'formats_text': ", ".join([f.name for f in book.formats.all()]),
        'editorial_name': book.editorial.name if book.editorial else '',
        'language_name': book.language.name if book.language else '',
    }


    if request.method == 'POST':
        action = request.POST.get('action')

        if form.is_valid():
            book_data_for_preview = {
                'title': form.cleaned_data.get('title'),
                'isbn': form.cleaned_data.get('isbn'),
                'release_date': form.cleaned_data.get('release_date').strftime('%Y-%m-%d') if form.cleaned_data.get('release_date') else '',
                'edition_number': form.cleaned_data.get('edition_number'),
                'authors_text': form.cleaned_data.get('authors_text'),
                'genres_text': form.cleaned_data.get('genres_text'),
                'formats_text': form.cleaned_data.get('formats_text'),
                'editorial_name': form.cleaned_data.get('editorial_name'),
                'language_name': form.cleaned_data.get('language_name'),
                'cover_url': request.POST.get('cover_url_hidden')
            }

            if action == 'save':
                try:
                    changes = []
                    for field_name in ['title', 'isbn', 'edition_number']:
                        old_value = old_data.get(field_name)
                        new_value = form.cleaned_data.get(field_name)
                        if str(old_value or '') != str(new_value or ''):
                            changes.append(gettext("{field_name_display}: '{old_value_display}' -> '{new_value_display}'").format(
                                field_name_display=field_name.replace('_', ' ').capitalize(),
                                old_value_display=old_value or 'N/A',
                                new_value_display=new_value or 'N/A'
                            ))

                    old_release_date = old_data.get('release_date')
                    new_release_date = form.cleaned_data.get('release_date')
                    if old_release_date != (new_release_date.strftime('%Y-%m-%d') if new_release_date else None):
                         changes.append(gettext("Release Date: '{old_date_display}' -> '{new_date_display}'").format(
                            old_date_display=old_release_date or 'N/A',
                            new_date_display=new_release_date.strftime('%Y-%m-%d') if new_release_date else 'N/A'
                         ))

                    fields_to_check = {
                        'authors_text': gettext('Authors'),
                        'genres_text': gettext('Genres'),
                        'formats_text': gettext('Formats'),
                        'editorial_name': gettext('Editorial'),
                        'language_name': gettext('Language')
                    }
                    for field_key, display_name in fields_to_check.items():
                        old_value = old_data.get(field_key)
                        new_value = form.cleaned_data.get(field_key)
                        if str(old_value or '') != str(new_value or ''):
                            changes.append(gettext("{display_name}: '{old_value_display}' -> '{new_value_display}'").format(
                                display_name=display_name,
                                old_value_display=old_value or 'N/A',
                                new_value_display=new_value or 'N/A'
                            ))

                    book_cover_file = request.FILES.get('cover')
                    current_cover_url = book.cover.url if book.cover else ''
                    new_cover_url_hidden = request.POST.get('cover_url_hidden')

                    if book_cover_file:
                        changes.append(gettext("Cover: new file uploaded"))
                    elif new_cover_url_hidden and new_cover_url_hidden != current_cover_url:
                         changes.append(gettext("Cover: changed to URL '{new_url}'").format(new_url=new_cover_url_hidden))
                    elif not new_cover_url_hidden and current_cover_url:
                        if not book_cover_file and not request.POST.get('isbn') and current_cover_url:
                            changes.append(gettext("Cover: removed"))

                    if changes:
                        book = form.save(commit=False)

                        authors_list = [a.strip() for a in form.cleaned_data['authors_text'].split(',') if a.strip()]
                        book_authors = [Author.objects.get_or_create(name=name)[0] for name in authors_list]
                        book.authors.set(book_authors)

                        editorial_obj = None
                        if form.cleaned_data['editorial_name']:
                            editorial_obj, _ = Editorial.objects.get_or_create(name=form.cleaned_data['editorial_name'])
                        book.editorial = editorial_obj

                        language_obj = None
                        if form.cleaned_data['language_name']:
                            language_obj, _ = Language.objects.get_or_create(name=form.cleaned_data['language_name'])
                        book.language = language_obj

                        genres_list = [g.strip() for g in form.cleaned_data['genres_text'].split(',') if g.strip()]
                        book_genres = [Genre.objects.get_or_create(name=name)[0] for name in genres_list]
                        book.genres.set(book_genres)

                        formats_list = [f.strip() for f in form.cleaned_data['formats_text'].split(',') if f.strip()]
                        book_formats = [Format.objects.get_or_create(name=name)[0] for name in formats_list]
                        book.formats.set(book_formats)

                        if book_cover_file:
                            file_name = default_storage.save(gettext(f'book_covers/{book_cover_file.name}'), ContentFile(book_cover_file.read()))
                            book.cover = file_name
                        elif request.POST.get('cover_url_hidden'):
                            try:
                                image_url = request.POST.get('cover_url_hidden')
                                response = requests.get(image_url, stream=True)
                                if response.status_code == 200:
                                    content_type = response.headers.get('Content-Type', '').lower()
                                    ext = 'jpg'
                                    if 'png' in content_type: ext = 'png'
                                    elif 'gif' in content_type: ext = 'gif'
                                    file_name = gettext(f"book_covers/{book.isbn or 'no_isbn'}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}")
                                    saved_path = default_storage.save(file_name, ContentFile(response.content))
                                    book.cover = saved_path
                                else:
                                    if 'Cover: removed' in changes:
                                        book.cover = None
                            except Exception as e:
                                messages.warning(request, gettext("Could not download book cover from Open Library during edit. Keeping existing cover if any."))
                                if 'Cover: removed' in changes:
                                    book.cover = None
                        else:
                            book.cover = None

                        book.last_modified_by = request.user
                        book.last_modified_at = timezone.now()
                        book.save()

                        BookEdit.objects.create(
                            book=book,
                            editor=request.user,
                            changes_summary=gettext("Edited: ") + "; ".join(changes)
                        )
                        messages.success(request, gettext(f"'{book.title}' has been updated successfully!"))
                        return redirect(reverse('book_detail', args=[book.pk]))
                    else:
                        messages.info(request, gettext("No changes were made to the book."))
                        return redirect(reverse('book_detail', args=[book.pk]))

                except Exception as e:
                    messages.error(request, gettext(f"An error occurred while updating the book: {e}"))
            elif action == 'preview':
                show_preview_modal = True
                book_cover_file = request.FILES.get('cover')
                if book_cover_file:
                    from django.core.files.storage import FileSystemStorage
                    fs = FileSystemStorage()
                    temp_file_name = fs.save(book_cover_file.name, book_cover_file)
                    book_data_for_preview['temp_cover_url'] = fs.url(temp_file_name)
                elif request.POST.get('cover_url_hidden'):
                     book_data_for_preview['temp_cover_url'] = request.POST.get('cover_url_hidden')
                elif book.cover and not book_cover_file:
                     book_data_for_preview['temp_cover_url'] = book.cover.url
        else:
            messages.error(request, gettext("Please correct the errors in the form."))
            book_data_for_preview = {
                'title': request.POST.get('title'),
                'isbn': request.POST.get('isbn'),
                'release_date': request.POST.get('release_date'),
                'edition_number': request.POST.get('edition_number'),
                'authors_text': request.POST.get('authors_text'),
                'genres_text': request.POST.get('genres_text'),
                'formats_text': request.POST.get('formats_text'),
                'editorial_name': request.POST.get('editorial_name'),
                'language_name': request.POST.get('language_name'),
                'cover_url': request.POST.get('cover_url_hidden')
            }
            book_cover_file = request.FILES.get('cover')
            if book_cover_file:
                from django.core.files.storage import FileSystemStorage
                fs = FileSystemStorage()
                temp_file_name = fs.save(book_cover_file.name, book_cover_file)
                book_data_for_preview['temp_cover_url'] = fs.url(temp_file_name)
            elif request.POST.get('cover_url_hidden'):
                 book_data_for_preview['temp_cover_url'] = request.POST.get('cover_url_hidden')
            elif book.cover:
                book_data_for_preview['temp_cover_url'] = book.cover.url


    context = {
        'form': form,
        'book_data_for_preview': book_data_for_preview,
        'show_preview_modal': show_preview_modal,
        'is_edit_mode': True,
        'book_id': book.pk,
    }
    return render(request, 'main_app/edit_book.html', context)


# Eliminar un libro (solo para administradores)
@user_passes_test(lambda u: u.is_staff, login_url='/login/') # Redirige a login si no es staff
@login_required
def delete_book_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        try:
            book_title = book.title
            book.delete()
            messages.success(request, gettext(f"The book '{book_title}' has been deleted successfully by an administrator."))
            return redirect(reverse('home')) # Redirige a la página de inicio o a una lista de libros
        except Exception as e:
            messages.error(request, gettext(f"An error occurred while deleting the book: {e}"))
            return redirect(request.META.get('HTTP_REFERER', reverse('book_detail', args=[pk])))
    messages.error(request, gettext("Invalid request to delete the book."))
    return redirect(request.META.get('HTTP_REFERER', reverse('book_detail', args=[pk])))


@login_required
def add_review_view(request):
    context = {
        'message': gettext("Write a review for a book you have already read.")
    }
    return render(request, 'main_app/add_review.html', context)

@login_required
def add_review_for_book_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        review_text = request.POST.get('review')
        rating_value = request.POST.get('rating')

        if not review_text or not rating_value:
            messages.error(request, gettext("Review and rating are required."))
        else:
            try:
                rating_value = float(rating_value)
                if not (0 <= rating_value <= 5):
                    raise ValueError("Rating out of range")
                
                HasRead.objects.update_or_create(
                    user=request.user,
                    book=book,
                    defaults={
                        'review': review_text,
                        'rating': rating_value,
                        'review_date': timezone.now()
                    }
                )
                messages.success(request, gettext(f"Your review for '{book.title}' has been saved!"))

                wants_to_read_entry = WantsToRead.objects.filter(user=request.user, book=book)
                if wants_to_read_entry.exists():
                    wants_to_read_entry.delete()
                    messages.info(request, gettext(f"'{book.title}' has been removed from your 'Wants to Read' list."))

                return redirect(reverse('book_detail', args=[book.pk]))
            except ValueError:
                messages.error(request, gettext("Rating must be a number between 0 and 5."))
            except Exception as e:
                messages.error(request, gettext(f"An error occurred: {e}"))
        return redirect(request.META.get('HTTP_REFERER', reverse('book_detail', args=[pk])))
    context = {
        'book': book,
    }
    return render(request, 'main_app/add_review_for_book.html', context)

@login_required
def delete_review_view(request, pk):
    review = get_object_or_404(HasRead, pk=pk, user=request.user)

    if request.method == 'POST':
        book_title = review.book.title
        review.delete()
        messages.success(request, gettext(f"Your review for '{book_title}' has been deleted."))
        return redirect(request.META.get('HTTP_REFERER', reverse('home')))
    else:
        messages.error(request, gettext("Invalid request method."))
        return redirect(request.META.get('HTTP_REFERER', reverse('home')))


# Vistas Generales

@login_required
def settings_view(request):
    user = request.user
    
    username_form = ChangeUsernameForm(instance=user)
    password_form = PasswordChangeForm(user=user)
    notification_form = NotificationSettingsForm(instance=user)
    profile_visibility_form = ProfileVisibilityForm(instance=user)
    timezone_form = TimeZoneForm(instance=user)
    theme_form = ThemeForm(instance=user)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'change_username':
            username_form = ChangeUsernameForm(request.POST, instance=user)
            if username_form.is_valid():
                username_form.save()
                messages.success(request, gettext("Your username has been updated successfully!"))
            else:
                for field, errors in username_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                messages.error(request, gettext("Error updating username. Please check the form."))

        elif form_type == 'change_password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, gettext("Your password was successfully updated!"))
            else:
                for field, errors in password_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                messages.error(request, gettext("Error updating password. Please check the form."))
        
        elif form_type == 'toggle_profile_visibility':
            profile_visibility_form = ProfileVisibilityForm(request.POST, instance=user)
            if profile_visibility_form.is_valid():
                profile_visibility_form.save()
                if user.is_public_profile:
                    messages.success(request, gettext("Your profile is now public."))
                else:
                    messages.info(request, gettext("Your profile is now private."))
            else:
                messages.error(request, gettext("Error updating profile visibility."))

        elif form_type == 'update_notification_settings':
            notification_form = NotificationSettingsForm(request.POST, instance=user)
            if notification_form.is_valid():
                notification_form.save()
                messages.success(request, gettext("Notification settings updated successfully!"))
            else:
                messages.error(request, gettext("Error updating notification settings. Please check the form."))

        elif form_type == 'set_timezone':
            timezone_form = TimeZoneForm(request.POST, instance=user)
            if timezone_form.is_valid():
                timezone_form.save()
                messages.success(request, gettext("Time zone updated successfully!"))
            else:
                messages.error(request, gettext("Error updating time zone. Please check the form."))

        elif form_type == 'toggle_theme':
            theme_form = ThemeForm(request.POST, instance=user)
            if theme_form.is_valid():
                theme_form.save()
                if user.is_dark_theme:
                    messages.success(request, gettext("Dark theme activated."))
                else:
                    messages.info(request, gettext("Light theme activated."))
            else:
                messages.error(request, gettext("Error updating theme."))

        return redirect(reverse('settings'))
        
    context = {
        'LANGUAGES': settings.LANGUAGES,
        'username_form': username_form,
        'password_form': password_form,
        'notification_form': notification_form,
        'profile_visibility_form': profile_visibility_form,
        'timezone_form': timezone_form,
        'theme_form': theme_form,
        'profile_is_public': user.is_public_profile, 
        'current_timezone': user.timezone, 
        'timezones': pytz.all_timezones,
        'current_theme_is_dark': user.is_dark_theme,
        'notify_new_followers': user.notify_new_followers,
        'notify_review_likes': user.notify_review_likes,
        'notify_friend_activity': user.notify_friend_activity,
    }
    return render(request, 'main_app/settings.html', context)


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request) # Desloguear al usuario antes de eliminar
        user.delete()
        messages.success(request, gettext("Your account has been deleted successfully."))
        return redirect(reverse('signup')) # Redirigir a la página de registro o inicio de sesión
    messages.error(request, gettext("Invalid request for account deletion."))
    return redirect(reverse('settings'))


@login_required
def manage_blocked_users(request):
    user = request.user
    
    blocked_by_me_entries = BlockedUser.objects.filter(blocker=user).select_related('blocked').order_by('blocked__display_name')
    
    
    context = {
        'blocked_by_me_entries': blocked_by_me_entries,
    }
    return render(request, 'main_app/manage_blocked_users.html', context)


@login_required
def block_user_view(request, pk):
    user_to_block = get_object_or_404(User, pk=pk)
    if request.user == user_to_block:
        messages.error(request, gettext("You cannot block yourself."))
        return redirect(request.META.get('HTTP_REFERER', reverse('home')))

    if request.method == 'POST':
        if not BlockedUser.objects.filter(blocker=request.user, blocked=user_to_block).exists():
            BlockedUser.objects.create(blocker=request.user, blocked=user_to_block)
            messages.success(request, gettext(f"You have blocked {user_to_block.display_name}."))
            Follow.objects.filter(
                Q(follower=request.user, followed=user_to_block) |
                Q(follower=user_to_block, followed=request.user)
            ).delete()
        else:
            messages.info(request, gettext(f"You have already blocked {user_to_block.display_name}."))
    return redirect(request.META.get('HTTP_REFERER', reverse('user_profile', args=[pk])))


@login_required
def unblock_user_view(request, pk):
    user_to_unblock = get_object_or_404(User, pk=pk)
    if request.user == user_to_unblock:
        messages.error(request, gettext("You cannot unblock yourself."))
        return redirect(request.META.get('HTTP_REFERER', reverse('home')))

    if request.method == 'POST':
        blocked_entry = BlockedUser.objects.filter(blocker=request.user, blocked=user_to_unblock)
        if blocked_entry.exists():
            blocked_entry.delete()
            messages.success(request, gettext(f"You have unblocked {user_to_unblock.display_name}."))
        else:
            messages.info(request, gettext(f"You were not blocking {user_to_unblock.display_name}."))
    return redirect(request.META.get('HTTP_REFERER', reverse('manage_blocked_users')))


def help_center(request):
    return render(request, 'main_app/help_center.html')


def contact_support(request):
    return render(request, 'main_app/contact_support.html')


@login_required
def notifications_view(request):
    user = request.user
    notifications = Notification.objects.filter(user=user).order_by('-created_at')

    if request.method == 'GET':
        Notification.objects.filter(user=user, read=False).update(read=True)

    context = {
        'notifications': notifications,
        'unread_count': Notification.objects.filter(user=user, read=False).count(),
    }
    return render(request, 'main_app/notifications.html', context)

@login_required
def mark_all_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        messages.success(request, gettext("All notifications marked as read."))
    return redirect(reverse('notifications'))


def all_books_view(request):
    sort_by = request.GET.get('sort_by', 'title_asc')

    books = Book.objects.all()

    if sort_by == 'title_asc':
        books = books.order_by('title')
    elif sort_by == 'title_desc':
        books = books.order_by('-title')

    # Obtener IDs de libros que el usuario actual ha leído o quiere leer
    has_read_book_ids = set()
    wants_to_read_book_ids = set()
    if request.user.is_authenticated:
        has_read_book_ids = set(HasRead.objects.filter(user=request.user).values_list('book__pk', flat=True))
        wants_to_read_book_ids = set(WantsToRead.objects.filter(user=request.user).values_list('book__pk', flat=True))

    context = {
        'books': books, # Renombrado de 'all_books' a 'books' para consistencia
        'section_title': gettext("All Books"),
        'current_sort': sort_by, # Pasa el orden actual a la plantilla
        'has_read_book_ids': has_read_book_ids,
        'wants_to_read_book_ids': wants_to_read_book_ids,
    }
    return render(request, 'main_app/all_books_list.html', context)

def view_all_recommended_view(request):
    all_recommended_books = Book.objects.all().order_by('?')
    context = {
        'books': all_recommended_books,
        'section_title': gettext("All Recommended Books"),
    }
    return render(request, 'main_app/all_books_list.html', context)

def view_all_trending_view(request):
    all_trending_books = Book.objects.all().order_by('-release_date')
    context = {
        'books': all_trending_books,
        'section_title': gettext("All Trending Books"),
    }
    return render(request, 'main_app/all_books_list.html', context)

def book_detail_view(request, pk):
    book = get_object_or_404(Book.objects.prefetch_related('authors', 'genres', 'formats').select_related('editorial', 'language', 'original_book', 'last_modified_by'), pk=pk)

    popular_book_reviews = HasRead.objects.filter(book=book).annotate(
        num_likes=Count('likes')
    ).order_by('-num_likes', '-review_date')[:5]

    friends_read_this_book = []
    has_read_this_book = False
    wants_to_read_this_book = False

    if request.user.is_authenticated:
        friend_users = set()

        following_me = Follow.objects.filter(followed=request.user).values_list('follower', flat=True)
        my_following = Follow.objects.filter(follower=request.user).values_list('followed', flat=True)
        mutual_friends_ids = set(following_me).intersection(set(my_following))

        friends_read_this_book = HasRead.objects.filter(
            book=book,
            user__pk__in=list(mutual_friends_ids) 
        ).select_related('user').order_by('-review_date')

        has_read_this_book = HasRead.objects.filter(user=request.user, book=book).exists()
        wants_to_read_this_book = WantsToRead.objects.filter(user=request.user, book=book).exists()

    edit_history = BookEdit.objects.filter(book=book).select_related('editor')[:5]

    context = {
        'book': book,
        'popular_book_reviews': popular_book_reviews,
        'friends_read_this_book': friends_read_this_book,
        'has_read_this_book': has_read_this_book,
        'wants_to_read_this_book': wants_to_read_this_book,
        'edit_history': edit_history,
    }
    return render(request, 'main_app/book_detail.html', context)

def search_results_view(request):
    query = request.GET.get('q', '')
    books_results = []
    users_results = []

    if query:
        users_results_queryset = User.objects.filter(
            Q(username__icontains=query) |
            Q(display_name__icontains=query)
        ).exclude(pk=request.user.pk if request.user.is_authenticated else None)

        if request.user.is_authenticated:
            blocked_by_me_pks = BlockedUser.objects.filter(blocker=request.user).values_list('blocked__pk', flat=True)
            blocking_me_pks = BlockedUser.objects.filter(blocked=request.user).values_list('blocker__pk', flat=True)
            all_blocked_pks = list(set(list(blocked_by_me_pks) + list(blocking_me_pks)))
            users_results_queryset = users_results_queryset.exclude(pk__in=all_blocked_pks)

        final_users_results = []
        if request.user.is_authenticated:
            following_me = Follow.objects.filter(followed=request.user).values_list('follower__pk', flat=True)
            my_following = Follow.objects.filter(follower=request.user).values_list('followed__pk', flat=True)
            mutual_friends_pks = set(following_me).intersection(set(my_following))

            for user_found in users_results_queryset:
                if user_found.is_public_profile:
                    final_users_results.append(user_found)
                elif user_found.pk in mutual_friends_pks: 
                    final_users_results.append(user_found)
        else: 
            final_users_results = list(users_results_queryset.filter(is_public_profile=True))

        users_results = final_users_results[:10]

        for user_found in users_results:
            user_found.is_following = Follow.objects.filter(follower=request.user, followed=user_found).exists()
            user_found.is_friend = (user_found.is_following and
                                    Follow.objects.filter(follower=user_found, followed=request.user).exists())

        books_results = Book.objects.filter(
            Q(title__icontains=query) |
            Q(isbn__icontains=query) |
            Q(editorial__name__icontains=query) |
            Q(authors__name__icontains=query)
        ).distinct()[:10]

    context = {
        'query': query,
        'books': books_results,
        'users': users_results,
    }
    return render(request, 'main_app/search_results.html', context)

@login_required
def autocomplete_data_view(request, model_name):
    query = request.GET.get('q', '')
    results = []
    Model = None

    if model_name == 'author':
        Model = Author
    elif model_name == 'editorial':
        Model = Editorial
    elif model_name == 'language':
        Model = Language
    elif model_name == 'genre':
        Model = Genre
    elif model_name == 'format':
        Model = Format
    
    if Model:
        queryset = Model.objects.filter(name__icontains=query).order_by('name')[:10]
        results = [{'id': obj.pk, 'name': obj.name} for obj in queryset]
    
    return JsonResponse(results, safe=False)

def lookup_isbn_view(request):
    isbn = request.GET.get('isbn')
    if not isbn:
        return JsonResponse({'error': 'ISBN parameter is missing.'}, status=400)

    # API de Open Library para buscar por ISBN
    open_library_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    
    try:
        response = requests.get(open_library_url)
        response.raise_for_status() # Lanza un HTTPError para respuestas de error (4xx o 5xx)
        data = response.json()

        if not data:
            return JsonResponse({'error': gettext('Book not found for this ISBN.')}, status=404)

        book_key = f"ISBN:{isbn}"
        book_data = data.get(book_key)

        if not book_data:
            return JsonResponse({'error': gettext('Book data not found for this ISBN key.')}, status=404)

        # Extraer campos relevantes
        title = book_data.get('title', '')
        
        # Fecha de publicación: intentar parsear diferentes formatos
        publish_date_str = book_data.get('publish_date', '')
        release_date = ''
        if publish_date_str:
            try:
                # Intenta con formato 'Month Day, Year'
                dt = timezone.datetime.strptime(publish_date_str, '%B %d, %Y')
                release_date = dt.strftime('%Y-%m-%d')
            except ValueError:
                try:
                    # Intenta con formato 'Year'
                    dt = timezone.datetime.strptime(publish_date_str, '%Y')
                    release_date = dt.strftime('%Y-%m-%d')
                except ValueError:
                    # Si no se puede parsear, dejarlo vacío
                    pass
        
        # Autores
        authors = [a['name'] for a in book_data.get('authors', [])]
        authors_text = ", ".join(authors)

        # Editoriales
        publishers = [p['name'] for p in book_data.get('publishers', [])]
        editorial_name = publishers[0] if publishers else ''

        # Idiomas - Open Library usa claves como /languages/eng.
        languages = []
        lang_map = {
            '/languages/eng': 'English',
            '/languages/spa': 'Spanish',
            '/languages/fre': 'French',
            '/languages/ger': 'German',
            '/languages/jpn': 'Japanese',
            '/languages/zho': 'Chinese',
            '/languages/rus': 'Russian',
            '/languages/jap': 'Japanese',
        }
        for lang_obj in book_data.get('languages', []):
            lang_key = lang_obj.get('key', '')
            languages.append(lang_map.get(lang_key, lang_key.split('/')[-1] if lang_key else ''))
        language_name = languages[0] if languages else ''

        # Géneros (Subjects)
        subjects = [s['name'] for s in book_data.get('subjects', [])]
        genres_text = ", ".join(subjects)

        # Formatos - Open Library no tiene un campo 'formats' directo. Dejar vacío o inferir si es posible.
        # Por ahora, se dejará vacío para que el usuario lo ingrese.
        formats_text = ''
        if 'physical_format' in book_data:
             formats_text = book_data['physical_format']


        # Imagen de portada
        # Prioriza la imagen grande, luego mediana, luego pequeña
        cover_url = book_data.get('cover', {}).get('large') or \
                    book_data.get('cover', {}).get('medium') or \
                    book_data.get('cover', {}).get('small')

        response_data = {
            'title': title,
            'authors_text': authors_text,
            'release_date': release_date,
            'editorial_name': editorial_name,
            'language_name': language_name,
            'genres_text': genres_text,
            'formats_text': formats_text,
            'cover_url': cover_url,
        }
        return JsonResponse(response_data)

    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': gettext(f'Failed to fetch data from Open Library: {e}')}, status=500)
    except Exception as e:
        return JsonResponse({'error': gettext(f'An unexpected error occurred: {e}')}, status=500)


def add_book_by_isbn_view(request):
    book_info = None
    isbn_from_url = request.GET.get('isbn')
    if isbn_from_url:
        try:
            openlibrary_response = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_from_url}&format=json&jscmd=data")
            openlibrary_response.raise_for_status()
            data = openlibrary_response.json()
            book_key = f"ISBN:{isbn_from_url}"
            if book_key in data:
                book_info = data[book_key]

                book_info = {
                    'isbn': isbn_from_url,
                    'title': book_info.get('title'),
                    'authors_text': ', '.join([a['name'] for a in book_info.get('authors', [])]),
                    'release_date': book_info.get('publish_date'),
                    # 'edition_number': book_info.get('number_of_pages'),
                    'editorial_name': book_info.get('publishers', [{}])[0].get('name'),
                    'language_name': book_info.get('languages', [{}])[0].get('name'),
                    'formats_text': ', '.join([f['name'] for f in book_info.get('physical_format', [])]),
                    'cover_url': f"https://covers.openlibrary.org/b/isbn/{isbn_from_url}-L.jpg"
                }
        except requests.exceptions.RequestException as e:
            messages.error(request, gettext(f"Error fetching book details from API: {e}"))
            book_info = None 
        except Exception as e:
            messages.error(request, gettext(f"An unexpected error occurred during API lookup: {e}"))
            book_info = None 

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        form_action = request.POST.get('form_action')

        if form.is_valid():
            isbn = form.cleaned_data['isbn']
            
            try:
                with transaction.atomic():
                    
                    if Book.objects.filter(isbn=isbn).exists():
                        form.add_error('isbn', gettext('A book with this ISBN already exists.'))
                        
                        return render(request, 'main_app/add_book_by_isbn.html', {
                            'form': form,
                            'book_info': book_info,
                            'show_preview_modal_on_load': False 
                        })

                    # Handle cover image upload or URL from API
                    if request.FILES.get('cover'):
                        book.cover = request.FILES['cover']
                    elif request.POST.get('cover_url_hidden'):
                        cover_url = request.POST.get('cover_url_hidden')
                        if cover_url and cover_url != settings.STATIC_URL + 'images/default_book.png':
                            try:
                                response = requests.get(cover_url, stream=True)
                                response.raise_for_status()
                                file_name = os.path.basename(cover_url.split('?')[0]) 
                                if not file_name:
                                    file_name = f'cover_{book.isbn}.jpg'
                                if '.' not in file_name:
                                    file_name += '.jpg' 
                                
                                path = default_storage.save(os.path.join('book_covers', file_name), ContentFile(response.content))
                                book.cover = path
                            except requests.exceptions.RequestException as e:
                                messages.warning(request, gettext(f"Could not download cover image from URL: {e}"))
                            except Exception as e:
                                messages.warning(request, gettext(f"Error saving cover image: {e}"))

                    book.save()
                    authors_text = request.POST.get('authors_text')
                    if authors_text:
                        for name in [n.strip() for n in authors_text.split(',') if n.strip()]:
                            author, created = Author.objects.get_or_create(name=name)
                            book.authors.add(author)

                    genres_text = request.POST.get('genres_text')
                    if genres_text:
                        for name in [n.strip() for n in genres_text.split(',') if n.strip()]:
                            genre, created = Genre.objects.get_or_create(name=name)
                            book.genres.add(genre)

                    editorial_name = request.POST.get('editorial_name')
                    if editorial_name:
                        editorial, created = Editorial.objects.get_or_create(name=editorial_name)
                        book.editorial = editorial
                    
                    language_name = request.POST.get('language_name')
                    if language_name:
                        language, created = Language.objects.get_or_create(name=language_name)
                        book.language = language

                    formats_text = request.POST.get('formats_text')
                    if formats_text:
                        for name in [n.strip() for n in formats_text.split(',') if n.strip()]:
                            book_format, created = Format.objects.get_or_create(name=name)
                            book.formats.add(book_format)


                    book.save() 
                    if form_action == 'save':
                        messages.success(request, gettext('Book added successfully!'))
                        return redirect('book_detail', pk=book.pk) 
                    elif form_action == 'preview':
                        
                        messages.success(request, gettext('Book saved and previewed!')) 
                        return redirect('book_detail', pk=book.pk)

            except Exception as e:
                messages.error(request, gettext(f'An error occurred while saving the book: {e}'))
                print(f"Error saving book: {e}") 
                return render(request, 'main_app/add_book_by_isbn.html', {
                    'form': form,
                    'book_info': book_info, 
                    'show_preview_modal_on_load': False
                })

        else: 
            messages.error(request, gettext('Please correct the errors below.'))
            
            show_preview_modal_on_load = False
            book_data_for_preview = None
            if form_action == 'preview':
                book_data_for_preview = {
                    'isbn': request.POST.get('isbn'),
                    'title': request.POST.get('title'),
                    'authors_text': request.POST.get('authors_text'),
                    'release_date': request.POST.get('release_date'),
                    'edition_number': request.POST.get('edition_number'),
                    'editorial_name': request.POST.get('editorial_name'),
                    'language_name': request.POST.get('language_name'),
                    'genres_text': request.POST.get('genres_text'),
                    'formats_text': request.POST.get('formats_text'),
                    'temp_cover_url': request.POST.get('cover_url_hidden')
                }
                if request.FILES.get('cover'):

                    pass

                show_preview_modal_on_load = True

            return render(request, 'main_app/add_book_by_isbn.html', {
                'form': form,
                'book_info': book_info, # Pass original book_info back
                'show_preview_modal_on_load': show_preview_modal_on_load,
                'book_data_for_preview': json.dumps(book_data_for_preview) if book_data_for_preview else None
            })

    else: 
        initial_data = {}
        if book_info:
            initial_data = {
                'isbn': book_info.get('isbn'),
                'title': book_info.get('title'),
              
                'release_date': book_info.get('release_date'),
                'edition_number': book_info.get('edition_number'),
            }
        form = BookForm(initial=initial_data)

    return render(request, 'main_app/add_book_by_isbn.html', {
        'form': form,
        'book_info': book_info, 
        'show_preview_modal_on_load': False
    })


@login_required
def add_book_by_ocr_view(request):

    return render(request, 'main_app/add_book_by_ocr.html')


@login_required
def ocr_isbn_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image_data')

            if not image_data:
                return JsonResponse({'error': gettext('No image data provided.')}, status=400)

            # 1. Decodificar la imagen Base64
            # El string de image_data viene con un prefijo "data:image/jpeg;base64,"
            # Necesitamos quitar ese prefijo para obtener solo la cadena base64.
            try:
                format_prefix, base64_string = image_data.split(';base64,')
                decoded_image = base64.b64decode(base64_string)
            except ValueError:
                return JsonResponse({'error': gettext('Invalid image data format. Expected base64 string.')}, status=400)

            # 2. Abrir la imagen con Pillow
            image = Image.open(BytesIO(decoded_image))

            # 3. Realizar OCR con Tesseract
            # Puedes ajustar 'config' para mejorar la precisión.
            # '--psm 6': Asume un solo bloque uniforme de texto.
            # '--psm 7': Trata la imagen como una sola línea de texto. (Útil para ISBNs)
            # '--oem 3': Usa el motor de OCR más nuevo.
            # Considera usar 'lang=' si el ISBN contiene caracteres especiales o si sabes el idioma.
            raw_text = pytesseract.image_to_string(image, config='--psm 7 --oem 3')
            print(f"OCR Raw Text: {raw_text}") # Para depuración: ver qué detecta Tesseract

            # 4. Procesar y limpiar el texto para encontrar el ISBN
            # Este es un patrón de RegEx más robusto para ISBN-10 y ISBN-13
            # Busca un patrón de ISBN que puede incluir "ISBN", guiones, y ser 10 o 13 dígitos
            # con 'X' para ISBN-10.
            isbn_pattern = re.compile(
                r'\b(?:ISBN(?:-1[03])?:?)(?=[- ]*[0-9X])(?:(?![ -]*$)(?:[ -]?[0-9X]){9,16})\b|' # Para ISBN con prefijo
                r'\b(?:[0-9]{9}[0-9X]|[0-9]{13})\b', # Para ISBN de solo 10 o 13 dígitos
                re.IGNORECASE
            )
            
            found_isbns = isbn_pattern.findall(raw_text)
            
            cleaned_isbn = None
            if found_isbns:
                # Tomar el primer ISBN encontrado y limpiarlo (quitar guiones y texto "ISBN")
                # re.sub(r'[^0-9X]', '', s.upper()) elimina todo excepto dígitos y 'X', y lo convierte a mayúsculas.
                potential_isbn = re.sub(r'[^0-9X]', '', found_isbns[0].upper()) 
                
                # Validación básica de la longitud
                if len(potential_isbn) in [10, 13]:
                    cleaned_isbn = potential_isbn
                else:
                    print(f"Found potential ISBN {potential_isbn} but length is not 10 or 13.")
            
            if cleaned_isbn:
                return JsonResponse({'isbn': cleaned_isbn}, status=200)
            else:
                return JsonResponse({'error': gettext('No valid ISBN found in the scanned image. Please try again.')}, status=404)

        except json.JSONDecodeError:
            return JsonResponse({'error': gettext('Invalid JSON.')}, status=400)
        except pytesseract.TesseractNotFoundError:
            # Captura el error si Tesseract no está instalado o en el PATH
            print("Tesseract OCR engine not found. Please ensure it is installed and in your system's PATH.")
            return JsonResponse({'error': gettext('Tesseract OCR engine not found. Please install it or check its path.')}, status=500)
        except Exception as e:
            print(f"Error in OCR ISBN view: {e}")
            return JsonResponse({'error': gettext(f'An unexpected error occurred during OCR: {e}')}, status=500)
    return JsonResponse({'error': gettext('Invalid request method.')}, status=405)

