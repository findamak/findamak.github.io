const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('projects/australian-fire-prototype/index.html', 'utf8');
const script = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'))
  .replace(/\bboot\(\);\s*$/, '');
const renderedElements = { cashflow: { innerHTML: '' }, dashboard: { innerHTML: '' }, checkin: { innerHTML: '' }, checkinBody: { innerHTML: '' }, headerTitle: { textContent: '' } };
const context = {
  console,
  Intl,
  Date,
  Math,
  JSON,
  document: {
    getElementById: id => renderedElements[id] || { innerHTML: '' },
    querySelectorAll: () => [],
  },
  window: { scrollTo: () => {} },
  localStorage: { getItem: () => null, setItem: () => {} },
};
vm.createContext(context);
vm.runInContext(`${script}\nthis.exportsForTest = { calculateRealReturn, calc, scenarioCalc, defaultState, assetTypeOptions, normaliseAssetType, liabilityTypeOptions, normaliseLiabilityType, linkablePropertyAssets, linkableAssets, suggestedAssetTypeForLiability, isUsualLiabilityAssetPair, incomeLines, cashIncomeLines, addIncomeSource, setIncomeSource, removeIncomeSource, addExpenseCategory, setExpenseCategory, removeExpenseCategory, removeAsset, removeLiability, renderCashflow, renderDashboard, shortMoney, openCheckinIncomeAndSpending };`, context);
const { calculateRealReturn, calc, scenarioCalc, defaultState, assetTypeOptions, normaliseAssetType, liabilityTypeOptions, normaliseLiabilityType, linkablePropertyAssets, linkableAssets, suggestedAssetTypeForLiability, isUsualLiabilityAssetPair, incomeLines, cashIncomeLines, addIncomeSource, setIncomeSource, removeIncomeSource, addExpenseCategory, setExpenseCategory, removeExpenseCategory, removeAsset, removeLiability, renderCashflow, renderDashboard, shortMoney, openCheckinIncomeAndSpending } = context.exportsForTest;

assert.equal(calculateRealReturn(7, 2.5), (1.07 / 1.025 - 1) * 100);
assert.equal(calculateRealReturn(0, 2.5), (1 / 1.025 - 1) * 100);
assert.match(assetTypeOptions('superannuation'), /<option value="superannuation" selected>Superannuation<\/option>/);
assert.doesNotMatch(assetTypeOptions('superannuation'), /value="super"|value="smsf"/);
assert.equal(normaliseAssetType('super'), 'superannuation');
assert.equal(normaliseAssetType('smsf'), 'superannuation');
assert.equal(normaliseAssetType('investment'), 'investment');
assert.deepEqual([...linkablePropertyAssets(defaultState.assets).map(asset => asset.id)].sort(), ['ip1', 'ppor']);
assert.equal(defaultState.debts.find(debt => debt.id === 'mortgage').name, 'PPOR loan');
assert.equal(defaultState.debts.find(debt => debt.id === 'mortgage').type, 'loan');
assert.equal(defaultState.debts.find(debt => debt.id === 'iploan').type, 'loan');
assert.equal(defaultState.debts.find(debt => debt.id === 'otherloan').name, 'Credit card debt');
assert.match(liabilityTypeOptions('loan'), /<option value="loan" selected>Loan<\/option>/);
assert.doesNotMatch(liabilityTypeOptions('loan'), /value="ppor_loan"|value="investment_property_loan"|value="margin_loan"|value="car_loan"|value="personal_loan"|value="smsf_loan"/);
['ppor_loan','investment_property_loan','margin_loan','car_loan','personal_loan','smsf_loan'].forEach(type => assert.equal(normaliseLiabilityType(type), 'loan'));
assert.equal(normaliseLiabilityType('credit_card'), 'credit_card');
assert.ok(defaultState.assets.every(asset => typeof asset.annualReturn === 'number'));
assert.equal(linkableAssets(defaultState.assets).length, defaultState.assets.length);
assert.equal(suggestedAssetTypeForLiability('loan'), '');
assert.equal(isUsualLiabilityAssetPair('loan', 'primary_residence'), true);
assert.equal(isUsualLiabilityAssetPair('loan', 'investment_property'), true);
assert.deepEqual(JSON.parse(JSON.stringify(incomeLines(defaultState.income))), [{name:'Employment',monthly:17500},{name:'Rental income',monthly:4100},{name:'Distributions',monthly:1100}]);
assert.deepEqual(JSON.parse(JSON.stringify(cashIncomeLines([
  {name:'Savings account',type:'cash',balance:12000,annualReturn:5},
  {name:'Zero-rate cash',type:'cash',balance:8000,annualReturn:0},
  {name:'Shares',type:'investment',balance:12000,annualReturn:5},
]))), [{name:'Estimated interest — Savings account',monthly:50}]);
const initialIncome = calc().income;
assert.equal(addIncomeSource('Side project'), 'Side project');
assert.equal(setIncomeSource('Side project', 'Consulting', 900), true);
assert.equal(calc().income, initialIncome + 900);
assert.equal(removeIncomeSource('Consulting'), true);
assert.equal(calc().income, initialIncome);

const result = calc();
assert.equal(result.net, result.assets - result.debt);
renderDashboard();
assert.match(renderedElements.dashboard.innerHTML, new RegExp(`<div class="metric-label">Net worth including PPOR<\\/div><div class="metric-value">${shortMoney(result.net).replace('$','\\$')}<\\/div>`));
assert.equal(result.income, result.manualIncome + result.cashIncome);
assert.ok(result.cashInterestLines.length > 0);
renderCashflow();
assert.ok(renderedElements.cashflow.innerHTML.includes('Estimated interest — Cash &amp; savings'));
assert.match(renderedElements.cashflow.innerHTML, /<h3>Income breakdown<\/h3>[\s\S]*onclick="openCheckinIncomeAndSpending\(\)">Update<\/button>[\s\S]*<span>Total income<\/span>/);
assert.match(renderedElements.cashflow.innerHTML, /<h3>Spending categories<\/h3>[\s\S]*onclick="openCheckinIncomeAndSpending\(\)">Update<\/button>/);
openCheckinIncomeAndSpending();
assert.match(renderedElements.checkinBody.innerHTML, /<h3>2\. Income & spending<\/h3>/);
assert.match(renderedElements.cashflow.innerHTML, /<h3>Spending categories<\/h3>[\s\S]*<span>Total spending<\/span><strong>\$12,500\/month<\/strong>[\s\S]*<h3>Automatic liability interest<\/h3>/);
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
