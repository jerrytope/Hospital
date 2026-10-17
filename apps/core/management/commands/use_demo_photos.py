"""Swap the old gradient placeholder images for the real stock photos in apps/core/demo_photos.py.

    python manage.py use_demo_photos            # replace placeholders, then delete them if nothing uses them
    python manage.py use_demo_photos --keep-old # replace placeholders but keep the old images in the library

Only images titled "Placeholder field photo ..." are touched, so photos you uploaded yourself stay where they are.
Live pages are republished; pages with unpublished changes get a new draft instead, so nothing is lost.
"""
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models, transaction
from wagtail.fields import StreamField
from wagtail.models import Page

from apps.core import demo_photos as dp
from apps.core.models import CustomImage, CustomRendition

PLACEHOLDER_PREFIX = "Placeholder field photo"


class Command(BaseCommand):
    help = "Replace the demo placeholder images with real stock photos."

    def add_arguments(self, parser):
        parser.add_argument("--keep-old", action="store_true", help="Don't delete the old placeholder images")

    @transaction.atomic
    def handle(self, *args, **opts):
        self.old = set(CustomImage.objects.filter(title__startswith=PLACEHOLDER_PREFIX).values_list("id", flat=True))
        if not self.old:
            self.stdout.write("No placeholder images found. Nothing to do.")
            return
        self.changed = 0
        self.fallback = 0
        self.region_counts = defaultdict(int)

        for page in Page.objects.order_by("path").specific():
            self.update_page(page)
        self.update_records()
        self.update_streamfield_models()

        left = self.remaining_references()
        if left:
            self.stdout.write(self.style.WARNING("Still using placeholder images: " + ", ".join(left)))
        elif not opts["keep_old"]:
            CustomImage.objects.filter(id__in=self.old).delete()
            self.stdout.write(f"Deleted {len(self.old)} old placeholder images.")
        self.stdout.write(self.style.SUCCESS(f"Updated {self.changed} items with real photos."))

    # --- helpers ----------------------------------------------------------------------------

    def photo(self, key):
        if key is None:
            key = dp.DEFAULT_POOL[self.fallback % len(dp.DEFAULT_POOL)]
            self.fallback += 1
        return dp.get_photo(key)

    def is_old(self, image_id):
        return image_id in self.old

    def walk(self, node, default_key=None):
        """Replace placeholder ids inside raw StreamField data. Cards and tabs are matched by their title."""
        changed = False
        if isinstance(node, dict):
            if isinstance(node.get("image"), int) and self.is_old(node["image"]):
                node["image"] = self.photo(dp.CARDS.get(node.get("title")) or default_key).id
                changed = True
            for value in node.values():
                changed |= self.walk(value, default_key)
        elif isinstance(node, list):
            for value in node:
                changed |= self.walk(value, default_key)
        return changed

    def update_streamfields(self, obj, default_key=None):
        changed = False
        for field in obj._meta.get_fields():
            if isinstance(field, StreamField):
                raw = list(getattr(obj, field.name).raw_data)
                if self.walk(raw, default_key):
                    setattr(obj, field.name, raw)
                    changed = True
        return changed

    # --- pages ----------------------------------------------------------------------------

    def hero_key(self, page):
        model = page.specific_class.__name__
        if model == "HomePage":
            return dp.HOME_HERO
        if model == "ProgramPage":
            return dp.PROGRAMS.get(page.title)
        if model == "EmergencyPage":
            return dp.EMERGENCIES.get(page.title)
        if model == "StoryPage":
            return dp.STORIES.get(page.title, (None,))[0]
        if model == "CountryPage":
            region = page.region.name if page.region_id else ""
            key = dp.country_key(region, self.region_counts[region])
            self.region_counts[region] += 1
            return key
        return dp.PAGE_HEROES.get(page.slug)

    def update_page(self, page):
        draft = page.has_unpublished_changes
        obj = page.get_latest_revision_as_object() if draft else page
        changed = False

        if self.is_old(getattr(obj, "hero_image_id", None)):
            obj.hero_image = self.photo(self.hero_key(obj))
            changed = True
        if self.is_old(getattr(obj, "share_image_id", None)):
            obj.share_image = obj.hero_image
            changed = True

        inline_key = dp.STORIES.get(obj.title, (None, None))[1] if obj.specific_class.__name__ == "StoryPage" else None
        changed |= self.update_streamfields(obj, inline_key)

        if hasattr(obj, "impact_rows"):
            rows = list(obj.impact_rows.all())
            for i, row in enumerate(rows):
                if self.is_old(row.image_id):
                    row.image = self.photo(dp.IMPACT_ROWS[i % len(dp.IMPACT_ROWS)])
                    changed = True
            obj.impact_rows = rows
        if hasattr(obj, "timeline_entries"):
            entries = list(obj.timeline_entries.all())
            for i, entry in enumerate(entries):
                if self.is_old(entry.photo_id):
                    entry.photo = self.photo(dp.TIMELINE[i % len(dp.TIMELINE)])
                    changed = True
            obj.timeline_entries = entries

        if not changed:
            return
        revision = obj.save_revision()
        if obj.live and not draft:
            revision.publish()
        self.changed += 1
        self.stdout.write(f"  {'draft' if draft else 'page'}: {obj.title}")

    # --- other records ----------------------------------------------------------------------

    def update_records(self):
        from apps.about.models import Person, Report
        from apps.core.models import OrganisationSettings
        from apps.giving.models import GiftItem

        for gift in GiftItem.objects.filter(image_id__in=self.old):
            gift.image = self.photo(dp.GIFTS.get(gift.title))
            gift.save()
            self.changed += 1
        for person in Person.objects.filter(photo_id__in=self.old):
            person.photo = self.photo(dp.PEOPLE.get(person.name, "nurse_portrait"))
            person.save()
            self.changed += 1
        for i, report in enumerate(Report.objects.filter(cover_id__in=self.old).order_by("-year")):
            report.cover = self.photo(dp.REPORT_COVERS[i % len(dp.REPORT_COVERS)])
            report.save()
            self.changed += 1
        for org in OrganisationSettings.objects.filter(default_share_image_id__in=self.old):
            org.default_share_image = self.photo(dp.SHARE_IMAGE)
            org.save()
            self.changed += 1

    def update_streamfield_models(self):
        """StreamFields outside pages, such as the header menu's promo cards."""
        for model in apps.get_models():
            if issubclass(model, Page):
                continue
            if not any(isinstance(f, StreamField) for f in model._meta.get_fields()):
                continue
            for obj in model.objects.all():
                if self.update_streamfields(obj):
                    obj.save()
                    self.changed += 1
                    self.stdout.write(f"  {model._meta.verbose_name}: {obj}")

    def remaining_references(self):
        left = []
        for model in apps.get_models():
            if model is CustomRendition:
                continue  # deleted along with the image
            for field in model._meta.get_fields():
                if isinstance(field, models.ForeignKey) and field.related_model is CustomImage:
                    if model.objects.filter(**{f"{field.name}__in": self.old}).exists():
                        left.append(f"{model.__name__}.{field.name}")
        return left
