"""Pure calculations; values supplied in one order/pricelist currency by the provider."""
from collections import defaultdict


def percentage(numerator, denominator):
    return 100.0 * numerator / denominator if denominator else 0.0


def growth(current, previous):
    # No invented infinity/100% when the comparison has no positive sales.
    return percentage(current - previous, previous) if previous > 0 else None


def customer_metrics(rows):
    amounts, counts = defaultdict(float), defaultdict(int)
    for row in rows:
        amounts[row['customer']] += row['amount']
        counts[row['customer']] += row.get('count',1)
    positive = [max(v, 0.0) for v in amounts.values()]
    return {
        'customers': len(counts),
        'repeat_share': percentage(sum(n > 1 for n in counts.values()), len(counts)),
        'top5_share': percentage(sum(sorted(positive, reverse=True)[:5]), sum(positive)),
    }


def summary(rows):
    total = sum(r['amount'] for r in rows)
    margin = sum(r.get('margin', 0.0) for r in rows)
    count=sum(r.get('count',1) for r in rows)
    return dict(bookings=total, orders=count, aov=total / count if count else 0.0,
                margin=margin, margin_pct=percentage(margin, total),
                confirmation_days=sum(r.get('days', 0.0) for r in rows)/count if count else 0.0,
                **customer_metrics(rows))


def grouped(rows, dimension, measure='amount'):
    totals = defaultdict(float)
    labels = {}
    for row in rows:
        key = row[dimension]
        labels[key] = row[dimension + '_label']
        totals[key] += row[measure]
    items = [(key, labels[key], value) for key, value in totals.items()]
    if dimension == 'month':
        items.sort(key=lambda r: r[0])
        selected = items[-12:]
    else:
        items.sort(key=lambda r: (-abs(r[2]), str(r[0])))
        selected = items[:12]
    return [{'label': label, 'value': value} for _, label, value in selected], len(items) > 12


def monthly(rows, measure, start, end):
    """Calendar-complete series, with at most the latest 12 calendar months."""
    totals = defaultdict(float)
    for row in rows:
        totals[row['month']] += row[measure]
    end_index = end.year * 12 + end.month - 1
    if start:
        first_index = start.year * 12 + start.month - 1
    elif totals:
        year, month = map(int, min(totals).split('-'))
        first_index = year * 12 + month - 1
    else:
        first_index = end_index
    truncated = end_index - first_index + 1 > 12
    first_index = max(first_index, end_index - 11)
    result = []
    for index in range(first_index, end_index + 1):
        year, month = divmod(index, 12)
        label = '%04d-%02d' % (year, month + 1)
        result.append({'label': label, 'value': totals.get(label, 0.0)})
    return result, truncated
