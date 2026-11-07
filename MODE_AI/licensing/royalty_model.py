"""Illustrative contract accounting tests only; not a MODE runtime component.

Inputs must already be actual covered-product accounts. This model does not
determine legal coverage, approve expenses, or estimate MODE contribution.
"""
import calendar
from datetime import date
from decimal import Decimal

RATE = Decimal('0.01')
PAYMENT_RECIPIENT = 'Governing Engines LLC'
PAYMENT_CONTACT = 'DeMarius J. Lawson'
DEADLINES = {1: (4, 30, 0), 2: (7, 30, 0), 3: (10, 30, 0), 4: (1, 30, 1)}


def amount(value):
    if isinstance(value, (float, bool)):
        raise ValueError('Use finite decimal product accounts, not float estimates')
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('Non-finite amount')
    return result


def calculate_product(revenue, allowable_expenses, prior_same_product_loss='0'):
    revenue, expenses, loss = map(amount, (revenue, allowable_expenses, prior_same_product_loss))
    if expenses < 0 or loss < 0:
        raise ValueError('Expense/loss balances cannot be negative')
    operating_profit = revenue - expenses
    royalty_bearing_total_profit = max(Decimal('0'), operating_profit - loss)
    return {'operating_net_profit': operating_profit,
            'royalty_bearing_total_net_profit': royalty_bearing_total_profit,
            'royalty': RATE * royalty_bearing_total_profit,
            'closing_same_product_loss': max(Decimal('0'), loss - operating_profit)}


def quarter_statement(products):
    """One party/quarter's separately identified product accounts, never netted."""
    result = {}; seen = set()
    for product in products:
        identity = product['product_id']
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError('Duplicate or invalid product profit entry')
        seen.add(identity)
        if type(product['covered']) is not bool:
            raise ValueError('Coverage must be explicitly identified, not inferred')
        if not product['covered']:
            continue
        allowed = {'product_id', 'covered', 'revenue', 'allowable_expenses', 'prior_same_product_loss'}
        if set(product) - allowed:
            raise ValueError('No contribution/feature discount or unknown accounting field')
        result[identity] = calculate_product(product['revenue'], product['allowable_expenses'],
                                             product.get('prior_same_product_loss', '0'))
    return result


def quarter_deadline(year, quarter):
    if quarter not in DEADLINES:
        raise ValueError('Quarter must be 1 through 4')
    month, day, year_offset = DEADLINES[quarter]
    return date(year + year_offset, month, day)


def quarter_period(year, quarter):
    if quarter not in DEADLINES:
        raise ValueError('Quarter must be 1 through 4')
    first_month, last_month = quarter * 3 - 2, quarter * 3
    return date(year, first_month, 1), date(year, last_month, calendar.monthrange(year, last_month)[1])
