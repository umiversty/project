import os
import re
import json
import csv
import pdfplumber
import spacy
from lmstudio import Client  # LM Studio 2025+ SDK

# --------------------------
# Setup
# --------------------------
nlp = spacy.load("en_core_web_sm")
OUTPUT_IMAGE_DIR = "output_images"
os.makedirs(OUTPUT_IMAGE_DIR, exist_ok=True)

# Initialize LM Studio client
client = Client()

# --------------------------
# Helpers
# --------------------------
def clean_text(text):
    lines = text.splitlines()
    return "\n".join([line.strip() for line in lines if line.strip() and not re.match(r"^Page\s*\d+$", line, re.IGNORECASE)])

def extract_keywords_and_entities(text):
    doc = nlp(text)
    entities = list(set([ent.text for ent in doc.ents]))
    keywords = [token.text for token in doc if token.pos_ in ("NOUN", "PROPN")]
    return list(set(keywords)), entities

# --------------------------
# PDF Extraction
# --------------------------
def extract_pdf_text(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text = clean_text(text)
            pages.append({"text": text})
    return pages

# --------------------------
# Chunking + metadata
# --------------------------
def chunk_and_summarize(pages, max_words=500):
    chunks=[]
    for page in pages:
        words = page["text"].split()
        for i in range(0, len(words), max_words):
            chunk_text = " ".join(words[i:i+max_words])
            keywords, entities = extract_keywords_and_entities(chunk_text)
            sentences = re.split(r'(?<=[.!?]) +', chunk_text)
            summary = " ".join(sentences[:3])
            chunks.append({
                "text": chunk_text,
                "summary": summary,
                "keywords": keywords,
                "entities": entities
            })
    return chunks

# --------------------------
# Question generation
# --------------------------
def generate_questions_local(chunk, model, max_questions=3):
    prompt = f"""
You are an educational assistant generating questions.
Chunk summary: {chunk.get('summary','')}

Text content:
{chunk.get('text','')}

Instructions:
- Generate up to {max_questions} clear educational questions.
- Number each question.
"""
    response = model.generate(
        prompt=prompt,
        max_new_tokens=512,
        temperature=0.7
    )
    questions = re.split(r"\n\d*\.?\s*", response.output_text.strip())
    return [q.strip() for q in questions if q.strip()]

def generate_questions_for_pdf_local(chunks, model, max_questions_per_chunk=3):
    all_questions=[]
    for idx, chunk in enumerate(chunks, start=1):
        q_chunk = generate_questions_local(chunk, model, max_questions=max_questions_per_chunk)
        for q in q_chunk:
            all_questions.append({
                "chunk_idx": idx,
                "question": q,
                "summary": chunk.get("summary",""),
                "keywords": chunk.get("keywords",[]),
                "entities": chunk.get("entities",[])
            })
    return all_questions

# --------------------------
# Save JSON + CSV
# --------------------------
def save_questions_json(questions, output_path="pdf_questions.json"):
    with open(output_path,"w",encoding="utf-8") as f:
        json.dump(questions,f,indent=2,ensure_ascii=False)
    print(f"Saved {len(questions)} questions to {output_path}")

def save_questions_csv(questions, output_path="pdf_questions.csv"):
    with open(output_path,"w",newline="",encoding="utf-8") as csvfile:
        fieldnames=["chunk_idx","question","summary","keywords","entities"]
        writer=csv.DictWriter(csvfile,fieldnames=fieldnames)
        writer.writeheader()
        for q in questions:
            writer.writerow({
                "chunk_idx":q["chunk_idx"],
                "question":q["question"],
                "summary":q["summary"],
                "keywords":"; ".join(q["keywords"]),
                "entities":"; ".join(q["entities"])
            })
    print(f"Saved {len(questions)} questions to {output_path}")

# --------------------------
# Main
# --------------------------
if __name__=="__main__":
    pdf_path="sample.pdf"  # Replace with your PDF
    model_name="mistral-nemo-instruct-2407"

    print("📄 Extracting PDF content...")
    pages = extract_pdf_text(pdf_path)
    print(f"✅ Extracted {len(pages)} pages from {pdf_path}")

    try:
        print(f"🔧 Loading model '{model_name}' via LM Studio SDK...")
        model = client.llms.load(model_name)
    except Exception as e:
        raise RuntimeError(f"Failed to load model '{model_name}': {e}")

    print("✂️ Chunking and summarizing text...")
    chunks = chunk_and_summarize(pages)
    print(f"✅ Created {len(chunks)} chunks")

    print("🧠 Generating questions from chunks...")
    questions = generate_questions_for_pdf_local(chunks, model, max_questions_per_chunk=3)
    print(f"✅ Generated {len(questions)} questions total")

    # Persist results
    save_questions_json(questions, output_path="pdf_questions.json")
    save_questions_csv(questions, output_path="pdf_questions.csv")

    print("🎉 Done.")
