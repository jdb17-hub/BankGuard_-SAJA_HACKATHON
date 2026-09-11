import unittest
from src.profile_engine import build_profile
from src.risk_engine import assess


class Engines(unittest.TestCase):
    def setUp(self):
        self.normal = dict(id='N', timestamp='2026-09-10T12:00:00-05:00', amount=28, country='PA', merchant='SUPER', category='food')
        self.history = [dict(self.normal, id=str(i), timestamp=f'2026-09-{i+1:02}T12:00:00-05:00', amount=20+i*2) for i in range(8)]
        self.profile = build_profile(self.history)

    def test_profile(self):
        self.assertEqual(self.profile['average_amount'], 27)
        self.assertEqual(self.profile['median_amount'], 27)

    def test_empty_history(self):
        with self.assertRaises(ValueError): build_profile([])

    def test_normal_transaction_low_risk(self):
        self.assertEqual(assess(self.normal,self.profile)['risk_score'],0)

    def test_high_amount_increases_risk(self):
        self.assertEqual(assess(dict(self.normal,amount=347),self.profile)['risk_score'],30)

    def test_foreign_country_increases_risk(self):
        self.assertEqual(assess(dict(self.normal,country='CO'),self.profile)['risk_score'],25)

    def test_unusual_time_increases_risk(self):
        self.assertEqual(assess(dict(self.normal,timestamp='2026-09-10T02:37:00-05:00'),self.profile)['risk_score'],15)

    def test_new_merchant_increases_risk(self):
        self.assertEqual(assess(dict(self.normal,merchant='TECH'),self.profile)['risk_score'],15)

    def test_multiple_signals_high_risk(self):
        self.assertEqual(assess(dict(self.normal,amount=347,country='CO',merchant='TECH',timestamp='2026-09-10T02:37:00-05:00'),self.profile)['risk_score'],85)

    def test_velocity_and_future_excluded(self):
        past=[dict(self.normal,id=str(i),timestamp='2026-09-10T11:59:00-05:00') for i in range(2)]
        self.assertTrue(assess(self.normal,self.profile,past)['high_velocity'])
        self.assertFalse(assess(self.normal,self.profile,[dict(t,timestamp='2026-09-10T12:01:00-05:00') for t in past])['high_velocity'])

if __name__ == '__main__': unittest.main()
