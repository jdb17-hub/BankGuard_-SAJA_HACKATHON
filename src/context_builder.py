def build_context(transaction, profile, risk):
    labels = dict(
        amount_anomaly=f"El monto equivale a {transaction['amount']/profile['average_amount']:.1f} veces el promedio histórico de ${profile['average_amount']:.2f}.",
        unusual_time=f"La hora {transaction['timestamp'][11:16]} está fuera del horario habitual {profile['usual_hours'][0]:02}:00–{profile['usual_hours'][1]:02}:59.",
        unusual_country=f"El país {transaction['country']} difiere de los países frecuentes: {', '.join(profile['frequent_countries'])}.",
        new_merchant='El comercio no aparece en el historial de referencia.',
        high_velocity='Existen al menos dos operaciones anteriores en los últimos cinco minutos.')
    return dict(transaction={k:transaction[k] for k in ['id','amount','currency','merchant','timestamp','country']},
                profile={k:profile[k] for k in ['average_amount','usual_hours','frequent_countries']},
                signals=risk['signals'], risk_score=risk['risk_score'], risk_level=risk['risk_level'],
                evidence=[labels[s] for s in risk['signals']])
