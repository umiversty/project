import os
import sys
import types
import json
import csv
import tempfile
import unittest

# Create lightweight fakes for heavy external deps before importing the module under test
lmstudio_fake = types.ModuleType("lmstudio")
class _FakeClient:
    def __init__(self):
        self.llms = types.SimpleNamespace(load=lambda name: None)
lmstudio_fake.Client = _FakeClient
sys.modules["lmstudio"] = lmstudio_fake

spacy_fake = types.ModuleType("spacy")
def _fake_load(name):
    class _DummyNLP:
        def __call__(self, text):
            class _DummyDoc:
                ents = []
                def __iter__(self):
                    return iter([])
            return _DummyDoc()
    return _DummyNLP()
spacy_fake.load = _fake_load
sys.modules["spacy"] = spacy_fake

try:
    import pdfplumber  # type: ignore
    HAS_PDFPLUMBER = True
except ImportError:  # pragma: no cover - fallback for minimal envs
    pdfplumber_fake = types.ModuleType("pdfplumber")

    def _pdfplumber_missing(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("pdfplumber is not available in the test environment")

    pdfplumber_fake.open = _pdfplumber_missing  # type: ignore[attr-defined]
    sys.modules["pdfplumber"] = pdfplumber_fake
    HAS_PDFPLUMBER = False

# Now import the module under test
import pipeline_lmstudio as pl


class MockModel:
    class _Resp:
        def __init__(self, text):
            self.output_text = text

    def generate(self, prompt, max_new_tokens=512, temperature=0.7):
        return MockModel._Resp(
            "1. What is the main idea?\n2. Why is this important?\n3. How does it work?"
        )


class PipelineTestCase(unittest.TestCase):
    def setUp(self):
        # Stub keyword/entity extraction to avoid depending on NLP
        pl.extract_keywords_and_entities = lambda text: (["physics", "math"], ["London"])  # type: ignore

    def test_chunk_generate_and_save(self):
        pages = [
            {"text": "This is a test. Second sentence. Third sentence about physics and math. London is a city."}
        ]

        chunks = pl.chunk_and_summarize(pages, max_words=50)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertIn("summary", chunks[0])

        model = MockModel()
        questions = pl.generate_questions_for_pdf_local(chunks, model, max_questions_per_chunk=3)
        # We expect 3 questions for the single chunk
        self.assertEqual(len(questions), 3)
        for q in questions:
            self.assertIn("chunk_idx", q)
            self.assertIn("question", q)
            self.assertTrue(q["question"])  # non-empty

        with tempfile.TemporaryDirectory() as tmpd:
            json_path = os.path.join(tmpd, "out.json")
            csv_path = os.path.join(tmpd, "out.csv")
            pl.save_questions_json(questions, json_path)
            pl.save_questions_csv(questions, csv_path)

            # Validate JSON contents
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data), 3)

            # Validate CSV row count (including header)
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = list(csv.reader(f))
            # 1 header + 3 rows
            self.assertEqual(len(reader), 4)

    def test_extract_pdf_text_real_sample(self):
        if not HAS_PDFPLUMBER:
            self.skipTest("pdfplumber not installed; skipping PDF extraction test")

        sample_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample.pdf"))
        if not os.path.exists(sample_path):
            self.skipTest("sample.pdf not found")

        # Should not raise even without LM Studio/spacy installed
        pages = pl.extract_pdf_text(sample_path)
        self.assertGreater(len(pages), 0)
        self.assertIn("text", pages[0])
        self.assertIsInstance(pages[0]["text"], str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
