const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('dashboard.html', 'utf8');
const code = html.slice(html.indexOf("        const FEAR_GREED_URL"), html.indexOf('        // Initial fetch'));
const elements = {};
for (const symbol of ['btc', 'eth']) for (const name of ['dial', 'value', 'label', 'updated', 'source']) {
  elements[`${symbol}-fg-${name}`] = {textContent: '', style: {setProperty() {}}, removeAttribute() {}};
}
const context = {document: {getElementById: id => elements[id]}, console: {error() {}},
  fetch: async () => { throw Error('offline'); }};
vm.createContext(context);
vm.runInContext(code, context);
const render = (entry) => context.updateFearGreedDial('btc', entry, new Date().toISOString());
render({value: 62, classification: 'Greed', sourcePublishedAt: '2026-08-20T01:00:08Z'});
assert.match(elements['btc-fg-label'].textContent, /Stale/i, 'old observations must not look current');
assert.match(elements['btc-fg-updated'].textContent, /2026/, 'source date must include year');
assert.match(elements['btc-fg-updated'].textContent, /20 Aug/, 'never use artifact fetch time');
render({value: 33, classification: 'Fear', sourcePublishedAt: new Date().toISOString(), sourceName: 'CFGI', source: 'https://cfgi.io/bitcoin-fear-greed-index/', status: 'ok'});
assert.equal(elements['btc-fg-label'].textContent, 'Fear');
assert.match(elements['btc-fg-source'].textContent, /CFGI.*1D/);
render({value: 33, classification: 'Fear', sourcePublishedAt: new Date().toISOString(), status: 'error'});
assert.match(elements['btc-fg-label'].textContent, /unavailable/i);
render({value: 33, classification: 'Fear'});
assert.match(elements['btc-fg-label'].textContent, /Stale/i, 'missing source date cannot be current');
render({value: NaN});
assert.equal(elements['btc-fg-value'].textContent, '--');
render(undefined);
assert.equal(elements['btc-fg-value'].textContent, '--');
(async () => {
  await context.fetchFearGreedData();
  for (const symbol of ['btc', 'eth']) assert.match(elements[`${symbol}-fg-label`].textContent, /unavailable/i);
  console.log('Fear & Greed rendering regressions passed');
})().catch(e => {console.error(e); process.exit(1);});
