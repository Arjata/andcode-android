import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../app/src/main/assets/andcode-terminal-ime.js', import.meta.url), 'utf8');
const selector = 'textarea[aria-label="Terminal input"]';

class Input extends EventTarget {
    constructor(terminal = true) {
        super();
        this.terminal = terminal;
        this.attributes = {};
        this.value = '';
        this.isConnected = true;
    }
    matches(value) { return this.terminal && value === selector; }
    setAttribute(key, value) { this.attributes[key] = value; }
    setSelectionRange(start, end) { this.selection = [start, end]; }
}

function setup(inputs = []) {
    let observer;
    let count = 0;
    const context = {
        window: {}, WeakSet, queueMicrotask,
        document: {
            documentElement: {},
            querySelectorAll: value => inputs.filter(input => input.matches(value)),
        },
        MutationObserver: class {
            constructor(callback) { observer = callback; count++; }
            observe() {}
        },
    };
    runInNewContext(script, context);
    return {
        add: node => observer([{ addedNodes: [node] }]),
        repeat: () => { runInNewContext(script, context); return count; },
    };
}

test('sets terminal hints and sentinel without touching ordinary chat inputs', () => {
    const terminal = new Input();
    const chat = new Input(false);
    const harness = setup([terminal, chat]);
    assert.equal(terminal.attributes.inputmode, 'url');
    assert.equal(terminal.attributes.enterkeyhint, 'enter');
    assert.equal(terminal.value, ' ');
    assert.deepEqual(terminal.selection, [1, 1]);
    assert.deepEqual(chat.attributes, {});
    assert.equal(chat.value, '');
    assert.equal(harness.repeat(), 1);
});

test('configures asynchronously mounted tabs without resetting existing input', () => {
    const harness = setup();
    const terminal = new Input();
    harness.add(terminal);
    assert.equal(terminal.attributes.autocomplete, 'off');
    terminal.value = 'pending';
    harness.add(terminal);
    assert.equal(terminal.value, 'pending');
});

test('restores deletion sentinel after upstream handling but preserves composition', async () => {
    const terminal = new Input();
    setup([terminal]);
    terminal.dispatchEvent(new Event('beforeinput'));
    terminal.value = ''; // Upstream handles/prevents input, then clears the buffer.
    await Promise.resolve();
    assert.equal(terminal.value, ' ');
    terminal.dispatchEvent(new Event('compositionstart'));
    terminal.value = '中文';
    terminal.dispatchEvent(new Event('input'));
    await Promise.resolve();
    assert.equal(terminal.value, '中文');
    terminal.dispatchEvent(new Event('compositionend'));
    terminal.value = ''; // Upstream cleanup runs before the scheduled reset.
    await Promise.resolve();
    assert.equal(terminal.value, ' ');
    terminal.isConnected = false;
    terminal.value = '';
    terminal.dispatchEvent(new Event('keyup'));
    await Promise.resolve();
    assert.equal(terminal.value, '');
});
