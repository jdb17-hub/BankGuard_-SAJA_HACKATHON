"""Loopback-only web UI and API; no additional dependencies or cloud services."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from src.profile_engine import build_profile
from src.risk_engine import assess
from src.context_builder import build_context
from src.qvac_client import explain, settings, MODEL
from src.rag import ask, chunks_from_docs

ROOT = Path(__file__).resolve().parent
ROWS = json.loads((ROOT/'data/transactions.json').read_text(encoding='utf-8'))['transactions']
PROFILE = build_profile([t for t in ROWS if t['partition']=='baseline'])
EVALUATION = [t for t in ROWS if t['partition']=='evaluation']
INFERENCE_LOCK = threading.Lock()
STATIC = {'/': ('index.html','text/html'), '/app.js': ('app.js','text/javascript'), '/style.css': ('style.css','text/css'), '/logo.svg': ('logo.svg','image/svg+xml')}


def analysis(tx_id):
    tx = next((t for t in EVALUATION if t['id']==tx_id), None)
    if tx is None:
        raise ValueError('Transacción no encontrada.')
    risk = assess(tx, PROFILE, [t for t in ROWS if t['timestamp']<tx['timestamp']])
    return {'transaction':tx,'risk':risk,'context':build_context(tx,PROFILE,risk)}


class Handler(BaseHTTPRequestHandler):
    def send(self, status, value, mime='application/json'):
        payload = json.dumps(value,ensure_ascii=False).encode('utf-8') if mime=='application/json' else value
        self.send_response(status)
        self.send_header('Content-Type',mime+'; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Browser closed; inference still releases its resources.

    def allowed(self):
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        origin = self.headers.get('Origin')
        if self.headers.get('Host') not in hosts or (origin and origin not in {f'http://{h}' for h in hosts}):
            self.send(403,{'error':'Solo se permite acceso desde esta aplicación local.'})
            return False
        return True

    def do_GET(self):
        if not self.allowed(): return
        url = urlsplit(self.path)
        if url.path in STATIC:
            name,mime = STATIC[url.path]
            return self.send(200,(ROOT/'frontend'/name).read_bytes(),mime)
        if url.path=='/api/status':
            try:
                _,model = settings()
                runtime = {'ready':True,'model':MODEL,'size_mb':round(model.stat().st_size/1e6,1)}
            except FileNotFoundError as exc:
                runtime = {'ready':False,'model':MODEL,'error':str(exc)}
            return self.send(200,{'runtime':runtime,'profile':PROFILE,'transactions':EVALUATION,'baseline':[t for t in ROWS if t['partition']=='baseline'],'synthetic':True})
        if url.path=='/api/documents':
            return self.send(200,{'synthetic':True,'chunks':chunks_from_docs()})
        if url.path=='/api/analysis':
            try:
                return self.send(200,analysis(parse_qs(url.query).get('id',[''])[0]))
            except ValueError as exc:
                return self.send(404,{'error':str(exc)})
        self.send(404,{'error':'Ruta no encontrada.'})

    def do_POST(self):
        if not self.allowed(): return
        if self.headers.get('X-BankGuard') != 'local' or self.headers.get_content_type() != 'application/json':
            return self.send(403,{'error':'Solicitud local inválida.'})
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 8192: raise ValueError()
            body = json.loads(self.rfile.read(length))
            if not isinstance(body,dict): raise ValueError()
            if self.path != '/api/ask':
                detail = analysis(body.get('id'))
        except (ValueError, TypeError):
            return self.send(400,{'error':'Solicitud o transacción inválida.'})
        if self.path in ('/api/explain','/api/ask'):
            if self.path=='/api/ask' and (not isinstance(body.get('question'),str) or not 5<=len(body['question'].strip())<=600):
                return self.send(400,{'error':'Escribe una pregunta de entre 5 y 600 caracteres.'})
            if not INFERENCE_LOCK.acquire(blocking=False):
                return self.send(409,{'error':'QVAC está procesando otra operación. Intenta de nuevo al terminar.'})
            try:
                # Rebuild context on the server: never trust a browser-supplied score.
                result = ask(body['question']) if self.path=='/api/ask' else explain(detail['context'])
            except Exception as exc:
                error = {'error':f'QVAC no pudo completar la explicación ({type(exc).__name__}). El análisis de riesgo sigue disponible.'}
            finally:
                INFERENCE_LOCK.release()
            if 'error' in locals():
                return self.send(503,error)
            return self.send(200,result)
        if self.path=='/api/decision':
            choice = body.get('choice')
            if choice not in ('recognized','reported'):
                return self.send(400,{'error':'Respuesta inválida.'})
            return self.send(200,{'simulated':True,'choice':choice,'case':f"FR-{int(body['id'].split('-')[1])+9440}" if choice=='reported' else None})
        self.send(404,{'error':'Ruta no encontrada.'})


if __name__=='__main__':
    server = ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    print('BankGuard Local: http://127.0.0.1:8765', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
