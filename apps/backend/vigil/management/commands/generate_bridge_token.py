from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class Command(BaseCommand):
    help = "Generate a long-lived JWT token for the vigil bridge service account."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="vigil-bridge", help="Service account username")
        parser.add_argument("--years",    type=int, default=10,   help="Token lifetime in years")
        parser.add_argument("--write-env", action="store_true",   help="Write VIGIL_BRIDGE_TOKEN= to .env")

    def handle(self, *args, **options):
        username = options["username"]
        years    = options["years"]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"is_active": True, "email": ""},
        )
        if created:
            user.set_unusable_password()
            user.save()
            self.stdout.write(f"Created service account: {username}")

        token = AccessToken.for_user(user)
        token.set_exp(lifetime=timedelta(days=365 * years))

        token_str = str(token)
        self.stdout.write(f"VIGIL_BRIDGE_TOKEN={token_str}")

        if options["write_env"]:
            from pathlib import Path
            env_path = Path(__file__).resolve().parents[4] / "backend" / ".env"
            lines = env_path.read_text().splitlines() if env_path.exists() else []
            lines = [l for l in lines if not l.startswith("VIGIL_BRIDGE_TOKEN=")]
            lines.append(f"VIGIL_BRIDGE_TOKEN={token_str}")
            env_path.write_text("\n".join(lines) + "\n")
            self.stdout.write(self.style.SUCCESS(f"Written to {env_path}"))
