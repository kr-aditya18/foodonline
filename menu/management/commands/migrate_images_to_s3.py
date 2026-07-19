import os
import requests
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile

from accounts.models import UserProfile
from vendor.models import Vendor
from menu.models import FoodItem
from ai_assistant.models import FoodReview

CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')


class Command(BaseCommand):
    help = "Migrate existing Cloudinary-hosted images to S3"

    def migrate_field(self, queryset, field_name, label):
        migrated, skipped, failed = 0, 0, 0
        for obj in queryset:
            field = getattr(obj, field_name)
            public_id = field.name if field else None

            if not public_id:
                skipped += 1
                continue

            if public_id.startswith('http'):
                url = public_id  # already a full URL, unlikely but just in case
            else:
                url = f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{public_id}"

            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                filename = public_id.split('/')[-1]
                getattr(obj, field_name).save(
                    filename,
                    ContentFile(response.content),
                    save=True
                )
                migrated += 1
                self.stdout.write(f"  ✓ {label} #{obj.pk}: {filename}")
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {label} #{obj.pk} ({url}): {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"{label}: {migrated} migrated, {skipped} skipped, {failed} failed"
        ))

    def handle(self, *args, **options):
        self.stdout.write("Migrating UserProfile.profile_picture...")
        self.migrate_field(UserProfile.objects.all(), 'profile_picture', 'UserProfile.profile_picture')

        self.stdout.write("Migrating UserProfile.cover_photo...")
        self.migrate_field(UserProfile.objects.all(), 'cover_photo', 'UserProfile.cover_photo')

        self.stdout.write("Migrating Vendor.vendor_license...")
        self.migrate_field(Vendor.objects.all(), 'vendor_license', 'Vendor.vendor_license')

        self.stdout.write("Migrating FoodItem.image...")
        self.migrate_field(FoodItem.objects.all(), 'image', 'FoodItem.image')

        self.stdout.write("Migrating FoodReview.image...")
        self.migrate_field(FoodReview.objects.all(), 'image', 'FoodReview.image')