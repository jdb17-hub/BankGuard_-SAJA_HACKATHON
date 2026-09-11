from datetime import datetime
from statistics import mean, median, pstdev
from collections import Counter


def build_profile(history):
    if not history:
        raise ValueError('Se requiere historial anterior a la operación.')
    amounts = [float(t['amount']) for t in history]
    if any(a <= 0 for a in amounts):
        raise ValueError('Los montos deben ser positivos.')
    dates = [datetime.fromisoformat(t['timestamp']) for t in history]
    countries = Counter(t['country'] for t in history)
    return dict(count=len(history), average_amount=round(mean(amounts), 2),
                median_amount=median(amounts), std_amount=round(pstdev(amounts), 2),
                usual_range=[min(amounts), max(amounts)],
                frequent_countries=[c for c, n in countries.items() if n / len(history) >= .1],
                known_merchants=sorted({t['merchant'] for t in history}),
                frequent_categories=dict(Counter(t['category'] for t in history)),
                usual_hours=[min(d.hour for d in dates), max(d.hour for d in dates)],
                transactions_per_day=round(len(history) / max(1, (max(dates)-min(dates)).days+1), 2))
