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
vm.runInContext(`${script}\nthis.exportsForTest = { calculateRealReturn, calc, scenarioCalc, defaultState, assetTypeOptions, linkablePropertyAssets, linkableAssets, suggestedAssetTypeForLiability, isUsualLiabilityAssetPair, incomeLines, addIncomeSource, setIncomeSource, removeIncomeSource, addExpenseCategory, setExpenseCategory, removeExpenseCategory, removeAsset, removeLiability };`, context);
const { calculateRealReturn, calc, scenarioCalc, defaultState, assetTypeOptions, linkablePropertyAssets, linkableAssets, suggestedAssetTypeForLiability, isUsualLiabilityAssetPair, incomeLines, addIncomeSource, setIncomeSource, removeIncomeSource, addExpenseCategory, setExpenseCategory, removeExpenseCategory, removeAsset, removeLiability } = context.exportsForTest;

assert.equal(calculateRealReturn(7, 2.5), (1.07 / 1.025 - 1) * 100);
assert.equal(calculateRealReturn(0, 2.5), (1 / 1.025 - 1) * 100);
assert.match(assetTypeOptions('smsf'), /<option value="smsf" selected>SMSF<\/option>/);
assert.deepEqual([...linkablePropertyAssets(defaultState.assets).map(asset => asset.id)].sort(), ['ip1', 'ppor']);
assert.equal(defaultState.debts.find(debt => debt.id === 'mortgage').name, 'PPOR loan');
assert.equal(defaultState.debts.find(debt => debt.id === 'otherloan').name, 'Credit card debt');
assert.ok(defaultState.assets.every(asset => typeof asset.annualReturn === 'number'));
assert.equal(linkableAssets(defaultState.assets).length, defaultState.assets.length);
assert.equal(suggestedAssetTypeForLiability('ppor_loan'), 'primary_residence');
assert.equal(suggestedAssetTypeForLiability('smsf_loan'), 'smsf');
assert.equal(isUsualLiabilityAssetPair('ppor_loan', 'primary_residence'), true);
assert.equal(isUsualLiabilityAssetPair('ppor_loan', 'investment_property'), false);
assert.deepEqual(JSON.parse(JSON.stringify(incomeLines(defaultState.income))), [{name:'Employment',monthly:17500},{name:'Rental income',monthly:4100},{name:'Distributions',monthly:1100}]);
const initialIncome = calc().income;
assert.equal(addIncomeSource('Side project'), 'Side project');
assert.equal(setIncomeSource('Side project', 'Consulting', 900), true);
assert.equal(calc().income, initialIncome + 900);
assert.equal(removeIncomeSource('Consulting'), true);
assert.equal(calc().income, initialIncome);

const result = calc();
const expectedMonthlyInterest = defaultState.debts.reduce((total, debt) => total + debt.balance * debt.annualInterestRate / 100 / 12, 0);
assert.equal(result.monthlyInterest, expectedMonthlyInterest);
assert.equal(result.totalExpenses, result.expenses + expectedMonthlyInterest);
assert.equal(result.assetEquity.find(asset => asset.id === 'ppor').equity, 2062000 - 1260000);
const fiAssets = defaultState.assets.filter(asset => asset.fi);
const expectedWeightedRealReturn = fiAssets.reduce(
  (total, asset) => total + asset.balance * calculateRealReturn(asset.annualReturn, defaultState.profile.inflationRate),
  0,
) / result.fi;
assert.ok(Math.abs(result.weightedRealReturn - expectedWeightedRealReturn) < 1e-10);

const currentPlan = scenarioCalc('current');
assert.ok(currentPlan.realReturn > 0);
assert.equal(currentPlan.realReturn, result.weightedRealReturn / 100);

const initialExpenses = calc().expenses;
assert.equal(addExpenseCategory('Pet insurance'), 'Pet insurance');
assert.equal(setExpenseCategory('Pet insurance', 'Pet care', 125), true);
assert.equal(calc().expenses, initialExpenses + 125);
assert.equal(removeExpenseCategory('Pet care'), true);
assert.equal(calc().expenses, initialExpenses);

const initialAssets = calc().assets;
assert.equal(removeAsset('cash'), true);
assert.equal(calc().assets, initialAssets - defaultState.assets.find(asset => asset.id === 'cash').balance);
const initialDebt = calc().debt;
assert.equal(removeLiability('loc'), true);
assert.equal(calc().debt, initialDebt - defaultState.debts.find(debt => debt.id === 'loc').balance);

console.log('Pathfire calculation tests: PASS');
