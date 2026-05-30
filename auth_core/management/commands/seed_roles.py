# auth_core/management/commands/seed_roles.py
#
# WHY THIS FILE EXISTS:
#   The RBAC system requires Role, Permission, and RolePermission rows to exist
#   in the database before any authorization checks can function correctly.
#   Without this seed, every user gets an empty permission set → blanket 403.
#
#   This command is the ONLY place where role/permission data enters the database.
#   It must be run:
#     - Once after initial deployment
#     - After any changes to ROLE_PERMISSION_MAP in users/constants.py
#     - In every test environment setup
#
# SAFETY PROPERTIES:
#   - Fully idempotent: safe to run multiple times on the same database
#   - Uses get_or_create exclusively — never deletes, never overwrites
#   - Wrapped in a single transaction: all-or-nothing
#   - Produces a clear diff-style output: [CREATED] vs [EXISTS]
#   - Does NOT assign roles to users — that is AuthService.register()'s job
#     or a separate admin action
#
# USAGE:
#   python manage.py seed_roles
#   python manage.py seed_roles --dry-run   (validates without writing)

from django.core.management.base import BaseCommand
from django.db import transaction

from users.constants import RoleNames, PermissionCodes, ROLE_PERMISSION_MAP
from users.models import Role, Permission, RolePermission


class Command(BaseCommand):
    help = (
        'Seed the database with all canonical Roles and their Permissions. '
        'Idempotent — safe to run multiple times. '
        'Wraps everything in a single transaction.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be created without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN — no database writes will occur.\n')
            )

        self._seed(dry_run=dry_run)

    @transaction.atomic
    def _seed(self, dry_run: bool) -> None:
        """
        Runs inside a single DB transaction.
        If any operation fails, the entire seed is rolled back.
        """
        # ── Step 1: Ensure all roles exist ───────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n[1/3] Seeding Roles'))

        role_objects: dict[str, Role] = {}

        # ALL roles including SUPER_ADMIN — the role row exists in DB even though
        # super_admin users use is_superuser bypass for permission checks.
        all_role_names = list(RoleNames.ALL)

        for role_name in all_role_names:
            if dry_run:
                role_obj = Role.objects.filter(name=role_name).first()
                exists = role_obj is not None
                tag = '[EXISTS]' if exists else '[WOULD CREATE]'
                self.stdout.write(f'  {tag} Role: {role_name}')
                # Only populate the dict if the row already exists;
                # dry-run must not write anything to the database.
                if role_obj:
                    role_objects[role_name] = role_obj
            else:
                role_obj, created = Role.objects.get_or_create(name=role_name)
                role_objects[role_name] = role_obj
                tag = self.style.SUCCESS('[CREATED]') if created else '[EXISTS] '
                self.stdout.write(f'  {tag} Role: {role_name}')

        # ── Step 2: Ensure all permission codes exist ─────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n[2/3] Seeding Permissions'))

        # Collect every unique code referenced in ROLE_PERMISSION_MAP
        all_codes: set[str] = set()
        for codes in ROLE_PERMISSION_MAP.values():
            all_codes.update(codes)

        # Derive human-readable name and module from the code
        # code format: '<module>.<action>_<resource>'  e.g. 'academics.view_result'
        permission_objects: dict[str, Permission] = {}
        for code in sorted(all_codes):
            parts = code.split('.', 1)  # split on first dot only
            module = parts[0] if len(parts) == 2 else ''
            action_resource = parts[1] if len(parts) == 2 else code
            # Convert 'view_result' → 'View Result'
            human_name = action_resource.replace('_', ' ').title()

            if dry_run:
                perm_obj = Permission.objects.filter(code=code).first()
                exists = perm_obj is not None
                tag = '[EXISTS]' if exists else '[WOULD CREATE]'
                self.stdout.write(f'  {tag} Permission: {code}')
                # Only populate the dict if the row already exists;
                # dry-run must not write anything to the database.
                if perm_obj:
                    permission_objects[code] = perm_obj
            else:
                perm_obj, created = Permission.objects.get_or_create(
                    code=code,
                    defaults={'name': human_name, 'module': module},
                )
                permission_objects[code] = perm_obj
                tag = self.style.SUCCESS('[CREATED]') if created else '[EXISTS] '
                self.stdout.write(f'  {tag} Permission: {code}')

        # ── Step 3: Assign permissions to roles ───────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n[3/3] Seeding Role → Permission assignments'))

        created_count = 0
        exists_count  = 0

        for role_name, codes in ROLE_PERMISSION_MAP.items():
            role_obj = role_objects.get(role_name)
            if not role_obj:
                self.stderr.write(
                    self.style.ERROR(f'  [MISSING ROLE] {role_name} — skipping its permissions')
                )
                continue

            for code in codes:
                perm_obj = permission_objects.get(code)
                if not perm_obj:
                    self.stderr.write(
                        self.style.ERROR(f'  [MISSING PERM] {code} for role {role_name} — skipping')
                    )
                    continue

                if dry_run:
                    exists = RolePermission.objects.filter(role=role_obj, permission=perm_obj).exists()
                    tag = '[EXISTS]' if exists else '[WOULD CREATE]'
                    self.stdout.write(f'  {tag} {role_name} → {code}')
                else:
                    _, created = RolePermission.objects.get_or_create(
                        role=role_obj,
                        permission=perm_obj,
                    )
                    if created:
                        created_count += 1
                    else:
                        exists_count += 1

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write('\n')
        if dry_run:
            self.stdout.write(
                self.style.WARNING('Dry run complete. No changes were written to the database.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Seed complete.\n'
                    f'  Roles:              {len(role_objects)} total\n'
                    f'  Permissions:        {len(permission_objects)} total\n'
                    f'  Role→Perm created:  {created_count}\n'
                    f'  Role→Perm existed:  {exists_count}\n'
                    f'\nThe database is ready for RBAC authorization.\n'
                    f'Run this command again at any time — it is fully idempotent.'
                )
            )
