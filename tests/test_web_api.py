import json
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server


class WebAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join()

    def request(self,path,body=None,extra=None):
        c=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        headers={'Content-Type':'application/json','X-BankGuard':'local',**(extra or {})}
        c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
        r=c.getresponse(); status=r.status; payload=r.read(); c.close()
        return status,payload

    def test_static_and_analyses(self):
        for path in ['/','/app.js','/style.css']:
            self.assertEqual(self.request(path)[0],200)
        for tx,score in [('TX-1040',0),('TX-1042',85),('TX-1044',100)]:
            status,data=self.request('/api/analysis?id='+tx)
            self.assertEqual(status,200)
            self.assertEqual(json.loads(data)['risk']['risk_score'],score)
        self.assertEqual(self.request('/api/analysis?id=unknown')[0],404)
        self.assertEqual(self.request('/../README.md')[0],404)

    def test_rebuilds_context_and_handles_qvac_failure(self):
        with patch('server.explain',return_value={'summary':'test'}) as mock:
            self.assertEqual(self.request('/api/explain',{'id':'TX-1042','risk_score':0})[0],200)
            self.assertEqual(mock.call_args.args[0]['risk_score'],85)
        with patch('server.explain',side_effect=RuntimeError('test')):
            self.assertEqual(self.request('/api/explain',{'id':'TX-1042'})[0],503)
        self.assertFalse(server.INFERENCE_LOCK.locked())

    def test_no_concurrent_inference(self):
        server.INFERENCE_LOCK.acquire()
        try:
            self.assertEqual(self.request('/api/explain',{'id':'TX-1042'})[0],409)
        finally: server.INFERENCE_LOCK.release()

    def test_rag_endpoint_and_shared_inference_lock(self):
        status,data=self.request('/api/documents')
        self.assertEqual(status,200)
        self.assertEqual(len(json.loads(data)['chunks']),10)
        with patch('server.ask',return_value={'answer':'test','sources':[]}) as mock:
            self.assertEqual(self.request('/api/ask',{'question':'Pregunta de prueba'})[0],200)
            mock.assert_called_once_with('Pregunta de prueba')
        self.assertEqual(self.request('/api/ask',{'question':'a'})[0],400)
        server.INFERENCE_LOCK.acquire()
        try:
            self.assertEqual(self.request('/api/ask',{'question':'Pregunta de prueba'})[0],409)
        finally: server.INFERENCE_LOCK.release()

    def test_simulated_decisions_and_origin_guard(self):
        status,result=self.request('/api/decision',{'id':'TX-1042','choice':'reported'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(result),{'simulated':True,'choice':'reported','case':'FR-10482'})
        self.assertEqual(self.request('/api/decision',{'id':'TX-1042','choice':'bad'})[0],400)
        self.assertEqual(self.request('/api/decision',{'id':'TX-1042','choice':'reported'}, {'Origin':'https://outside.example'})[0],403)
        self.assertEqual(self.request('/api/status',extra={'Host':'outside.example'})[0],403)
