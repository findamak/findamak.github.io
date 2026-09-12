# CGT illustration: boundaries and regression fixtures

Reviewed 13 September 2026. This is **not ATO-approved**, a lodgement calculator, a progressive income-tax assessment, or a verified implementation of final prescribed reform rules.

## Model

- Australian resident individual, one wholly taxable asset, positive unchanged cost base, positive gain, no losses/exemptions. Contract dates, not settlement dates.
- Reject holdings ending on/before the first calendar acquisition anniversary (acquisition and disposal days excluded), acquisitions on/before 21 September 1999, zero/negative nominal gains, zero cost base, negative CPI, and transition valuations outside cost-to-proceeds range or without a holding straddling 1 July 2027. Reject invalid calendar dates. These are conservative tool boundaries, not declarations that excluded cases have no tax treatment.
- Compound estimated transition value: `V = C * (S/C)^(preYears/totalYears)`. Constant compound growth is an illustrative assumption, not an observed valuation or verified ATO-prescribed method. No intermediate rounding.
- Calendar years: whole anniversaries + remaining UTC days / days to next anniversary. February 29 clamps to February 28 in non-leap years. Whole anniversary periods are exact integers, avoiding leap-day drift in official examples. This non-prescribed convention is separate from the eligibility test.
- Optional valuation replaces V only for straddling holdings. For post-transition purchases V=C; pre-transition sales allocate the whole gain to the discounted portion.
- Indexed base: `B = V * (1+CPI)^postYears`. Pre-taxable `(V-C)*0.5`; post-taxable `max(0,S-B)`. Zero floor does not create a capital loss.
- Tax sensitivity: pre-taxable × entered rate + post-taxable × max(entered rate,30%). Assumes minimum applies; no progressive brackets, other income, offsets, income-support exceptions, or Medicare calculation. Entered rate can contain a levy allowance for sensitivity only.
- Full-period discount is a hypothetical baseline for post-transition disposals, **not** a selectable lowest-tax legal option. No recommendation/ranking.
- Excludes new-build/affordable-housing concessions, main residences, foreign/changing residency, trusts/companies/super, partial disposals, changing or differently timed cost-base elements and other exemptions. Eligible disposal costs should not also be deducted from gross proceeds.

## Source fixtures

Official Budget PDF: https://budget.gov.au/content/factsheets/download/tax-explainers-negative-gearing-capital-gains-tax.pdf

- Jane (p7): 1 July 2022 cost $800,000; 1 July 2032 proceeds $1,600,000; transition 1 July 2027; 2.5% annual CPI and 47% sensitivity. Transition estimate $1,131,371; pre-taxable $165,685; post-taxable $319,958; total taxable $485,643; tax $228,252. Assertions allow $1 whole-dollar rounding tolerance, not bespoke formula adjustments.
- Michael (p6): transition value $500,000; proceeds $560,000 after two years at 2.5% CPI. Post-taxable $34,687.50 and post-tax $16,303.125 at 47%. The test supplies a synthetic $400,000 original cost solely to exercise the valuation UI; it does not claim the Budget specifies Michael's original cost. Its resulting $50,000 pre-taxable portion is added explicitly.

ATO notice and holding rules:
- https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/how-to-calculate-your-cgt
- https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount
- https://www.ato.gov.au/calculators-and-tools/capital-gains-tax-record-keeping-tool

The reviewed ATO notice says announced changes do not apply to Tax Time 2026. No claim is made that legislation does not exist; final prescribed reform calculations have not been verified.

## Run

`node --test tests/*.test.js`

The CGT tests execute the actual inline ES5 script through Node `vm`, using DOM element/event stubs (no mocked calculation results). Coverage includes Budget examples, visible reconciliation, warnings/source links, unsupported cases, invalid/stale results, anniversary/leap/fractional periods, minimum-rate allocation, zero-floor treatment and an absent-Intl fallback. Input/change handlers clear results before native browser validation can leave stale totals visible. Currency inputs accept cents.

Changes followed failing-test → implementation → passing-test slices for each correction, followed by supplementary boundary regressions and the existing Pathfire suite. Browser/device rendering is a separate parent review; ES5 syntax and missing-Intl operation do not certify every old iPad CSS/layout feature.
