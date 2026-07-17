from django.db.models.signals import post_delete, pre_delete
from django.db import transaction
from django.dispatch import receiver

from app.accounts.services import release_storage

from .models import PublishedAttachment


@receiver(pre_delete, sender=PublishedAttachment)
def remember_public_attachment_owner(sender, instance, **kwargs):
    instance._quota_owner_id = instance.snapshot.owner_id


@receiver(post_delete, sender=PublishedAttachment)
def delete_public_attachment_file_and_release_quota(sender, instance, **kwargs):
    name = instance.file.name
    storage = instance.file.storage
    if name:
        transaction.on_commit(
            lambda: storage.delete(name) if storage.exists(name) else None
        )
    owner_id = getattr(instance, "_quota_owner_id", None)
    if owner_id:
        release_storage(owner_id, instance.size)
