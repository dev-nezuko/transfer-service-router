"""Bulk-import service areas from a file, in any registered geometry format.

Uses the :mod:`testapp.geometry` registry, so adding a new source format never
touches this command.
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from testapp.geometry import GeometryFormatError, registry
from testapp.models import Provider, ServiceArea


class Command(BaseCommand):
    help = (
        "Import service areas from a JSON file whose records look like "
        '{"provider_email": ..., "name": ..., "price": ..., "geometry": ...}.'
    )

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the JSON file to import.")
        parser.add_argument(
            "--format",
            default="geojson",
            choices=registry.formats,
            help="Geometry format of the 'geometry' field (default: geojson).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate everything, then roll back.",
        )

    def handle(self, *args, **options):
        try:
            with open(options["path"], encoding="utf-8") as handle:
                records = json.load(handle)
        except (OSError, ValueError) as exc:
            raise CommandError("could not read %s: %s" % (options["path"], exc)) from exc

        if not isinstance(records, list):
            raise CommandError("expected a JSON list of service-area records")

        created = 0
        updated = 0
        with transaction.atomic():
            for index, record in enumerate(records, start=1):
                area, was_created = self._import_record(index, record, options["format"])
                created += was_created
                updated += not was_created
                self.stdout.write(
                    "%s %s (%s)"
                    % ("created" if was_created else "updated", area.name, area.provider)
                )
            if options["dry_run"]:
                transaction.set_rollback(True)

        summary = "%d created, %d updated" % (created, updated)
        if options["dry_run"]:
            summary += " (dry run: rolled back)"
        self.stdout.write(self.style.SUCCESS(summary))

    def _import_record(self, index, record, format_name):
        try:
            email = record["provider_email"]
            name = record["name"]
            price = record["price"]
            raw_geometry = record["geometry"]
        except (KeyError, TypeError) as exc:
            raise CommandError("record %d is missing %s" % (index, exc)) from exc

        try:
            provider = Provider.objects.get(email=email)
        except Provider.DoesNotExist as exc:
            raise CommandError(
                "record %d references unknown provider %r" % (index, email)
            ) from exc

        try:
            polygon = registry.read(raw_geometry, format_name)
        except GeometryFormatError as exc:
            raise CommandError(
                "record %d has an unusable geometry: %s" % (index, exc)
            ) from exc

        return ServiceArea.objects.update_or_create(
            provider=provider,
            name=name,
            defaults={"price": price, "area_polygon": polygon},
        )
