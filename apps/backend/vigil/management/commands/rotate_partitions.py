"""
management command: rotate_partitions

- Creates tomorrow's daily partition (idempotent).
- Drops partitions older than 90 days (i.e. day <= today - 91).

Schedule via cron or systemd timer to run once per day, e.g.:
    0 0 * * * /path/to/venv/bin/python manage.py rotate_partitions --database vigil
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Create tomorrow's partition and drop partitions older than 90 days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", default="vigil",
            help="Database alias to operate on (default: vigil)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print SQL without executing.",
        )

    def handle(self, *args, **options):
        db    = options["database"]
        dry   = options["dry_run"]
        today = date.today()

        stmts = []

        # Create tomorrow's partition
        tomorrow = today + timedelta(days=1)
        stmts.append(self._create_sql(tomorrow))

        # Drop partitions older than 90 days: everything before (today - 90)
        cutoff = today - timedelta(days=90)
        # scan 7 extra days back in case the command was skipped
        for offset in range(7):
            drop_day = cutoff - timedelta(days=offset)
            stmts.append(self._drop_sql(drop_day))

        with connections[db].cursor() as cur:
            for sql in stmts:
                if dry:
                    self.stdout.write(sql)
                else:
                    cur.execute(sql)

        if not dry:
            self.stdout.write(self.style.SUCCESS(
                f"rotate_partitions done: created {tomorrow}, dropped <= {cutoff - timedelta(days=1)}"
            ))

    @staticmethod
    def _create_sql(d: date) -> str:
        name  = f"vigil_detectionrecord_{d.strftime('%Y_%m_%d')}"
        start = d.isoformat()
        end   = (d + timedelta(days=1)).isoformat()
        return (
            f"CREATE TABLE IF NOT EXISTS {name} "
            f"PARTITION OF vigil_detectionrecord "
            f"FOR VALUES FROM ('{start}') TO ('{end}');"
        )

    @staticmethod
    def _drop_sql(d: date) -> str:
        name = f"vigil_detectionrecord_{d.strftime('%Y_%m_%d')}"
        return f"DROP TABLE IF EXISTS {name};"
