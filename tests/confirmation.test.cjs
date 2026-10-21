const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const source = readFileSync(resolve(__dirname, '../assets/mwc-ads-confirmation-v1.js'), 'utf8');

function run(cookie) {
  const scripts = [];
  const warnings = [];
  const window = { location: { href: 'https://tickets.mautic.org/Mautic/mwc2026/order/PRIVATE-ACCESS-SECRET/' } };
  const document = {
    cookie,
    currentScript: { dataset: { value: '123.45', currency: 'GBP', transactionId: 'Mautic-mwc2026-ABCDE' } },
    head: { appendChild(script) { scripts.push(script); } },
    createElement(tag) { assert.equal(tag, 'script'); return {}; }
  };
  vm.runInNewContext(source, { window, document, console: { warn(...args) { warnings.push(args); } } });
  const commands = Array.from(window.dataLayer || [], command => Array.from(command));
  return { scripts, warnings, commands };
}
const cookie = value => 'session=unrelated; mwc_consent=' + encodeURIComponent(JSON.stringify(value));

test('no tracking without affirmative Google Ads consent', () => {
  for (const value of ['', cookie({ 'google-ads': false }), cookie({ 'mautic-analytics': true }), cookie({ 'google-ads': 'true' }), cookie(null)]) {
    const result = run(value);
    assert.equal(result.scripts.length, 0);
    assert.equal(result.commands.length, 0);
  }
});

test('malformed consent fails closed with a diagnostic', () => {
  const result = run('mwc_consent=%not-json');
  assert.equal(result.scripts.length, 0);
  assert.equal(result.warnings.length, 1);
});

test('consented confirmation queues one conversion with order value and stable ID', () => {
  const consent = cookie({ 'google-ads': true });
  const result = run(consent);
  assert.equal(result.scripts.length, 1);
  assert.equal(result.scripts[0].src, 'https://www.googletagmanager.com/gtag/js?id=AW-960227364');
  assert.equal(result.scripts[0].referrerPolicy, 'no-referrer');
  const event = result.commands.find(c => c[0] === 'event');
  assert.equal(event[1], 'conversion');
  assert.equal(event[2].send_to, 'AW-960227364/-8CLCIO2obwCEKTQ78kD');
  assert.equal(event[2].value, 123.45);
  assert.equal(event[2].currency, 'GBP');
  assert.equal(event[2].transaction_id, 'Mautic-mwc2026-ABCDE');
  const repeated = run(consent).commands.find(c => c[0] === 'event');
  assert.equal(repeated[2].transaction_id, event[2].transaction_id); // Google's transaction-ID deduplication.
});

test('measurement fields contain no private URL and disable personalisation', () => {
  const result = run(cookie({ 'google-ads': true }));
  assert.doesNotMatch(JSON.stringify(result.commands), /PRIVATE-ACCESS-SECRET/);
  const set = result.commands.find(c => c[0] === 'set')[1];
  assert.equal(set.page_location, 'https://tickets.mautic.org/Mautic/mwc2026/');
  assert.equal(set.page_referrer, '');
  const consent = result.commands.find(c => c[0] === 'consent')[2];
  assert.equal(consent.ad_personalization, 'denied');
  assert.equal(consent.analytics_storage, 'denied');
  assert.equal(result.commands.find(c => c[0] === 'config')[2].send_page_view, false);
});
