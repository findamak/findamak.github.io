const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('btci.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = {};
const context = {Intl, Date, Number, Math, document: { getElementById(id) {
  return elements[id] ||= {classList: {add() {}}};
}}, fetch: () => new Promise(() => {})};
vm.createContext(context);
vm.runInContext(script, context);
const data = JSON.parse(fs.readFileSync('data/btci.json'));
context.renderSummary({...data, aum: {btci: {usd: 1085389587}, bito: {usd: 1161052307}}});
assert.equal(elements.btciAum.textContent, '$1,085,389,587');
assert.equal(elements.bitoAum.textContent, '$1,161,052,307');
context.renderSummary({...data, aum: undefined});
assert.equal(elements.btciAum.textContent, 'Unavailable');
assert.equal(elements.bitoAum.textContent, 'Unavailable');
console.log('AUM summary rendering and missing-data tests passed');
