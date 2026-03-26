from django.core.management.base import BaseCommand
from kcore.models import User


class Command(BaseCommand):
    help = 'Delete all users (dev reset)'

    def handle(self, *args, **options):
        count = User.objects.count()
        User.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Cleared: {count} users'))
