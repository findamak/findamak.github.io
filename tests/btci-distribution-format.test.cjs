const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../btci.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = {};
const context = { Intl, document: { getElementById(id) { return elements[id] ||= {}; } }, fetch() { return new Promise(() => {}); } };
vm.createContext(context);
vm.runInContext(script, context);
vm.runInContext(`renderDistributionTable({ distributions: [
  {date:'2026-11-01', etf:'BTCI', distribution:1.23456, close:42.12, annualized_distribution_pct:12},
  {date:'2026-11-01', etf:'BITO', distribution:0.5, close:12, annualized_distribution_pct:12}
] })`, context);
assert.match(elements.distributionTable.innerHTML, /<td>\$1\.2346<\/td>/);
assert.match(elements.distributionTable.innerHTML, /<td>\$0\.5000<\/td>/);
assert.match(elements.distributionTable.innerHTML, /<td>\$42\.12<\/td>/);
assert.match(elements.distributionTable.innerHTML, /<td>\$12\.00<\/td>/);
console.log('PASS: distributions have four decimals; ETF closes retain two.');
