const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('projects/australian-fire-prototype/index.html', 'utf8');
const script = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'))
  .replace(/\bboot\(\);\s*$/, '');
const renderedElements = { cashflow: { innerHTML: '' }, dashboard: { innerHTML: '' }, checkin: { innerHTML: '' }, checkinModal: { innerHTML: '' }, settings: { innerHTML: '' }, plans: { innerHTML: '' }, sheet: { innerHTML: '' }, modal: { innerHTML: '', classList: { add: () => {}, remove: () => {} } }, checkinBody: { innerHTML: '' }, headerTitle: { textContent: '' } };
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
vm.runInContext(`${script}\nthis.exportsForTest = { calculateRealReturn, calc, scenarioCalc, defaultState, state, assetTypeOptions, normaliseAssetType, liabilityTypeOptions, normaliseLiabilityType, linkablePropertyAssets, linkableAssets, suggestedAssetTypeForLiability, isUsualLiabilityAssetPair, incomeLines, cashIncomeLines, addIncomeSource, setIncomeSource, removeIncomeSource, addExpenseCategory, setExpenseCategory, removeExpenseCategory, removeAsset, removeLiability, makeCheckinSnapshot, checkinSnapshotForEditing, checkinCashflowMetrics, dashboardSnapshotMetrics, sortCheckins, updateHistoricalCheckin, deleteHistoricalCheckin, renderCashflow, renderDashboard, renderCheckin, renderSettings, shortMoney, openCheckinIncomeAndSpending, openCurrentCheckin, openScenarioEditor };`, context);
const { calculateRealReturn, calc, scenarioCalc, defaultState, state, assetTypeOptions, normaliseAssetType, liabilityTypeOptions, normaliseLiabilityType, linkablePropertyAssets, linkableAssets, suggestedAssetTypeForLiability, isUsualLiabilityAssetPair, incomeLines, cashIncomeLines, addIncomeSource, setIncomeSource, removeIncomeSource, addExpenseCategory, setExpenseCategory, removeExpenseCategory, removeAsset, removeLiability, makeCheckinSnapshot, checkinSnapshotForEditing, checkinCashflowMetrics, dashboardSnapshotMetrics, sortCheckins, updateHistoricalCheckin, deleteHistoricalCheckin, renderCashflow, renderDashboard, renderCheckin, renderSettings, shortMoney, openCheckinIncomeAndSpending, openCurrentCheckin, openScenarioEditor } = context.exportsForTest;

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
const checkinSnapshot = makeCheckinSnapshot({month:'January',year:2025,note:'Reconciled month'}, defaultState);
assert.equal(checkinSnapshot.label, 'January 2025');
assert.equal(checkinSnapshot.assets.length, defaultState.assets.length);
assert.equal(checkinSnapshot.debts.length, defaultState.debts.length);
assert.equal(checkinSnapshot.netExPpor, checkinSnapshot.net - defaultState.assets.find(asset=>asset.id==='ppor').balance + defaultState.debts.filter(debt=>debt.linked==='ppor').reduce((total,debt)=>total+debt.balance,0));
assert.deepEqual(JSON.parse(JSON.stringify(checkinSnapshot.income)), JSON.parse(JSON.stringify(defaultState.income)));
assert.deepEqual(JSON.parse(JSON.stringify(checkinSnapshot.expenses)), JSON.parse(JSON.stringify(defaultState.expenses)));
const historicCashflow=checkinCashflowMetrics(checkinSnapshot);
assert.equal(historicCashflow.spending*12, checkinSnapshot.spend);
assert.equal(historicCashflow.surplus, historicCashflow.income-historicCashflow.spending);
assert.ok(historicCashflow.income > Object.values(defaultState.income).reduce((total,value)=>total+value,0));
checkinSnapshot.assets[0].balance=1;
assert.notEqual(defaultState.assets[0].balance, 1);
const editableLegacyCheckin=checkinSnapshotForEditing({label:'February',net:123,fi:100,spend:80,note:'Legacy'}, defaultState);
assert.equal(editableLegacyCheckin.label, 'February 2026');
assert.equal(editableLegacyCheckin.assets.length, defaultState.assets.length);
assert.equal(editableLegacyCheckin.debts.length, defaultState.debts.length);
assert.deepEqual(JSON.parse(JSON.stringify(editableLegacyCheckin.income)), JSON.parse(JSON.stringify(defaultState.income)));
assert.deepEqual(JSON.parse(JSON.stringify(sortCheckins([{label:'December 2024',month:'December',year:2024},{label:'January 2026',month:'January',year:2026},{label:'November 2025',month:'November',year:2025}]).map(checkin=>checkin.label))), ['January 2026','November 2025','December 2024']);
const snapshotDashboard=dashboardSnapshotMetrics([{month:'January',year:2026,assets:[{id:'cash',balance:200,fi:true,accessible:true},{id:'super',balance:250,fi:true,accessible:false},{id:'ppor',type:'primary_residence',balance:300,fi:false,accessible:false}],debts:[{linked:'ppor',balance:100},{balance:50}]}], {net:999,netExPpor:998,accessible:997,superBal:996});
assert.deepEqual(JSON.parse(JSON.stringify(snapshotDashboard)), {net:600,netExPpor:400,accessible:200,superBal:250});
assert.deepEqual(JSON.parse(JSON.stringify(dashboardSnapshotMetrics([{month:'July',year:2026,net:2300000}], {net:999,netExPpor:998,accessible:997,superBal:996}))), {net:999,netExPpor:998,accessible:997,superBal:996});
const revisedCheckin = updateHistoricalCheckin(0, {...checkinSnapshot,month:'January',year:2024,note:'Corrected after reconciliation.'});
assert.equal(revisedCheckin.label, 'January 2024');
assert.equal(revisedCheckin.year, 2024);
assert.equal(revisedCheckin.assets[0].balance, 1);
assert.equal(revisedCheckin.note, 'Corrected after reconciliation.');
assert.equal(updateHistoricalCheckin(-1, {month:'Invalid'}), false);
assert.equal(deleteHistoricalCheckin(-1), false);
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
renderDashboard();
assert.match(renderedElements.dashboard.innerHTML, /Complete this month’s check-in/);
assert.doesNotMatch(renderedElements.dashboard.innerHTML, /Complete January 2026 check-in/);
renderSettings();
assert.match(renderedElements.settings.innerHTML, /starting balances.*kick off your FI plan[\s\S]*monthly Check-ins/i);
openCurrentCheckin();
assert.match(renderedElements.checkinModal.innerHTML, /<h2>Current monthly check-in<\/h2>[\s\S]*<label>Check-in period<\/label>[\s\S]*id="checkinMonth"[\s\S]*id="checkinYear"/);
renderCashflow();
assert.ok(renderedElements.cashflow.innerHTML.includes('Estimated interest — Cash &amp; savings'));
assert.match(renderedElements.cashflow.innerHTML, /<h3>Income breakdown<\/h3>[\s\S]*onclick="openCheckinIncomeAndSpending\(\)">Update<\/button>[\s\S]*<span>Total income<\/span>/);
assert.match(renderedElements.cashflow.innerHTML, /<h3>Spending categories<\/h3>[\s\S]*onclick="openCheckinIncomeAndSpending\(\)">Update<\/button>/);
assert.match(renderedElements.cashflow.innerHTML, /<div class="section-title">Cash-flow history<\/div>[\s\S]*January 2024[\s\S]*Income[\s\S]*Spending[\s\S]*[Ss]urplus/);
renderCheckin();
assert.match(renderedElements.checkin.innerHTML, /<h2>Check-ins<\/h2>/);
assert.match(renderedElements.checkin.innerHTML, /<div class="section-title">Previous check-ins<\/div>/);
assert.match(renderedElements.checkin.innerHTML, /<div class="metric-label">Net worth excluding PPOR<\/div>[\s\S]*<div class="metric-label">FI portfolio<\/div>[\s\S]*<span>Net worth<\/span>/);
assert.match(renderedElements.checkin.innerHTML, /January 2024[\s\S]*onclick="openHistoricalCheckin\(0\)">Update<\/button>[\s\S]*onclick="deleteHistoricalCheckinUI\(0\)">Delete<\/button>/);
assert.match(renderedElements.checkin.innerHTML, /onclick="openCurrentCheckin\(\)">Complete check-in for this month<\/button>/);
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

state.profile.retirementSpend = 100000;
state.profile.retirementAge = 55;
state.scenarios.current.spend = 1;
state.scenarios.current.workEndAge = 41;
state.scenarios.current.flexIncome = 20000;
const settingsDrivenPlan = scenarioCalc('current');
assert.equal(settingsDrivenPlan.spend, 100000);
assert.equal(settingsDrivenPlan.workEndAge, 55);
assert.equal(settingsDrivenPlan.full, 80000 / (state.profile.withdrawalRate / 100));
assert.equal(settingsDrivenPlan.years, 15);
assert.equal(settingsDrivenPlan.bridge, 80000 * (state.profile.preservationAge - 55));
openScenarioEditor('current');
assert.match(renderedElements.sheet.innerHTML, /Annual flexible-work income/);
assert.doesNotMatch(renderedElements.sheet.innerHTML, /Annual retirement spending|Age to leave full-time work|id="sspend"|id="sage"/);

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
while(deleteHistoricalCheckin(0)){}
assert.doesNotThrow(() => renderDashboard());

console.log('Pathfire calculation tests: PASS');
