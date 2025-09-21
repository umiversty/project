import os
import re
import json
import csv
import pdfplumber
import spacy
from openai import OpenAI, BadRequestError

# ==========================================
# Config
# ==========================================
# Set to None or "auto" to auto-pick from what's actually available on LM Studio
PREFERRED_MODEL_NAME = "mistral-nemo-instruct-2407"  # will be ignored if not found
LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
API_KEY = "lm-studio"  # any non-empty string works for LM Studio

# ==========================================
# Setup
# ==========================================
nlp = spacy.load("en_core_web_sm")
if "sentencizer" not in nlp.pipe_names:
    nlp.add_pipe("sentencizer", first=True)

OUTPUT_IMAGE_DIR = "output_images"
os.makedirs(OUTPUT_IMAGE_DIR, exist_ok=True)

llm = OpenAI(base_url=LMSTUDIO_BASE_URL, api_key=API_KEY)

# ==========================================
# Model resolution
# ==========================================
def list_model_ids():
    models = llm.models.list()
    return [m.id for m in getattr(models, "data", [])]

def looks_like_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    bad = ("embed", "embedding", "whisper", "tts", "clip")
    if any(b in low for b in bad):
        return False
    good_hints = ("instruct", "chat", "qwen", "llama", "mistral", "gemma", "phi", "deepseek", "hermes", "orion")
    return any(h in low for h in good_hints)

def resolve_model_name(preferred: str | None) -> str:
    try:
        ids = list_model_ids()
    except Exception as e:
        raise RuntimeError(
            f"Could not query models from LM Studio at {LMSTUDIO_BASE_URL}. "
            f"Make sure the local server is running and a model is started.\nOriginal error: {e}"
        )

    if not ids:
        raise RuntimeError(
            f"No models are visible at {LMSTUDIO_BASE_URL}. Start at least one model in LM Studio's UI."
        )

    # Exact match first
    if preferred and preferred in ids:
        return preferred

    # Loose substring match
    if preferred:
        loose = [mid for mid in ids if preferred.lower() in mid.lower()]
        if loose:
            return loose[0]

    # Auto-pick something chat-friendly
    chatty = [mid for mid in ids if looks_like_chat_model(mid)]
    def score(mid: str) -> tuple:
        m = mid.lower()
        return (
            0 if "instruct" in m else 1,
            0 if "mistral" in m or "mistralai" in m else 1,
            len(m),
            m,
        )
    candidates = sorted(chatty, key=score) if chatty else []
    if candidates:
        return candidates[0]
    return ids[0]

# ==========================================
# LLM call (robust: chat with system+user -> chat with user-only -> legacy completions)
# ==========================================
def generate_text(model_name: str, prompt: str, max_new_tokens=512, temperature=0.7) -> str:
    """
    Try:
      1) Chat API with system+user
      2) Chat API with user-only (some LM Studio templates ban 'system')
      3) Legacy Completions API
    """
    # 1) Try with system+user
    try:
        resp = llm.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You generate concise educational questions."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_new_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content
    except BadRequestError as e:
        # 2) Retry user-only for models whose jinja template rejects 'system'
        if "Only user and assistant roles are supported" in str(e):
            combined = (
                "Instruction: Generate concise educational questions based on the content below.\n\n"
                + prompt
            )
            resp = llm.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": combined}],
                max_tokens=max_new_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content
        # If it failed for some other reason, try the completions endpoint below

    # 3) Legacy Completions fallback
    combined = (
        "Instruction: Generate concise educational questions based on the content below.\n\n"
        + prompt
    )
    resp = llm.completions.create(
        model=model_name,
        prompt=combined,
        max_tokens=max_new_tokens,
        temperature=temperature,
    )
    # LM Studio tends to return a standard .choices[0].text here
    return resp.choices[0].text

# ==========================================
# Helpers
# ==========================================
def clean_text(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(
        [line.strip() for line in lines if line.strip() and not re.match(r"^Page\s*\d+$", line, re.IGNORECASE)]
    )

def extract_keywords_and_entities(text: str):
    if not text.strip():
        return [], []
    doc = nlp(text)
    entities = list({ent.text.strip() for ent in doc.ents if ent.text.strip()})
    keywords = []
    for tok in doc:
        if tok.pos_ in ("NOUN", "PROPN"):
            t = tok.text.strip()
            if 2 <= len(t) <= 40:
                keywords.append(t)
    keywords = list(dict.fromkeys(keywords))[:50]
    return keywords, entities

# ==========================================
# PDF Extraction
# ==========================================
def extract_pdf_text(pdf_path: str):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text = clean_text(text)
            pages.append({"text": text})
    return pages

# ==========================================
# Chunking + metadata
# ==========================================
def chunk_and_summarize(pages, max_words=500):
    chunks = []
    for page in pages:
        words = page["text"].split()
        if not words:
            continue
        for i in range(0, len(words), max_words):
            chunk_text = " ".join(words[i : i + max_words]).strip()
            if not chunk_text:
                continue
            keywords, entities = extract_keywords_and_entities(chunk_text)
            doc = nlp(chunk_text)
            sents = [s.text.strip() for s in doc.sents if s.text.strip()]
            summary = " ".join(sents[:3]) if sents else chunk_text[:300]
            chunks.append(
                {
                    "text": chunk_text,
                    "summary": summary,
                    "keywords": keywords,
                    "entities": entities,
                }
            )
    return chunks

# ==========================================
# Question generation
# ==========================================
def generate_questions_local(chunk, model_name: str, max_questions=3):
    prompt = f"""
You are an educational assistant generating questions.

Chunk summary:
{chunk.get('summary','')}

Text content:
{chunk.get('text','')}

Instructions:
- Generate up to {max_questions} clear educational questions about the content.
- Number each question on its own line.
- Avoid yes/no questions unless they test meaningful understanding.
"""
    raw = generate_text(model_name, prompt, max_new_tokens=512, temperature=0.7)

    # Parse numbered or bulleted lines
    lines = [l.strip() for l in raw.strip().splitlines()]
    numbered = [
        re.sub(r"^\s*(\d+[\.\)]|-)\s*", "", l).strip()
        for l in lines
        if re.match(r"^\s*(\d+[\.\)]|-)\s*", l)
    ]
    if not numbered:
        # Fallback if the model ignored formatting
        numbered = [s.strip() for s in re.split(r"\n|\r|(?:(?<=\?)\s+)", raw) if s.strip()]

    out = [q for q in numbered if q][:max_questions]
    return out

def generate_questions_for_pdf_local(chunks, model_name: str, max_questions_per_chunk=3):
    all_questions = []
    for idx, chunk in enumerate(chunks, start=1):
        q_chunk = generate_questions_local(chunk, model_name, max_questions=max_questions_per_chunk)
        for q in q_chunk:
            all_questions.append(
                {
                    "chunk_idx": idx,
                    "question": q,
                    "summary": chunk.get("summary", ""),
                    "keywords": chunk.get("keywords", []),
                    "entities": chunk.get("entities", []),
                }
            )
    return all_questions

# ==========================================
# Save JSON + CSV
# ==========================================
def save_questions_json(questions, output_path="pdf_questions.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(questions)} questions to {output_path}")

def save_questions_csv(questions, output_path="pdf_questions.csv"):
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["chunk_idx", "question", "summary", "keywords", "entities"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for q in questions:
            writer.writerow(
                {
                    "chunk_idx": q["chunk_idx"],
                    "question": q["question"],
                    "summary": q["summary"],
                    "keywords": "; ".join(q["keywords"]),
                    "entities": "; ".join(q["entities"]),
                }
            )
    print(f"Saved {len(questions)} questions to {output_path}")

# ==========================================
# Main
# ==========================================
if __name__ == "__main__":
    pdf_path = "sample.pdf"  # change if you're feeling adventurous

    print("📄 Extracting PDF content...")
    pages = extract_pdf_text(pdf_path)
    print(f"✅ Extracted {len(pages)} pages from {pdf_path}")

    print(f"🔧 Resolving model on LM Studio (preferred: '{PREFERRED_MODEL_NAME}')...")
    resolved_model = resolve_model_name(PREFERRED_MODEL_NAME)
    if PREFERRED_MODEL_NAME and resolved_model != PREFERRED_MODEL_NAME:
        print(f"ℹ️ Preferred model not found. Using '{resolved_model}' instead.")
    else:
        print(f"✅ Using model '{resolved_model}'")

    print("✂️ Chunking and summarizing text...")
    chunks = chunk_and_summarize(pages)
    print(f"✅ Created {len(chunks)} chunks")

    print("🧠 Generating questions from chunks...")
    questions = generate_questions_for_pdf_local(chunks, resolved_model, max_questions_per_chunk=3)
    print(f"✅ Generated {len(questions)} questions total")

    # Persist results
    save_questions_json(questions, output_path="pdf_questions.json")
    save_questions_csv(questions, output_path="pdf_questions.csv")

    print("🎉 Done.")
