(function () {
    "use strict";

    const form = document.querySelector("[data-research-editor]");
    if (!form) return;

    const autosaveUrl = form.dataset.autosaveUrl;
    const versionInput = form.querySelector("[name='object_version']");
    const status = document.getElementById("autosave-status");
    const saveButton = form.querySelector("[data-manual-save]");
    if (!autosaveUrl || !versionInput || !status) return;

    let debounceTimer = null;
    let activeRequest = null;
    let changeSequence = 0;
    let savedSequence = 0;
    let manualSubmitRequested = false;
    let nativeSubmitStarted = false;
    let autosavePaused = false;

    function setStatus(message, state) {
        status.textContent = message;
        status.classList.toggle("error", state === "error");
        status.classList.toggle("success", state === "success");
        status.classList.toggle("saving", state === "saving");
    }

    function startNativeSubmit() {
        nativeSubmitStarted = true;
        manualSubmitRequested = false;
        window.removeEventListener("beforeunload", warnBeforeLeaving);
        if (saveButton) {
            saveButton.disabled = true;
            saveButton.textContent = "正在保存…";
        }
        setStatus("正在保存最终版本…", "saving");
        form.requestSubmit();
    }

    async function runAutosave() {
        if (activeRequest || autosavePaused || nativeSubmitStarted) {
            return activeRequest;
        }

        const requestSequence = changeSequence;
        const requestBody = new FormData(form);
        setStatus("正在自动保存…", "saving");

        activeRequest = fetch(autosaveUrl, {
            method: "POST",
            body: requestBody,
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        });

        try {
            const response = await activeRequest;
            let payload = {};
            try {
                payload = await response.json();
            } catch (error) {
                payload = {};
            }

            if (response.ok) {
                versionInput.value = payload.version;
                savedSequence = requestSequence;
                const time = new Date().toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                });
                setStatus(`已自动保存 ${time}`, "success");
            } else if (response.status === 409) {
                autosavePaused = true;
                setStatus(
                    "检测到其他页面的更新。自动保存已暂停；当前草稿仍在本页，请先复制草稿再刷新。",
                    "error",
                );
            } else {
                setStatus(
                    payload.message || "自动保存失败，可点击“保存记录”重试。",
                    "error",
                );
            }
        } catch (error) {
            setStatus("网络异常，自动保存失败；当前草稿仍在本页。", "error");
        } finally {
            activeRequest = null;
            if (manualSubmitRequested) {
                startNativeSubmit();
            } else if (
                changeSequence > requestSequence &&
                !autosavePaused &&
                !nativeSubmitStarted
            ) {
                scheduleAutosave(300);
            }
        }
        return null;
    }

    function scheduleAutosave(delay) {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(function () {
            debounceTimer = null;
            runAutosave();
        }, delay);
    }

    function markChanged(event) {
        if (
            nativeSubmitStarted ||
            event.target.name === "csrfmiddlewaretoken" ||
            event.target.name === "object_version"
        ) {
            return;
        }
        changeSequence += 1;
        setStatus(
            autosavePaused ? "草稿有未保存更改；自动保存已暂停。" : "有未保存更改…",
            autosavePaused ? "error" : "",
        );
        if (!autosavePaused) scheduleAutosave(1200);
    }

    function warnBeforeLeaving(event) {
        if (
            nativeSubmitStarted ||
            (changeSequence <= savedSequence && !activeRequest)
        ) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    }

    form.addEventListener("input", markChanged);
    form.addEventListener("change", markChanged);
    form.addEventListener("submit", function (event) {
        if (nativeSubmitStarted) return;

        window.clearTimeout(debounceTimer);
        debounceTimer = null;
        if (activeRequest) {
            event.preventDefault();
            manualSubmitRequested = true;
            if (saveButton) {
                saveButton.disabled = true;
                saveButton.textContent = "等待自动保存…";
            }
            setStatus("正在完成自动保存，随后保存最终版本…", "saving");
            return;
        }

        nativeSubmitStarted = true;
        window.removeEventListener("beforeunload", warnBeforeLeaving);
        if (saveButton) saveButton.disabled = true;
        setStatus("正在保存最终版本…", "saving");
    });
    window.addEventListener("beforeunload", warnBeforeLeaving);
}());
