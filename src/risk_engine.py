from datetime import datetime

WEIGHTS = dict(amount_anomaly=30, unusual_time=15, unusual_country=25, new_merchant=15, high_velocity=15)


def assess(transaction, profile, previous=()):
    moment = datetime.fromisoformat(transaction['timestamp'])
    if transaction['amount'] <= 0:
        raise ValueError('El monto debe ser positivo.')
    recent = sum(0 <= (moment-datetime.fromisoformat(t['timestamp'])).total_seconds() <= 300
                 for t in previous if t['id'] != transaction['id'])
    flags = dict(
        amount_anomaly=transaction['amount'] > max(3*profile['average_amount'], profile['average_amount']+3*profile['std_amount']),
        unusual_time=not profile['usual_hours'][0] <= moment.hour <= profile['usual_hours'][1],
        unusual_country=transaction['country'] not in profile['frequent_countries'],
        new_merchant=transaction['merchant'] not in profile['known_merchants'],
        high_velocity=recent >= 2)
    score = min(100, sum(WEIGHTS[k] for k, v in flags.items() if v))
    level = 'bajo' if score < 30 else 'medio' if score < 60 else 'alto' if score < 80 else 'crítico'
    return dict(**flags, signals=[k for k,v in flags.items() if v], risk_score=score, risk_level=level)
