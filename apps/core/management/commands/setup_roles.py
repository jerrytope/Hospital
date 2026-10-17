"""Create the staff roles (Wagtail groups) described in the implementation plan.

Safe to run repeatedly: it brings each group's permissions back to the defined set.
The site owner is a superuser (python manage.py createsuperuser) and needs no group.
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from wagtail.models import Collection, GroupApprovalTask, GroupCollectionPermission, GroupPagePermission, Page, Workflow, WorkflowPage

CONTENT_SNIPPETS = [
    ("taxonomy", "region"), ("taxonomy", "topic"), ("resources", "resource"),
    ("emergencies", "situationreport"), ("emergencies", "mediaalert"), ("emergencies", "pastemergency"),
    ("about", "person"), ("about", "report"), ("pages", "office"),
]
COMMS_MODELS = [("newsletter", "subscriber"), ("emergencies", "situationreport"), ("emergencies", "mediaalert"), ("resources", "resource")]
FINANCE_MODELS = [
    ("giving", "donation"), ("giving", "recurringgift"), ("giving", "appeal"), ("giving", "bankaccount"),
    ("giving", "banktransfernotice"), ("giving", "giftitem"), ("giving", "giftorder"), ("giving", "ecard"),
    ("fundraising", "fundraiser"), ("fundraising", "fundraiserreport"), ("payments", "webhookevent"),
    ("about", "report"), ("newsletter", "subscriber"),
]

ROLES = {
    "Content Editor": {
        "pages": ["add_page", "change_page"],
        "models": CONTENT_SNIPPETS,
        "media": True,
    },
    "Publisher": {
        "pages": ["add_page", "change_page", "publish_page", "lock_page", "unlock_page", "delete_page"],
        "models": CONTENT_SNIPPETS + [("wagtailredirects", "redirect")],
        "media": True,
        "extra": [("core", "change_navigationsettings"), ("core", "change_organisationsettings")],
    },
    "Communications": {
        "pages": ["add_page", "change_page", "publish_page"],
        "models": COMMS_MODELS,
        "media": True,
    },
    "Fundraising & Finance": {
        "pages": [],
        "models": FINANCE_MODELS,
        "media": False,
        "extra": [("giving", "change_donationsettings")],
    },
    "HR": {"pages": [], "models": [("involvement", "job")], "media": False},
    "Procurement": {"pages": [], "models": [("involvement", "tender")], "media": True},
    "Events": {"pages": [], "models": [("involvement", "event")], "media": True},
}


def model_perms(app_label, model):
    return Permission.objects.filter(
        content_type__app_label=app_label,
        codename__in=[f"{a}_{model}" for a in ("add", "change", "delete", "view")],
    )


class Command(BaseCommand):
    help = "Create or refresh the staff roles and the content approval workflow."

    def handle(self, *args, **options):
        access_admin = Permission.objects.get(content_type__app_label="wagtailadmin", codename="access_admin")
        root_page = Page.objects.filter(depth=2).first() or Page.get_first_root_node()
        root_collection = Collection.get_first_root_node()
        media_perms = list(
            Permission.objects.filter(
                content_type__app_label__in=["wagtailimages", "wagtaildocs"],
                codename__in=["add_image", "change_image", "choose_image", "add_document", "change_document", "choose_document"],
            )
        )

        for name, spec in ROLES.items():
            group, created = Group.objects.get_or_create(name=name)
            perms = [access_admin]
            for app_label, model in spec["models"]:
                perms.extend(model_perms(app_label, model))
            for app_label, codename in spec.get("extra", []):
                perms.extend(Permission.objects.filter(content_type__app_label=app_label, codename=codename))
            group.permissions.set(perms)

            GroupPagePermission.objects.filter(group=group).delete()
            for codename in spec["pages"]:
                GroupPagePermission.objects.create(
                    group=group, page=root_page, permission=Permission.objects.get(content_type__app_label="wagtailcore", codename=codename)
                )
            GroupCollectionPermission.objects.filter(group=group).delete()
            if spec["media"]:
                for perm in media_perms:
                    GroupCollectionPermission.objects.create(group=group, collection=root_collection, permission=perm)
            self.stdout.write(f"{'Created' if created else 'Updated'} role: {name}")

        # Content Editors submit; Publishers approve.
        workflow, _ = Workflow.objects.get_or_create(name="Editorial approval", defaults={"active": True})
        task, _ = GroupApprovalTask.objects.get_or_create(name="Publisher approval")
        task.groups.set(Group.objects.filter(name__in=["Publisher"]))
        if not workflow.workflow_tasks.filter(task=task).exists():
            workflow.workflow_tasks.create(task=task, sort_order=0)
        WorkflowPage.objects.update_or_create(page=root_page, defaults={"workflow": workflow})
        self.stdout.write(self.style.SUCCESS("Roles ready. Add staff to groups in Admin > Settings > Users."))
