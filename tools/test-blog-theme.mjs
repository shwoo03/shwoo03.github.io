import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../assets/js/theme.js', import.meta.url), 'utf8');
function load(saved, unavailable = false) {
  const events = {}, handlers = {}, label = {}, attributes = {};
  const root = { dataset: {} };
  const button = {
    hidden: true,
    setAttribute: (key, value) => attributes[key] = value,
    querySelector: () => label,
    addEventListener: (key, value) => handlers[key] = value
  };
  const store = {
    getItem: () => { if (unavailable) throw Error('blocked'); return saved; },
    setItem: (key, value) => { if (unavailable) throw Error('blocked'); saved = value; }
  };
  runInNewContext(source, {
    document: { documentElement: root, getElementById: () => button, addEventListener: (key, value) => events[key] = value },
    localStorage: store
  });
  const beforeReady = root.dataset.bsTheme;
  events.DOMContentLoaded();
  return { root, button, attributes, beforeReady, click: handlers.click, saved: () => saved };
}
const initial = load(null);
assert.equal(initial.beforeReady, 'light');
assert.equal(initial.button.hidden, false);
initial.click();
assert.equal(initial.root.dataset.bsTheme, 'dark');
assert.equal(initial.saved(), 'dark');
assert.equal(initial.attributes['aria-label'], '라이트 모드로 전환');
const nextPage = load(initial.saved());
assert.equal(nextPage.beforeReady, 'dark', 'Saved mode applies before the page becomes visible');
nextPage.click();
assert.equal(nextPage.saved(), 'light');
assert.equal(load('invalid').beforeReady, 'light');
const blocked = load(null, true);
blocked.click();
assert.equal(blocked.root.dataset.bsTheme, 'dark', 'Blocked storage must not disable the control');
console.log('Theme persistence, labels and unavailable storage checks passed.');
