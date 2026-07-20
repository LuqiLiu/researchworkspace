(function () {
    "use strict";

    const form = document.querySelector(".form-panel");
    if (!form) return;

    const objectType = form.querySelector("[name='object_type']");
    const teamVisibility = form.querySelector("[name='is_shared_with_team']");
    const teamAttachments = form.querySelector("[name='share_team_attachments']");
    if (!teamVisibility || !teamAttachments) return;

    const sharedByDefault = new Set(["PAPER", "WRITING", "RESOURCE"]);
    let visibilityWasChosen = false;

    function syncAttachmentControl() {
        teamAttachments.disabled = !teamVisibility.checked;
        if (!teamVisibility.checked) teamAttachments.checked = false;
    }

    teamVisibility.addEventListener("change", function () {
        visibilityWasChosen = true;
        syncAttachmentControl();
    });

    if (form.hasAttribute("data-new-research-object") && objectType) {
        objectType.addEventListener("change", function () {
            if (visibilityWasChosen) return;
            teamVisibility.checked = sharedByDefault.has(objectType.value);
            syncAttachmentControl();
        });
    }

    syncAttachmentControl();
}());
