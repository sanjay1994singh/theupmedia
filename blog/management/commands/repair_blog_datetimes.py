from django.core.management.base import BaseCommand
from django.db import connection

from blog.models import BlogPost


class Command(BaseCommand):
    help = "Repair zero or NULL datetime values in blog posts using raw SQL."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show affected counts without updating.")

    def handle(self, *args, **options):
        table = BlogPost._meta.db_table
        columns = ("published_at", "updated_at", "created_at")
        dry_run = options["dry_run"]

        with connection.cursor() as cursor:
            for column in columns:
                cursor.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM `{table}`
                    WHERE `{column}` IS NULL
                       OR `{column}` = '0000-00-00 00:00:00'
                    """
                )
                count = cursor.fetchone()[0]
                self.stdout.write(f"{column}: {count} bad value(s)")
                if count and not dry_run:
                    cursor.execute(
                        f"""
                        UPDATE `{table}`
                        SET `{column}` = NOW()
                        WHERE `{column}` IS NULL
                           OR `{column}` = '0000-00-00 00:00:00'
                        """
                    )

        prefix = "DRY RUN: " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}Blog datetime repair complete."))
