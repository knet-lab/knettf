from django.core.management.base import BaseCommand
from kcore.models import User


MOCK_USERS = [
    {'username': 'admin',  'email': 'admin@netsentinel.dev',  'password': 'admin123',  'is_staff': True, 'is_superuser': True},
    {'username': 'alice',  'email': 'alice@netsentinel.dev',  'password': 'alice123'},
    {'username': 'bob',    'email': 'bob@netsentinel.dev',    'password': 'bob123'},
]


class Command(BaseCommand):
    help = 'Create mock users for development'

    def handle(self, *args, **options):
        created, skipped = 0, 0
        for spec in MOCK_USERS:
            if User.objects.filter(username=spec['username']).exists():
                self.stdout.write(f"  skip : {spec['username']} (already exists)")
                skipped += 1
                continue
            User.objects.create_user(
                username=spec['username'],
                email=spec['email'],
                password=spec['password'],
                is_staff=spec.get('is_staff', False),
                is_superuser=spec.get('is_superuser', False),
            )
            self.stdout.write(f"  created : {spec['username']}")
            created += 1
        self.stdout.write(self.style.SUCCESS(f'Done — created {created}, skipped {skipped}'))
