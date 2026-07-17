from .models import SecurityAuditLog


def record_event(
    *,
    actor,
    event_type,
    resource,
    target_user=None,
    metadata=None,
):
    return SecurityAuditLog.objects.create(
        actor=actor,
        event_type=event_type,
        resource_type=resource._meta.label_lower,
        resource_id=resource.pk,
        target_user=target_user,
        metadata_json=metadata or {},
    )
