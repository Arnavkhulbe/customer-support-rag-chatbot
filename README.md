# ShopSphere — AI Customer Support RAG Chatbot

A full-stack **Retrieval-Augmented Generation (RAG)** chatbot for the fictional e-commerce
company **ShopSphere**. It answers customer questions **only** from the company's policy
PDFs, cites the source document and page for every answer, and refuses to answer anything
that isn't covered by those documents.

---

## Overview

E-commerce support teams spend most of their time answering the same questions over and
over: *How long do I have to return this? When will my refund arrive? Can I change my
delivery address?* Hand-written FAQ pages go stale, and general-purpose chatbots
hallucinate policies that don't exist — confidently telling customers things the company
never promised.

**ShopSphere solves this** by grounding every answer in the company's real policy
documents. The system extracts text from the policy PDFs, embeds it locally, and stores
it in a vector database. At question time it retrieves only the most relevant passages,
gates them behind a relevance threshold, and asks the LLM to answer strictly from that
context — or to refuse. The result is a support bot that can point to the exact document
and page behind every claim, and that defaults to *"I couldn't find this information in
the available ShopSphere company documents"* instead of guessing.

---

## Features

- **PDF-based knowledge base** — five official ShopSphere policy PDFs in `knowledge/` are the single source of truth.
- **Semantic search** — questions are matched by meaning, not keywords, so phrasing variations still find the right policy.
- **Pinecone vector database** — 384-dimension cosine-similarity index (`shopsphere-support`, namespace `policies`) with deterministic, idempotent upserts.
- **Local embeddings** — free, private `sentence-transformers/all-MiniLM-L6-v2` runs on your machine; no embedding API calls.
- **Groq LLM** — fast answer generation via the Groq API (default model `openai/gpt-oss-120b`).
- **Grounded-response guard** — a numeric relevance threshold drops weak matches before the LLM ever runs, and a strict system prompt keeps answers inside the retrieved context.
- **Out-of-scope refusal** — questions the documents can't answer (general knowledge, coding help, sales questions) get a polite, fixed refusal instead of a made-up answer.
- **Source citations & relevance scores** — every response lists the retrieved documents, pages, and similarity scores.
- **React chat interface** — clean chat UI with markdown rendering, source cards, typing indicators, and auto-scroll.
- **Automated RAG evaluation** — a repeatable offline harness (`backend/scripts/eval.py`) scores retrieval and grounding on a 27-question dataset.

---

## Architecture

```
PDFs → Text Extraction → Chunking → Local Embeddings → Pinecone → Retrieval → Relevance Gate → Groq → Grounding Guard → React UI
```

| Component | What it does |
| --- | --- |
| **PDFs** | The five policy documents in `knowledge/` are the only source of truth. |
| **Text Extraction** | `pypdf` reads each page and keeps page numbers + source filename as metadata. |
| **Chunking** | A paragraph/sentence-aware splitter creates approximately 180-word chunks with 40-word overlap, keeping chunks small enough for the embedding model's input limits. |
| **Local Embeddings** | `all-MiniLM-L6-v2` converts each chunk into a 384-dimension vector on your machine (loaded once per process). |
| **Pinecone** | Stores the vectors with their text and metadata (document, page, chunk ID) under deterministic IDs, so re-ingestion upserts instead of duplicating. |
| **Retrieval** | At question time, the question is embedded the same way and Pinecone returns the top-4 most similar chunks. |
| **Relevance Gate** | Chunks scoring below the minimum relevance threshold (`0.20` by default) are discarded; if nothing survives, the fixed fallback is returned **without calling the LLM**. |
| **Groq** | The LLM receives only the surviving chunks, the system prompt, and the question — never the whole knowledge base. |
| **Grounding Guard** | A system-prompt rule requires the model to refuse when the retrieved context doesn't actually contain the answer (second defense layer). |
| **React UI** | Renders the answer as markdown, shows source cards with document/page/score, and keeps the conversation in a responsive chat window. |

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.10+ |
| Backend API | FastAPI + Uvicorn |
| PDF extraction | `pypdf` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local, 384-dim) |
| Vector database | Pinecone (cosine similarity) |
| LLM | Groq API (`openai/gpt-oss-120b` by default) |
| Frontend | React 18 + Vite + plain CSS |
| Markdown rendering | `react-markdown` |
| Evaluation harness | Python + `urllib` (stdlib only) |

---

## Knowledge Base

Five policy documents live in `knowledge/`:

| Document | What it covers |
| --- | --- |
| `return-policy.pdf` | Return window (10 calendar days from the delivery date), return conditions, and how to start a return. |
| `exchange-policy.pdf` | Exchange window (15 calendar days), eligible items, and how to request an exchange. |
| `payment-refund-policy.pdf` | Refund process — refunds are initiated within 2 business days of approval — and refund payment methods. |
| `shipping-delivery.pdf` | Shipping timelines, including standard delivery in 3–7 business days. |
| `orders-account-help.pdf` | Order tracking and cancellation, delivery-address changes (pre-shipment only), password reset via the registered email, and profile updates (name, email, phone, password). |

---

## RAG Pipeline

### Ingestion (offline, run when documents change)

```
knowledge/*.pdf
  → pypdf extracts text per page (source + page metadata)
  → chunker splits into ~180-word chunks (40-word overlap)
  → all-MiniLM-L6-v2 embeds each chunk locally (384-dim)
  → Pinecone upsert with deterministic IDs (document + page + chunk + content hash)
```

- Chunk text is stored as Pinecone **metadata**, so retrieval returns readable text, not vectors.
- Ingestion is **idempotent**: re-running `scripts/ingest.py` updates existing vectors instead of creating duplicates.

### Query time (per user question)

```
question → embed locally → Pinecone top-4 similarity search
        → drop chunks with score < 0.20  (if none remain → fixed fallback, no LLM call)
        → system prompt + retrieved chunks + question → Groq
        → answer + sources (document, page, score)
```

The LLM only ever sees the top-k retrieved chunks — never the full knowledge base, and never raw vectors.

---

## Hallucination / Grounding Protection

Two independent layers keep answers grounded. **Neither layer guarantees zero
hallucinations** — they substantially reduce the risk, but LLM output is probabilistic,
which is why the evaluation harness below exists to measure behavior empirically.

1. **Numeric relevance threshold** — retrieval drops any chunk whose cosine similarity is
   below `MIN_RELEVANCE_SCORE` (default `0.20`, calibrated so off-topic questions score
   below 0.13 while in-scope questions score above 0.19). If no chunk passes, the API
   returns the fixed refusal — *"I couldn't find this information in the available
   ShopSphere company documents."* — **without calling the LLM at all**. There is no path
   for the model to generate text when retrieval finds nothing relevant.

2. **LLM grounding rule** — a numbered rule in the system prompt instructs the model to
   answer only from the retrieved context and to respond with that exact refusal whenever
   the context doesn't contain the requested information. This catches questions that
   clear the numeric gate but still aren't covered by the documents — for example
   *"Do you sell laptops?"*, which retrieves weakly related chunks yet must still be
   refused.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, /health
│   │   ├── config.py                # env-driven settings (pydantic-settings)
│   │   ├── schemas.py               # request/response models
│   │   ├── api/routes/chat.py       # POST /api/v1/chat
│   │   ├── rag/
│   │   │   ├── extraction.py        # PDF → per-page text
│   │   │   ├── chunking.py          # overlap-aware chunker
│   │   │   ├── embeddings.py        # local all-MiniLM-L6-v2 (loaded once)
│   │   │   ├── pinecone_store.py    # index mgmt, deterministic upsert, query
│   │   │   ├── retriever.py         # top-k search + relevance threshold
│   │   │   ├── generator.py         # Groq answer generation + fallback string
│   │   │   └── prompts.py           # system prompt + grounding rules
│   │   └── services/chat_service.py # orchestration: retrieve → generate
│   ├── scripts/
│   │   ├── ingest.py                # ingestion CLI (idempotent)
│   │   ├── eval.py                  # repeatable RAG evaluation harness
│   │   └── eval_dataset.json        # 27-question test dataset
│   ├── requirements.txt
│   └── .venv/                       # local virtual environment
├── frontend/
│   ├── src/
│   │   ├── components/              # ChatWindow, MessageBubble, ChatInput,
│   │   │                            # SourceCard, TypingIndicator
│   │   ├── services/api.js          # backend client
│   │   ├── App.jsx                  # chat state, suggestions, scroll behavior
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── knowledge/                       # the five policy PDFs (source of truth)
├── .env.example                     # template for required API keys
├── .gitignore                       # ignores .env and all secret files
└── README.md
```

---

## Environment Variables

Copy `.env.example` to `.env` in the **project root** and fill in the values. The
template contains exactly two variables:

```env
GROQ_API_KEY=
PINECONE_API_KEY=
```

Real keys never appear in this repository — `.env.example` ships with empty values, and
`.env` is git-ignored.

All other settings have working defaults (see `backend/app/config.py`) and are optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq answer-generation model |
| `PINECONE_INDEX_NAME` | `shopsphere-support` | Vector index name |
| `PINECONE_NAMESPACE` | `policies` | Vector namespace |
| `TOP_K` | `4` | Chunks retrieved per query |
| `MIN_RELEVANCE_SCORE` | `0.20` | Minimum cosine similarity to trust |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `180` / `40` | Chunking parameters (words) |
| `VITE_API_URL` | `http://localhost:8000` | Backend URL used by the frontend |

---

## How to Run

> Commands below are for **Windows** (PowerShell or CMD). The backend must be running
> before ingestion or evaluation.

### 1. Backend

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Verify: <http://localhost:8000/health> should return `{"status": "ok"}`.
API docs: <http://localhost:8000/docs>.

### 2. Frontend

```bat
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

### 3. Ingestion (one-time, or after PDFs change)

With the backend virtual environment activated:

```bat
cd backend
.venv\Scripts\activate
python scripts\ingest.py
```

Safe to re-run — deterministic IDs mean no duplicate vectors.

### 4. Evaluation

With the backend running on port 8000:

```bat
cd backend
.venv\Scripts\activate
python scripts\eval.py
```

Exit code `0` means every test passed. Add `--json results.json` to save machine-readable
results.

---

## RAG Evaluation

The project ships with a repeatable evaluation harness: [`backend/scripts/eval.py`](backend/scripts/eval.py)
runs every question in [`backend/scripts/eval_dataset.json`](backend/scripts/eval_dataset.json)
against the **live API** and scores retrieval and grounding per test.

Dataset: 21 in-scope questions (4–5 per knowledge document) + 6 out-of-scope questions = 27 tests.

**Verified results from the current evaluation dataset (run against the live API):**

| Metric | Result |
| --- | --- |
| Total tests | 27 |
| In-scope tests | 21 |
| Out-of-scope tests | 6 |
| Tests passed | **27 / 27** |
| Overall pass rate | **100%** |
| In-scope pass rate (expected doc retrieved **and** grounded answer) | **100%** |
| Out-of-scope refusal pass rate | **100%** |
| Average in-scope top retrieval score | **0.5662** |
| Consistency | Suite run twice with identical results |

Per-test criteria:

- **In-scope** — passes only if the expected document appears in the retrieved sources *and*
  the final answer is grounded (not the fallback refusal).
- **Out-of-scope** — passes only if the chatbot refuses with the fallback response.

> **These are results from the current 27-question dataset, not a universal accuracy
> guarantee.** They measure this system against these specific questions at this point in
> time. A larger and more diverse dataset (see Future Improvements) would give a broader
> picture of generalization.

---

## Example Questions

| Question | Expected behavior |
| --- | --- |
| *How many days do I have to return an item?* | Grounded answer citing `return-policy.pdf` (10 calendar days from delivery). |
| *How long does it take to receive a refund?* | Grounded answer citing `payment-refund-policy.pdf` (initiated within 2 business days of approval). |
| *How long does standard delivery take?* | Grounded answer citing `shipping-delivery.pdf` (3–7 business days). |
| *How do I change my password?* | Grounded answer citing `orders-account-help.pdf` (reset via the registered email). |
| *Can I exchange an item after 15 days?* | Grounded answer citing `exchange-policy.pdf`, explaining the 15-calendar-day window. |
| *What is the capital of France?* | Refused — out of scope for company policy documents. |
| *Do you sell laptops?* | Refused with the fallback response — not covered by the policy docs. |

Every grounded response also includes source cards showing the document name, page number,
and similarity score.

---

## API

### `POST /api/v1/chat`

```json
{ "question": "How long does a refund take after approval?" }
```

Response:

```json
{
  "answer": "After ShopSphere approves a refund, the refund is initiated within 2 business days…",
  "sources": [
    { "document": "payment-refund-policy.pdf", "page": 2, "document_type": "payment_refund_policy", "score": 0.78 }
  ],
  "score": 0.78
}
```

When the relevance gate blocks a question, the response is the fixed fallback with
`"sources": []` and `"score": null`.

### `GET /health`

```json
{ "status": "ok" }
```

---

## Security

- **API keys live only in `.env`** at the project root, loaded server-side by the FastAPI
  backend. Nothing is hard-coded.
- **`.env` must never be committed.** It is listed in `.gitignore`; the committed
  `.env.example` contains variable *names* with empty values only.
- **The frontend must never contain backend API keys.** The React app talks only to the
  FastAPI backend (via `VITE_API_URL`, which is a URL, not a secret) — Groq and Pinecone
  keys are never bundled into browser JavaScript and are never sent over the wire to the
  client.
- Embedding vectors and raw knowledge-base text are never exposed through the API; only
  cited answer snippets are returned.

---

## Future Improvements

*These are ideas for future work — none of them are implemented in the current project.*

- **Reranking** — add a cross-encoder reranker on top of Pinecone's initial top-k to improve precision on borderline queries.
- **Larger evaluation datasets** — expand beyond the current 27 questions with paraphrases, typos, adversarial phrasings, and multi-intent questions.
- **Better observability** — structured logging/tracing of retrieval scores, refusals, and latency per request; dashboards for drift over time.
- **CI regression testing** — run `eval.py` automatically on every change to prompts, chunking, or retrieval settings to catch regressions before merge.
- **Conversation memory** — multi-turn context so follow-up questions resolve naturally.
- **Streaming responses** — token streaming for lower perceived latency in the chat UI.

---

## License

No license file is currently present in this repository. All rights reserved by the
project owner unless a license is added later. If you intend to reuse this project,
please check with the owner first.
