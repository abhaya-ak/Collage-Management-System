# auth_core/management/commands/cleanup_tokens.py
"""
Management command: cleanup_tokens
====================================
Prunes two tables that grow indefinitely without a cleanup job:

  1. TokenBlacklist  — rows whose refresh token has already expired.
     Once the token's exp timestamp has passed, the row is pointless:
     simplejwt will reject the token on expiry grounds before we even
     check the blacklist. These rows are pure dead weight.

  2. UserSession (closed) — rows older than --retention-days (default 90).
     Closed sessions are kept for the forensic audit trail. Rows older
     than the retention window serve no operational or legal purpose.

Usage:
    python manage.py cleanup_tokens
    python manage.py cleanup_tokens --dry-run
    python manage.py cleanup_tokens --retention-days 30

Recommended cron schedule (runs at 3 AM daily):
    0 3 * * *  /path/to/venv/bin/python /path/to/manage.py cleanup_tokens

Or via Celery beat:
    from django.core.management import call_command
    call_command('cleanup_tokens')
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from auth_core.models import TokenBlacklist, UserSession

# Default retention for closed sessions
_DEFAULT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = 'Prune expired TokenBlacklist entries and old closed UserSession rows'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be deleted without actually deleting anything',
        )
        parser.add_argument(
            '--retention-days',
            type=int,
            default=_DEFAULT_RETENTION_DAYS,
            help=(
                f'Days to retain closed UserSession records for forensic purposes '
                f'(default: {_DEFAULT_RETENTION_DAYS})'
            ),
        )

    def handle(self, *args, **options):
        now            = timezone.now()
        dry_run        = options['dry_run']
        retention_days = options['retention_days']
        session_cutoff = now - timedelta(days=retention_days)

        # ── Build querysets ───────────────────────────────────────────────────
        # TokenBlacklist: jti whose original refresh token has already expired.
        # The token can never be replayed anyway — the row is pure dead weight.
        bl_qs = TokenBlacklist.objects.filter(expires_at__lt=now)

        # UserSession (closed): rows closed longer ago than retention_days.
        # Active sessions are NEVER touched by this command.
        ss_qs = UserSession.objects.filter(
            is_active=False,
            closed_at__lt=session_cutoff,
        )

        bl_count = bl_qs.count()
        ss_count = ss_qs.count()

        # ── Dry run ───────────────────────────────────────────────────────────
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] No rows were deleted.\n'
                    f'  Would delete {bl_count:,} expired TokenBlacklist rows\n'
                    f'  Would delete {ss_count:,} closed UserSession rows '
                    f'(older than {retention_days} days)\n'
                )
            )
            return

        # ── Delete ────────────────────────────────────────────────────────────
        bl_qs.delete()
        ss_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'\ncleanup_tokens complete ({now.strftime("%Y-%m-%d %H:%M UTC")}):\n'
                f'  Deleted {bl_count:,} expired TokenBlacklist rows\n'
                f'  Deleted {ss_count:,} closed UserSession rows '
                f'(older than {retention_days} days)\n'
            )
        )
