# Super reference worked examples

`super.html` is a static information page, not a calculator or personalised sale-tax estimate.

## Model boundary

The Division 296 examples deliberately take two independent inputs:

- `B`: the relevant Division 296 reference TSB (30 June 2027 for FY2026–27; generally the larger opening/closing value thereafter).
- `E`: total member Division 296 earnings across interests after fund calculation, attribution and applicable statutory/CGT adjustments, but before threshold apportionment.

The three examples use E = $100,000 and B = $3m, $10m and $20m. Calculate the percentages above $3m and $10m, floor each at zero and round each percentage to two decimals. Additional tax is E multiplied by 15% of the first proportion plus 10% of the second. Expected liabilities: $0, $10,500, $17,750.

The displayed figures are additional member tax only. They do not infer cost bases, capital gains, investment returns, pension balances or ordinary fund tax from TSB. Do not reapply a CGT discount or transitional factor to E. Pension earnings are not automatically excluded.

For a future full sale-tax calculator, specify actual gains, fund type, pension/accumulation allocation, SMSF transitional election or APRA phase-in, expenses/losses, member attribution and reference TSB separately. Avoid reinstating a combined tax total based only on total balance.

## Separate pension sale example

`#pension-sale-example` derives earnings for a hypothetical single-member mixed SMSF: closing reference TSB $10m consists of $2.1m pension and $7.9m accumulation. Separately assume the properly calculated annual exemption is 21%, with 79% taxable; do not infer the annual actuarial exemption from closing balances alone. The pooled asset supports both interests.

Sale proceeds $1,200,000 less original cost base $600,000 gives a $600,000 gain. Ordinary fund CGT is $600,000 × 79% × 10% = $47,400. The 10% effective rate includes the one-third discount (equivalently, gain × 2/3 × 79% × 15%); never discount again before applying 10%.

A valid transitional election supplies a $900,000 Division 296 cost base; the resulting $300,000 gain is discounted by one-third to $200,000. With no other adjustments and all earnings attributed to this member, reference TSB $10m gives 70% × 15% × $200,000 = $21,000 additional tax. The earnings base includes both pension and accumulation, so it is not multiplied by 79%. No above-$10m charge applies at exactly $10m. Combined tax is $68,400, or 11.4% of the original $600,000 gain (7.9% ordinary tax plus 3.5% Division 296). This is not a universal rate or tax on sale proceeds.

The closing reference TSB is independently specified after transactions, not derived from the sale. Assumptions cover ownership/holding period, election, pension compliance, actuarial requirements, absence of other earnings/losses/contributions/expenses, and absence of individual exclusions. This is not the large-APRA phase-in. Tests independently derive tax proportions and outputs and check the displayed rows.

## Sources and maintenance

The page links directly to current ATO guidance on reference balances, SMSF/APRA adjustments, personal contributions, pension rules and withdrawal/death-benefit rates, plus the 2026 amending Act (section 296-60). Review date: 16 October 2026. Check official guidance before updating annual thresholds or extending the model to another year; thresholds are not permanently fixed.

## Verification

Run `python3 tests/test_super_reference.py` and `git diff --check`.

Tests independently calculate the examples with Python Decimal, verify each row’s displayed earnings/proportions/liability, check the critical caveats and source links, and reject superseded model figures. No browser JavaScript is introduced.
