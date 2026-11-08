// Android soft-keyboard hints for the bundled ghostty-web terminal only.
// Do not forward text ourselves: upstream owns beforeinput/composition deduplication.
(() => {
    if (window.__andcodeTerminalIme) return;
    window.__andcodeTerminalIme = true;

    const selector = 'textarea[aria-label="Terminal input"]';
    const configured = new WeakSet();
    function configure(input) {
        if (configured.has(input)) return;
        configured.add(input);
        // Android LatinIME otherwise composes whole English words invisibly in
        // ghostty's hidden textarea until space/Enter. URL mode disables this
        // word prediction without disabling non-Latin composition or hiding text.
        input.setAttribute('inputmode', 'url');
        input.setAttribute('enterkeyhint', 'enter');
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('autocorrect', 'off');
        input.setAttribute('autocapitalize', 'off');
        input.setAttribute('spellcheck', 'false');

        // Ghostty prevents beforeinput and keeps this textarea empty. Android
        // won't generate deleteContentBackward for an empty editable buffer.
        // A local sentinel gives the IME something to delete; it is never sent
        // to the PTY. Restore after upstream handlers (which may clear value).
        let composing = false;
        function reset() {
            if (composing || !input.isConnected) return;
            input.value = ' ';
            input.setSelectionRange(1, 1);
        }
        function scheduleReset() { queueMicrotask(reset); }
        input.addEventListener('compositionstart', () => { composing = true; });
        input.addEventListener('compositionend', () => {
            composing = false;
            scheduleReset();
        });
        for (const type of ['beforeinput', 'input', 'keyup', 'paste', 'focus']) {
            input.addEventListener(type, scheduleReset);
        }
        reset();
    }
    function scan(root) {
        if (root.matches?.(selector)) configure(root);
        root.querySelectorAll?.(selector).forEach(configure);
    }
    scan(document);
    // Terminal tabs are mounted asynchronously and replaced on SPA navigation.
    new MutationObserver(records => {
        for (const record of records) {
            for (const node of record.addedNodes) scan(node);
        }
    }).observe(document.documentElement, { childList: true, subtree: true });
})();
