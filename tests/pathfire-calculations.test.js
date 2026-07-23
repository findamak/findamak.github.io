const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('projects/australian-fire-prototype/index.html', 'utf8');
const script = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'))
  .replace(/\bboot\(\);\s*$/, '');
const context = {
  console,
  Intl,
  Date,
  Math,
  JSON,
  localStorage: { getItem: () => null, setItem: () => {} },
};
vm.createContext(context);
vm.runInContext(`${script}\nthis.exportsForTest = { calculateRealReturn, calc, scenarioCalc, defaultState, assetTypeOptions };`, context);
const { calculateRealReturn, calc, scenarioCalc, defaultState, assetTypeOptions } = context.exportsForTest;

assert.equal(calculateRealReturn(7, 2.5), (1.07 / 1.025 - 1) * 100);
assert.equal(calculateRealReturn(0, 2.5), (1 / 1.025 - 1) * 100);
assert.match(assetTypeOptions('smsf'), /<option value="smsf" selected>SMSF<\/option>/);
assert.equal(defaultState.debts.find(debt => debt.id === 'mortgage').name, 'PPOR loan');
assert.equal(defaultState.debts.find(debt => debt.id === 'otherloan').name, 'Credit card debt');
assert.ok(defaultState.assets.every(asset => typeof asset.annualReturn === 'number'));

const result = calc();
const fiAssets = defaultState.assets.filter(asset => asset.fi);
const expectedWeightedRealReturn = fiAssets.reduce(
  (total, asset) => total + asset.balance * calculateRealReturn(asset.annualReturn, defaultState.profile.inflationRate),
  0,
) / result.fi;
assert.ok(Math.abs(result.weightedRealReturn - expectedWeightedRealReturn) < 1e-10);

const currentPlan = scenarioCalc('current');
assert.ok(currentPlan.realReturn > 0);
assert.equal(currentPlan.realReturn, result.weightedRealReturn / 100);

console.log('Pathfire calculation tests: PASS');
