from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Repair invalid empty-string FK values in live TV tables."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        tables = {
            "live_tv_livetvchannel": ["category_id", "state_id", "city_id"],
            "live_tv_shortsvideo": ["category_id", "state_id", "city_id"],
        }
        dry_run = options["dry_run"]
        total = 0
        with connection.cursor() as cursor:
            for table, columns in tables.items():
                for column in columns:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table}` WHERE `{column}` = ''")
                    count = cursor.fetchone()[0]
                    if count:
                        self.stdout.write(f"{table}.{column}: {count} invalid empty value(s)")
                        total += count
                        if not dry_run:
                            cursor.execute(f"UPDATE `{table}` SET `{column}` = NULL WHERE `{column}` = ''")
        self.stdout.write(f"{'Would repair' if dry_run else 'Repaired'} {total} value(s).")
