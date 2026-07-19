window.MathJax = {
    tex: {
        inlineMath: [["$", "$"], ["\\(", "\\)"]],
        displayMath: [["$$", "$$"], ["\\[", "\\]"]],
        processEscapes: true,
        processEnvironments: true,
    },
    options: {
        skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"],
    },
};

document.addEventListener("htmx:afterSwap", function (event) {
    if (window.MathJax && typeof window.MathJax.typesetPromise === "function") {
        window.MathJax.typesetPromise([event.detail.target]).catch(function () {
            // A malformed formula must not break the rest of the page.
        });
    }
});
