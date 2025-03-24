(function() {
    const style = document.createElement('style');
    style.textContent = `
        .infobar, [class*="infobar"], [id*="infobar"] {
            display: none !important;
        }
    `;
    document.head.appendChild(style);
})();