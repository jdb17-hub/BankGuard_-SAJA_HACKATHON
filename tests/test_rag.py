import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from src.rag import ask, chunks_from_docs, cosine, fingerprint, retrieve, terms, eligible_sources


class Rag(unittest.TestCase):
    def test_documents_are_synthetic_and_chunked(self):
        chunks=chunks_from_docs()
        self.assertEqual(len(chunks),10)
        self.assertEqual(len({c['document'] for c in chunks}),5)
        self.assertEqual(len({c['id'] for c in chunks}),10)
        for path in (Path(__file__).resolve().parents[1]/'data/security_docs').glob('*.md'):
            self.assertIn('100% sintético',path.read_text(encoding='utf-8'))

    def test_cosine_and_rank(self):
        self.assertAlmostEqual(cosine([1,0],[1,0]),1)
        self.assertEqual(cosine([1,0],[0,1]),0)
        with self.assertRaises(ValueError): cosine([1],[1,2])
        chunks=[{'id':'a','heading':'correo contraseña','text':'No respondas al correo.'},{'id':'b','heading':'tarjeta','text':'Reporte simulado.'}]
        self.assertEqual(retrieve('correo contraseña',[1,0],chunks,[[1,0],[0,1]])[0]['id'],'a')
        self.assertIn('contrasena',terms('¿Mi CONTRASEÑA?'))

    def test_index_changes_with_documents_or_model(self):
        with tempfile.TemporaryDirectory() as folder:
            model=Path(folder)/'model.gguf';model.write_bytes(b'test')
            original=fingerprint([{'text':'a'}],model)
            self.assertNotEqual(original,fingerprint([{'text':'b'}],model))
            model.write_bytes(b'changed')
            self.assertNotEqual(original,fingerprint([{'text':'a'}],model))

    def test_invalid_questions_do_not_load_models(self):
        with patch('src.rag.run_local') as run:
            for question in ('', 'abc', 'x'*601, None):
                with self.assertRaises(ValueError): ask(question)
            run.assert_not_called()

    def test_unrelated_semantic_match_cannot_be_cited(self):
        sources=[{'id':'a','score':.95,'lexical':0},{'id':'b','score':.6,'lexical':.2}]
        self.assertEqual([c['id'] for c in eligible_sources(sources)],['b'])
        self.assertEqual(eligible_sources(sources[:1]),[])

    def test_only_transient_rpc_failure_is_retried(self):
        with patch('src.rag._ask',new=AsyncMock(side_effect=[RuntimeError('RPC is closed'),{'answer':'ok'}])) as call:
            self.assertEqual(ask('Pregunta de prueba')['attempts'],2)
            self.assertEqual(call.await_count,2)
        with patch('src.rag._ask',new=AsyncMock(side_effect=ValueError('invalid output'))) as call:
            with self.assertRaises(ValueError): ask('Pregunta de prueba')
            self.assertEqual(call.await_count,1)
