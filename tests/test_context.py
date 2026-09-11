import json
import unittest
from pathlib import Path
from src.profile_engine import build_profile
from src.risk_engine import assess
from src.context_builder import build_context

class Context(unittest.TestCase):
    def test_dataset_and_context(self):
        data=json.loads((Path(__file__).resolve().parents[1]/'data/transactions.json').read_text(encoding='utf-8'))
        self.assertTrue(data['synthetic'])
        rows=data['transactions']
        self.assertEqual(len(rows),30)
        baseline=[t for t in rows if t['partition']=='baseline']
        profile=build_profile(baseline)
        self.assertEqual(profile['average_amount'],28)
        expected=[0,0,85,85,100,85]
        for tx,score in zip([t for t in rows if t['partition']=='evaluation'],expected):
            self.assertTrue(all(t['timestamp']<tx['timestamp'] for t in baseline))
            risk=assess(tx,profile,[t for t in rows if t['timestamp']<tx['timestamp']])
            self.assertEqual(risk['risk_score'],score)
            context=build_context(tx,profile,risk)
            self.assertNotIn('known_merchants',context['profile'])
            self.assertEqual(len(context['evidence']),len(risk['signals']))
            self.assertLess(len(json.dumps(context)),1800)
