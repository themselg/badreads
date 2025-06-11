
from django.urls import path
from . import views

urlpatterns = [

    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.home_view, name='home'),

    path('profile/<int:pk>/', views.user_profile_view, name='user_profile'),
    path('profile/<int:pk>/edit/', views.edit_user_profile_view, name='edit_profile'),
    path('reviews/popular/', views.popular_reviews_view, name='popular_reviews'),
    path('reviews/user/<int:pk>/', views.user_specific_reviews_view, name='user_specific_reviews'),
    path('review/<int:pk>/like/', views.like_review_view, name='like_review'),
    path('review/<int:pk>/delete/', views.delete_review_view, name='delete_review'),

    path('my-list/<int:pk>/', views.my_list_view, name='my_list'),
    path('book/<int:pk>/want-to-read/', views.add_to_wants_to_read_view, name='add_to_wants_to_read'),
    path('my-list/remove/<int:pk>/', views.remove_from_wants_to_read_view, name='remove_from_wants_to_read'),

    path('friends/<int:pk>/', views.friends_view, name='friends'),
    path('friends/search/', views.friends_search_view, name='friends_search'),
    path('user/<int:pk>/follow/', views.follow_user_view, name='follow_user'),

    path('chats/', views.chat_list_view, name='chat_list'),
    path('chats/<int:other_user_pk>/', views.chat_room_view, name='chat_room'),


    path('add/', views.add_book_or_review_view, name='add_book_or_review'),
    path('add/book/', views.add_book_view, name='add_book'),
    path('book/add/ocr/', views.add_book_by_ocr_view, name='add_book_by_ocr'),
    path('book/ocr_isbn/', views.ocr_isbn_view, name='ocr_isbn'),
    path('book/add/isbn/', views.add_book_by_isbn_view, name='add_book_by_isbn'),

    path('book/<int:pk>/edit/', views.edit_book_view, name='edit_book'),
    path('add/review/', views.add_review_view, name='add_review'),
    path('book/<int:pk>/add-review/', views.add_review_for_book_view, name='add_review_for_book'),
    path('book/<int:pk>/delete/', views.delete_book_view, name='delete_book'),


    path('settings/', views.settings_view, name='settings'),
    # path('settings/change-username/', views.change_username, name='change_username'),
    # path('settings/change-password/', views.change_password, name='change_password'),
    path('settings/delete-account/', views.delete_account, name='delete_account'),
    # path('settings/toggle-profile-visibility/', views.toggle_profile_visibility, name='toggle_profile_visibility'),
    # path('settings/update-notifications/', views.update_notification_settings, name='update_notification_settings'),
    # path('settings/set-timezone/', views.set_timezone, name='set_timezone'),
    # path('settings/toggle-theme/', views.toggle_theme, name='toggle_theme'),
    path('settings/manage-blocked-users/', views.manage_blocked_users, name='manage_blocked_users'),
    path('user/<int:pk>/block/', views.block_user_view, name='block_user'), # New URL for blocking
    path('user/<int:pk>/unblock/', views.unblock_user_view, name='unblock_user'), # New URL for unblocking
    path('help/', views.help_center, name='help_center'),
    path('contact/', views.contact_support, name='contact_support'),

    path('books/all/', views.all_books_view, name='all_books'),
    path('books/recommended/all/', views.view_all_recommended_view, name='view_all_recommended'),
    path('books/trending/all/', views.view_all_trending_view, name='view_all_trending'),
    path('book/<int:pk>/', views.book_detail_view, name='book_detail'),
    path('search/', views.search_results_view, name='search_results'),

    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('autocomplete/<str:model_name>/', views.autocomplete_data_view, name='autocomplete_data'),
    path('book/lookup_isbn/', views.lookup_isbn_view, name='lookup_isbn'),

]
