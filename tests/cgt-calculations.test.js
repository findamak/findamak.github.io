'use strict';
var assert = require('node:assert/strict');
var test = require('node:test');
var fs = require('node:fs');
var vm = require('node:vm');
var html = fs.readFileSync(require('node:path').join(__dirname, '../cgt.html'), 'utf8');
var script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
function calculator(overrides, noIntl) {
  var elements = {};
  html.replace(/id="([^"]+)"/g, function (_, id) {
    elements[id] = { value: '', textContent: '', style: {}, addEventListener: function (name, fn) { this[name] = fn; } };
  });
  vm.runInNewContext(script, { document: { getElementById: function (id) { assert.ok(elements[id], 'real element ' + id); return elements[id]; } }, Intl: noIntl ? undefined : Intl });
  var values = { buyDate: '2022-07-01', sellDate: '2032-07-01', costBasis: '800000', saleAmount: '1600000', transitionMarketValue: '', marginalTaxRate: '47', averageCpi: '0' };
  Object.assign(values, overrides);
  Object.keys(values).forEach(function (id) { elements[id].value = values[id]; });
  elements.cgtForm.submit({ preventDefault: function () {} });
  return elements;
}
test('Jane Budget example compounds CPI over five calendar years', function () {
  var e = calculator({ averageCpi: '2.5' });
  close(dollars(e.newTaxableGain), 485643);
  close(dollars(e.newTax), 228252);
  close(dollars(e.oldTax), 188000);
});
test('Michael Budget post-transition example compounds CPI in valuation model', function () {
  var e = calculator({ costBasis: '400000', saleAmount: '560000', sellDate: '2029-07-01', transitionMarketValue: '500000', averageCpi: '2.5' });
  close(dollars(e.marketTaxableGain), 50000 + 34687.5);
  close(dollars(e.marketTax), 23500 + 16303.125);
});
[
  ['zero cost base', { costBasis: '0' }, /positive cost base/i],
  ['nonexistent calendar date', { buyDate: '2023-02-29' }, /valid.*dates/i],
  ['numeric overflow', { costBasis: '1e-308', saleAmount: '1e308' }, /numeric range/i],
  ['nominal loss', { saleAmount: '700000' }, /reduced cost base|loss rules/i],
  ['zero gain', { saleAmount: '800000' }, /reduced cost base|loss rules/i],
  ['valuation loss before transition', { transitionMarketValue: '700000' }, /between cost base and sale proceeds/i],
  ['valuation loss after transition', { transitionMarketValue: '1700000' }, /between cost base and sale proceeds/i],
  ['pre-1999 asset', { buyDate: '1999-09-20' }, /1999/i],
  ['leap-year anniversary not eligible', { buyDate: '2023-07-01', sellDate: '2024-07-01' }, /12 months/i],
  ['short holding', { buyDate: '2027-07-01', sellDate: '2028-06-30' }, /12 months/i],
  ['valuation without straddling transition', { buyDate: '2027-07-01', transitionMarketValue: '900000' }, /straddl/i],
  ['valuation after sale', { sellDate: '2026-07-02', transitionMarketValue: '900000' }, /straddl/i],
  ['negative CPI not supported', { averageCpi: '-1' }, /negative CPI|0%/i]
].forEach(function (fixture) {
  test('scope rejects ' + fixture[0] + ' and clears stale output', function () {
    var e = calculator();
    Object.keys(fixture[1]).forEach(function (id) { e[id].value = fixture[1][id]; });
    e.cgtForm.submit();
    assert.match(e.errorBox.textContent, fixture[2]);
    assert.equal(e.newTax.textContent, '--');
    assert.equal(e.oldTax.textContent, '--');
  });
});
[
  ['compound CPI base', { sellDate: '9999-07-01', averageCpi: '20' }],
  ['post-transition CPI base', { buyDate: '2027-07-01', sellDate: '9999-07-01', averageCpi: '20' }],
  ['valuation indexed-base sum', { sellDate: '2028-07-01', costBasis: '1e307', saleAmount: '1.7e308', transitionMarketValue: '1.6e308', averageCpi: '20' }]
].forEach(function (fixture) {
  test('numeric range rejects overflowing ' + fixture[0] + ' before rendering', function () {
    var e = calculator({ transitionMarketValue: '1100000' });
    assert.notEqual(e.marketTax.textContent, '--');
    e.transitionMarketValue.value = '';
    Object.keys(fixture[1]).forEach(function (id) { e[id].value = fixture[1][id]; });
    e.cgtForm.submit();
    assert.equal(e.errorBox.textContent, 'Inputs exceed the supported numeric range.');
    assert.equal(e.errorBox.style.display, 'block');
    ['lowerMethod', 'taxDifference', 'nominalGain', 'oldCostBase', 'oldTaxableGain', 'oldTax', 'oldEffectiveRate', 'newCostBase', 'newTaxableGain', 'newTax', 'newEffectiveRate', 'marketTaxableGain', 'marketTax', 'marketEffectiveRate', 'newComponents', 'marketComponents'].forEach(function (id) {
      assert.equal(e[id].textContent, '--', id + ' must be cleared');
    });
    assert.equal(e.marketTreatment.textContent, 'Enter 1 July 2027 value to calculate');
  });
});
test('results reconcile Jane components and identify a comparison, not a tax election', function () {
  var e = calculator({ averageCpi: '2.5', transitionMarketValue: '1131371' });
  assert.ok(e.newComponents, 'visible compound components');
  assert.match(e.newComponents.textContent, /1,131,371/);
  assert.match(e.newComponents.textContent, /331,371/);
  assert.match(e.newComponents.textContent, /165,685/);
  assert.match(e.newComponents.textContent, /1,280,042/);
  assert.match(e.newComponents.textContent, /319,958/);
  assert.match(e.marketComponents.textContent, /1,131,371/);
  assert.equal(e.lowerMethod.textContent, 'Comparison only — not a tax election');
  assert.match(html, /Not ATO-approved/);
  assert.match(html, /not for lodgement/i);
  assert.match(html, /Illustrative announced reform/);
  assert.match(html, /13 September 2026/);
  assert.match(html, /hypothetical baseline/i);
  assert.match(html, /not verified the final prescribed/i);
  assert.match(html, /contract dates/i);
  assert.match(html, /no Medicare levy is calculated/i);
  assert.match(html, /income support/i);
  assert.match(html, /new-build/i);
  assert.match(html, /affordable housing/i);
  assert.match(html, /https:\/\/www.ato.gov.au\/individuals-and-families\/investments-and-assets\/capital-gains-tax/);
  assert.match(html, /https:\/\/budget.gov.au\//);
  assert.doesNotMatch(html, /Lower tax method|New model|new rules|Old model|by holding days/);
});
function dollars(element) { return Number(element.textContent.replace(/[^0-9.-]/g, '')); }
test('older iPads without Intl still calculate formatted values', function () {
  var e = calculator({ averageCpi: '2.5' }, true);
  assert.equal(e.newTax.textContent, '$228,252');
  assert.equal(e.oldEffectiveRate.textContent, '23.5%');
});
test('currency inputs accept cents and the official ATO tool is linked', function () {
  ['costBasis', 'saleAmount', 'transitionMarketValue'].forEach(function (id) {
    assert.match(html.match(new RegExp('<input id="' + id + '"[^>]+>'))[0], /step="(?:0.01|any)"/);
  });
  assert.match(html, /https:\/\/www.ato.gov.au\/calculators-and-tools\/capital-gains-tax-record-keeping-tool/);
});
test('editing any input clears results before native validation can block submission', function () {
  ['input', 'change'].forEach(function (event) {
    var e = calculator();
    e.costBasis.value = '';
    assert.equal(typeof e.costBasis[event], 'function');
    e.costBasis[event]();
    assert.equal(e.newTax.textContent, '--');
    assert.equal(e.newComponents.textContent, '--');
  });
});
test('sources point directly to the verified discount page and Budget examples', function () {
  assert.match(html, /href="https:\/\/www.ato.gov.au\/individuals-and-families\/investments-and-assets\/capital-gains-tax\/cgt-discount"/);
  assert.match(html, /href="https:\/\/budget.gov.au\/content\/factsheets\/download\/tax-explainers-negative-gearing-capital-gains-tax.pdf"/);
});
test('day after anniversary is accepted across leap years', function () {
  ['2023-07-01', '2024-02-29'].forEach(function (buyDate, i) {
    var e = calculator({ buyDate: buyDate, sellDate: i ? '2025-03-01' : '2024-07-02' });
    assert.equal(e.errorBox.textContent, '');
    assert.equal(e.oldTax.textContent, '$188,000');
    assert.equal(e.newTax.textContent, e.oldTax.textContent);
  });
});
test('post-transition purchase uses only indexed base and assumed minimum rate', function () {
  var e = calculator({ buyDate: '2027-07-01', costBasis: '100', saleAmount: '125', marginalTaxRate: '10', averageCpi: '2.5' });
  assert.equal(e.errorBox.textContent, '');
  close(dollars(e.newTaxableGain), 125 - 100 * Math.pow(1.025, 5));
  close(dollars(e.newTax), (125 - 100 * Math.pow(1.025, 5)) * 0.30);
});
test('minimum rate applies to post gain only, not the discounted pre gain', function () {
  var e = calculator({ marginalTaxRate: '10' });
  var v = Math.sqrt(800000 * 1600000);
  close(dollars(e.newTax), (v - 800000) * 0.5 * 0.10 + (1600000 - v) * 0.30);
});
test('CPI does not create a modelled capital loss', function () {
  var e = calculator({ buyDate: '2027-07-01', saleAmount: '810000', averageCpi: '20' });
  assert.equal(e.errorBox.textContent, '');
  assert.equal(e.newTaxableGain.textContent, '$0');
});
test('fractional post year uses remaining days over the next anniversary year', function () {
  var e = calculator({ buyDate: '2027-07-01', sellDate: '2028-10-01', averageCpi: '2.5' });
  var fraction = (Date.UTC(2028, 9, 1) - Date.UTC(2028, 6, 1)) / (Date.UTC(2029, 6, 1) - Date.UTC(2028, 6, 1));
  close(dollars(e.newTaxableGain), 1600000 - 800000 * Math.pow(1.025, 1 + fraction));
});
function close(actual, expected) { assert.ok(Math.abs(actual - expected) <= 1, actual + ' expected within $1 of ' + expected); }
test('compound growth estimates the transition value at the calendar halfway anniversary', function () {
  var e = calculator();
  assert.equal(e.errorBox.textContent, '');
  close(dollars(e.newTaxableGain), (Math.sqrt(800000 * 1600000) - 800000) * 0.5 + 1600000 - Math.sqrt(800000 * 1600000));
});
