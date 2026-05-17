import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='orders.Order')
def create_review_reminders_on_completion(sender, instance, **kwargs):
    """
    When a vendor marks an order as Completed, create ReviewReminder
    rows for every item in that order so the customer gets nudged to review.
    """
    if instance.status != 'Completed':
        return

    try:
        from orders.models import OrderedFood
        from .models import ReviewReminder

        items = OrderedFood.objects.filter(order=instance).select_related('fooditem')
        created_count = 0

        for item in items:
            _, created = ReviewReminder.objects.get_or_create(
                customer=instance.user,
                order_item=item,
            )
            if created:
                created_count += 1

        if created_count:
            logger.info(
                f"[ReviewReminder] Created {created_count} reminders "
                f"for order {instance.order_number} (user: {instance.user.email})"
            )
    except Exception as e:
        logger.warning(f"[ReviewReminder] Signal failed for order {instance.order_number}: {e}")


@receiver(post_save, sender='accounts.User')
def create_onboarding_tour(sender, instance, created, **kwargs):
    """
    Create an OnboardingTour row for every new user automatically.
    """
    if not created:
        return
    try:
        from .models import OnboardingTour
        OnboardingTour.objects.get_or_create(user=instance)
        logger.info(f"[Onboarding] Tour created for new user: {instance.email}")
    except Exception as e:
        logger.warning(f"[Onboarding] Failed to create tour for {instance.email}: {e}")