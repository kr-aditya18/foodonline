from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User,UserProfile
# connecting sender and reciever
@receiver(post_save, sender=User)
def post_save_create_profile_receiver(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        try:
            profile = UserProfile.objects.get(user=instance)
            profile.save()  # was profile.save
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=instance)

# connecting sender and reciever

# post.save.connet(post_save_create_profile_receiver)

