# Super reference worked examples

`super.html` is a static information page, not a calculator or personalised sale-tax estimate.

## Model boundary

The Division 296 examples deliberately take two independent inputs:

- `B`: the relevant Division 296 reference TSB (30 June 2027 for FY2026–27; generally the larger opening/closing value thereafter).
- `E`: total member Division 296 earnings across interests after fund calculation, attribution and applicable statutory/CGT adjustments, but before threshold apportionment.

The three examples use E = $100,000 and B = $3m, $10m and $20m. Calculate the percentages above $3m and $10m, floor each at zero and round each percentage to two decimals. Additional tax is E multiplied by 15% of the first proportion plus 10% of the second. Expected liabilities: $0, $10,500, $17,750.

The displayed figures are additional member tax only. They do not infer cost bases, capital gains, investment returns, pension balances or ordinary fund tax from TSB. Do not reapply a CGT discount or transitional factor to E. Pension earnings are not automatically excluded.

For a future full sale-tax calculator, specify actual gains, fund type, pension/accumulation allocation, SMSF transitional election or APRA phase-in, expenses/losses, member attribution and reference TSB separately. Avoid reinstating a combined tax total based only on total balance.

## Sources and maintenance

The page links directly to current ATO guidance on reference balances, SMSF/APRA adjustments, personal contributions, pension rules and withdrawal/death-benefit rates, plus the 2026 amending Act (section 296-60). Review date: 16 October 2026. Check official guidance before updating annual thresholds or extending the model to another year; thresholds are not permanently fixed.

## Verification

Run `python3 tests/test_super_reference.py` and `git diff --check`.

Tests independently calculate the examples with Python Decimal, verify each row’s displayed earnings/proportions/liability, check the critical caveats and source links, and reject superseded model figures. No browser JavaScript is introduced.
