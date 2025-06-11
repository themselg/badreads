from .models import Notification

def unread_notifications_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}