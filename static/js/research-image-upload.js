(function () {
    "use strict";

    const panel = document.querySelector("[data-image-uploader]");
    const textarea = document.getElementById("id_content_markdown");
    if (!panel || !textarea) return;

    const uploadForm = panel.querySelector(".image-upload-form");
    const fileInput = uploadForm && uploadForm.querySelector('input[type="file"]');
    const status = panel.querySelector(".upload-status");
    const library = panel.querySelector(".editor-image-library");

    function setStatus(message, state) {
        status.textContent = message;
        status.classList.remove("error", "success");
        if (state) status.classList.add(state);
    }

    function markdownFor(name, url) {
        const stem = name.replace(/\.[^.]+$/, "") || "实验结果";
        const alt = stem.replace(/\\/g, "\\\\").replace(/\[/g, "\\[").replace(/\]/g, "\\]");
        return `![${alt}](${url})`;
    }

    function insertAtCursor(markdown) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const before = textarea.value.slice(0, start);
        const after = textarea.value.slice(end);
        const prefix = before && !before.endsWith("\n") ? "\n\n" : "";
        const suffix = after && after.startsWith("\n") ? "\n" : "\n\n";
        textarea.setRangeText(prefix + markdown + suffix, start, end, "end");
        textarea.focus();
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
        setStatus("图片已插入正文，请保存记录。", "success");
    }

    function addLibraryImage(result) {
        const empty = library.querySelector(".gallery-empty");
        if (empty) empty.remove();
        const figure = document.createElement("figure");
        figure.className = "image-card";
        const image = document.createElement("img");
        image.src = result.inline_url;
        image.alt = result.name;
        image.loading = "lazy";
        const caption = document.createElement("figcaption");
        const name = document.createElement("span");
        name.textContent = result.name;
        name.title = result.name;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "link-button";
        button.dataset.insertImage = "";
        button.dataset.imageName = result.name;
        button.dataset.inlineUrl = result.inline_url;
        button.textContent = "插入正文";
        caption.append(name, button);
        figure.append(image, caption);
        library.prepend(figure);
    }

    async function uploadFile(file) {
        const csrf = uploadForm.querySelector('input[name="csrfmiddlewaretoken"]').value;
        const data = new FormData();
        data.append("file", file, file.name || "clipboard-image.png");
        const response = await fetch(uploadForm.action, {
            method: "POST",
            body: data,
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "X-CSRFToken": csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        let result;
        try {
            result = await response.json();
        } catch (_error) {
            throw new Error("服务器没有返回有效结果，请刷新页面后重试。");
        }
        if (!response.ok) throw new Error(result.error || "图片上传失败。");
        addLibraryImage(result);
        insertAtCursor(result.markdown || markdownFor(result.name, result.inline_url));
    }

    async function uploadFiles(files) {
        const images = Array.from(files).filter((file) => file.type.startsWith("image/"));
        if (!images.length) {
            setStatus("请选择 PNG、JPEG、GIF 或 WebP 图片。", "error");
            return;
        }
        const button = uploadForm.querySelector('button[type="submit"]');
        button.disabled = true;
        setStatus(`正在上传 ${images.length} 张图片…`);
        try {
            for (const file of images) await uploadFile(file);
            fileInput.value = "";
            setStatus(`${images.length} 张图片已上传并插入正文，请保存记录。`, "success");
        } catch (error) {
            setStatus(error.message || "图片上传失败。", "error");
        } finally {
            button.disabled = false;
        }
    }

    panel.addEventListener("click", function (event) {
        const button = event.target.closest("[data-insert-image]");
        if (!button) return;
        insertAtCursor(markdownFor(button.dataset.imageName, button.dataset.inlineUrl));
    });

    if (!uploadForm) return;

    uploadForm.addEventListener("submit", function (event) {
        event.preventDefault();
        uploadFiles(fileInput.files);
    });

    textarea.addEventListener("paste", function (event) {
        const images = Array.from(event.clipboardData?.files || []).filter((file) => file.type.startsWith("image/"));
        if (!images.length) return;
        event.preventDefault();
        uploadFiles(images);
    });

    textarea.addEventListener("dragover", function (event) {
        if (!event.dataTransfer?.types.includes("Files")) return;
        event.preventDefault();
        panel.classList.add("is-dragging");
    });
    textarea.addEventListener("dragleave", function () {
        panel.classList.remove("is-dragging");
    });
    textarea.addEventListener("drop", function (event) {
        panel.classList.remove("is-dragging");
        if (!event.dataTransfer?.files.length) return;
        event.preventDefault();
        uploadFiles(event.dataTransfer.files);
    });
})();
