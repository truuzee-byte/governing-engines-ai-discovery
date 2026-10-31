import json
from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from royalty_model import (calculate_product, quarter_statement, quarter_deadline,
                           quarter_period, PAYMENT_RECIPIENT, PAYMENT_CONTACT)
from validate_licensing import validate_contract_text

HERE = Path(__file__).resolve().parent


class LicensingRegressionTests(unittest.TestCase):
    def test_million_net_profit_owes_ten_thousand(self):
        self.assertEqual(calculate_product('1500000', '500000')['royalty'], Decimal('10000'))

    def test_hundred_thousand_net_profit_owes_thousand(self):
        self.assertEqual(calculate_product('125000', '25000')['royalty'], Decimal('1000'))

    def test_ten_thousand_net_profit_owes_hundred(self):
        self.assertEqual(calculate_product('11000', '1000')['royalty'], Decimal('100'))

    def test_zero_profit_owes_zero(self):
        self.assertEqual(calculate_product('1000', '1000')['royalty'], Decimal('0'))

    def test_no_contribution_fraction_parameter(self):
        with self.assertRaises(TypeError):
            calculate_product('1000000', '0', mode_contribution='0.1')
        with self.assertRaises(ValueError):
            quarter_statement([{'product_id': 'one', 'covered': True, 'revenue': '1000000',
                                'allowable_expenses': '0', 'feature_fraction': '0.1'}])

    def test_unrelated_revenue_and_losses_are_excluded(self):
        result = quarter_statement([
            {'product_id': 'covered', 'covered': True, 'revenue': '100000', 'allowable_expenses': '0'},
            {'product_id': 'unrelated-loss', 'covered': False, 'revenue': '0', 'allowable_expenses': '500000'},
            {'product_id': 'unrelated-profit', 'covered': False, 'revenue': '9000000', 'allowable_expenses': '0'}])
        self.assertEqual(set(result), {'covered'})
        self.assertEqual(result['covered']['royalty'], Decimal('1000'))

    def test_covered_products_do_not_cross_net_losses(self):
        result = quarter_statement([
            {'product_id': 'A', 'covered': True, 'revenue': '100000', 'allowable_expenses': '0'},
            {'product_id': 'B', 'covered': True, 'revenue': '0', 'allowable_expenses': '500000'}])
        self.assertEqual(result['A']['royalty'], Decimal('1000'))
        self.assertEqual(result['B']['closing_same_product_loss'], Decimal('500000'))

    def test_same_product_losses_carry_and_are_consumed_once(self):
        first = calculate_product('100', '300')
        second = calculate_product('150', '0', first['closing_same_product_loss'])
        third = calculate_product('100', '0', second['closing_same_product_loss'])
        self.assertEqual(first['royalty'], Decimal('0'))
        self.assertEqual(second['closing_same_product_loss'], Decimal('50'))
        self.assertEqual(third['royalty'], Decimal('0.50'))
        self.assertEqual(third['closing_same_product_loss'], Decimal('0'))

    def test_duplicate_party_product_quarter_not_charged_twice(self):
        p = {'product_id': 'one', 'covered': True, 'revenue': '100000', 'allowable_expenses': '0'}
        with self.assertRaises(ValueError):
            quarter_statement([p, p.copy()])

    def test_all_quarter_deadlines_and_next_year(self):
        self.assertEqual([quarter_deadline(2026, q) for q in range(1, 5)],
                         [date(2026, 4, 30), date(2026, 7, 30), date(2026, 10, 30), date(2027, 1, 30)])
        self.assertEqual(quarter_deadline(2027, 4), date(2028, 1, 30))

    def test_calendar_quarter_periods(self):
        self.assertEqual(quarter_period(2028, 1), (date(2028, 1, 1), date(2028, 3, 31)))
        self.assertEqual(quarter_period(2026, 2), (date(2026, 4, 1), date(2026, 6, 30)))
        self.assertEqual(quarter_period(2026, 3), (date(2026, 7, 1), date(2026, 9, 30)))
        self.assertEqual(quarter_period(2026, 4), (date(2026, 10, 1), date(2026, 12, 31)))

    def test_payment_recipient_and_coordination(self):
        schedule = json.loads((HERE / 'ACTIVATION_SCHEDULE.json').read_text(encoding='utf-8'))
        self.assertEqual(PAYMENT_RECIPIENT, 'Governing Engines LLC')
        self.assertEqual(PAYMENT_CONTACT, 'DeMarius J. Lawson')
        self.assertEqual(schedule['payment_recipient'], PAYMENT_RECIPIENT)
        self.assertTrue(schedule['contact_required_before_first_payment_deadline'])
        self.assertFalse(schedule['failure_to_contact_waives_or_extends_obligation'])
        self.assertIsNone(schedule['payment_instructions'])

    def test_schedule_matches_actual_calendar_deadlines(self):
        schedule = json.loads((HERE / 'ACTIVATION_SCHEDULE.json').read_text(encoding='utf-8'))
        for q in range(1, 5):
            row = schedule['quarterly_deadlines'][f'Q{q}']
            self.assertEqual(quarter_deadline(2026, q),
                             date(2026 + row['due_year_offset'], row['due_month'], row['due_day']))

    def test_no_future_updates_or_support_and_no_false_activation(self):
        s = json.loads((HERE / 'ACTIVATION_SCHEDULE.json').read_text(encoding='utf-8'))
        for k in ('future_versions_entitled', 'private_code_entitled', 'future_learning_entitled',
                  'updates_patches_support_maintenance_assistance_promised', 'continued_development_obligation',
                  'license_activation_approved', 'company_equity_granted'):
            self.assertFalse(s[k])
        self.assertIsNone(s['effective_date'])
        self.assertIsNone(s['acceptance_evidence'])

    def test_invalid_accounting_and_quarters_rejected(self):
        for revenue, expenses, loss in [('NaN', '0', '0'), ('1', '-1', '0'), ('1', '0', '-1')]:
            with self.assertRaises(ValueError):
                calculate_product(revenue, expenses, loss)
        with self.assertRaises(ValueError):
            quarter_deadline(2026, 0)

    def test_contract_regressions_cannot_silently_remove_core_conditions(self):
        text = (HERE.parent / 'MODE_SOURCE_LICENSE.md').read_text(encoding='utf-8')
        validate_contract_text(text)
        mutations = [
            text.replace("exactly 1% of each Covered Commercial Product's total net profit", 'a MODE contribution fraction of profit'),
            text.replace('AS IS. NO UPDATES PROMISED.', 'Updates are included.'),
            text.replace('All royalty payments are payable to Governing Engines LLC', 'Pay any recipient'),
            text + '\nAttributable Revenue is the estimated MODE code-value fraction.',
        ]
        for changed in mutations:
            with self.subTest(change=mutations.index(changed)):
                with self.assertRaises(AssertionError):
                    validate_contract_text(changed)


if __name__ == '__main__':
    unittest.main()
