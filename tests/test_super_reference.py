"""Regression checks for the static super reference; run with python3."""
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.examples = []
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr' and 'data-reference-tsb' in attrs:
            attrs['text'] = ''
            self.examples.append(attrs)
            self.current_example = attrs
        if tag == 'a':
            self.links.append(attrs.get('href', ''))

    def handle_data(self, data):
        current = getattr(self, 'current_example', None)
        if current is not None:
            current['text'] += data

    def handle_endtag(self, tag):
        if tag == 'tr':
            self.current_example = None

class SuperReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'super.html').read_text()
        cls.page = Page(cls.html)

    def test_division296_examples(self):
        self.assertEqual(len(self.page.examples), 3)
        for row, expected in zip(self.page.examples, ['0', '10500', '17750']):
            balance = Decimal(row['data-reference-tsb'])
            earnings = Decimal(row['data-earnings'])
            proportions = [
                max(Decimal(0), (balance - Decimal(t)) / balance * 100)
                .quantize(Decimal('.01'), rounding=ROUND_HALF_UP) / 100
                for t in ['3000000', '10000000']
            ]
            tax = earnings * (Decimal('.15') * proportions[0] + Decimal('.10') * proportions[1])
            self.assertEqual(tax, Decimal(expected))
            self.assertEqual(tax, Decimal(row['data-tax']))
            self.assertIn('$' + format(int(tax), ','), row['text'])
            self.assertIn('$' + format(int(earnings), ','), row['text'])
            for percentage in proportions:
                self.assertIn(format(percentage * 100, '.2f') + '%', row['text'])

    def test_no_old_sale_model(self):
        for obsolete in ['assuming the whole TSB is a realised capital gain', '$1.343m', '$3.91m', 'pending any later indexed update', 'latest ATO-published amount', 'Total tax paid']:
            self.assertNotIn(obsolete, self.html)

    def test_essential_qualifications(self):
        for wording in ['not subsequent investment growth', 'net exempt current pension income', '30 June 2027', 'greater of opening and closing', '30 June 2026 market value', '0.2, 0.4, 0.6 and 0.8', 'work test or exemption', 'Historical treatment', 'former spouse', 'may form part of the estate', '16 October 2026', 'existing bring-forward arrangement', 'These taxes apply to income and realised capital gains, subject to the relevant exemptions and adjustments—not to the super balance itself.', 'For Division 296, total super balance determines what proportion of the statutory earnings base is subject to additional tax.']:
            self.assertIn(wording, self.html)

    def test_separate_tax_tables(self):
        self.assertIn('<h2>Tax on super</h2>', self.html)
        self.assertIn('Ordinary fund tax: depends on the account phase', self.html)
        self.assertIn('Additional Division 296 tax: depends on total super balance', self.html)
        self.assertIn('Accumulation tax does not start at $2.1m or stop at $3m.', self.html)
        self.assertIn('not a tax-free balance band', self.html)
        self.assertIn('href="#division-296-modelling"', self.html)
        section = self.html.split('<h2>Tax on super</h2>')[1].split('</section>')[0]
        self.assertEqual(section.count('<table>'), 2)
        ordinary, additional = section.split('<table>')[1:]
        self.assertNotIn('proportion above $3.0m', ordinary)
        self.assertNotIn('<th>Long-term', additional)
        self.assertIn('30 June 2027', additional)

    def test_pension_sale_example(self):
        self.assertTrue('id="pension-sale-example"' in self.html, 'Missing pension sale example')
        section = self.html.split('id="pension-sale-example"')[1].split('</section>')[0]
        sale, original, reset = map(Decimal, ['1200000', '600000', '900000'])
        ordinary_gain = sale - original
        adjusted_gain = sale - reset
        earnings = adjusted_gain * Decimal(2) / Decimal(3)
        tax = earnings * Decimal('.70') * Decimal('.15')
        self.assertEqual(ordinary_gain, Decimal('600000'))
        self.assertEqual(adjusted_gain, Decimal('300000'))
        self.assertEqual(earnings, Decimal('200000'))
        self.assertEqual(tax, Decimal('21000'))
        for label, amount in [('ordinary-gain', ordinary_gain), ('div296-gain', adjusted_gain), ('div296-earnings', earnings), ('ordinary-tax', Decimal(0)), ('div296-tax', tax), ('combined-tax', tax)]:
            row = section.split('data-sale-step="' + label + '"')[1].split('</tr>')[0]
            self.assertTrue('$' + format(int(amount), ',') in row, label)
        for text in ['single-member SMSF', '30 June 2027', 'valid transitional CGT election', 'no other earnings', 'at least 12 months', 'not an extra tax on the $10m balance', 'not the large-APRA-fund phase-in']:
            self.assertTrue(text in section, text)

    def test_current_sources(self):
        for suffix in ['how-division-296-tax-is-calculated', 'about-division-296-tax-for-smsfs', 'about-division-296-tax-for-apra-funds', 'personal-super-contributions', 'superannuation-death-benefits']:
            self.assertTrue(any(h.endswith(suffix) for h in self.page.links), suffix)
        self.assertFalse(any('better-targeted-super-concessions-is-law' in h for h in self.page.links))

if __name__ == '__main__':
    unittest.main()
