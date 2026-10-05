TERMINAL 1 — BACKEND

cd D:\customer_support_rag_chatbot\backend
.venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000






TERMINAL 2 — FRONTEND

cd D:\customer_support_rag_chatbot\frontend
npm run dev




ShopSphere Customer Support RAG Chatbot
ShopSphere is a full-stack Retrieval-Augmented Generation (RAG) customer support chatbot built using FastAPI, React, Pinecone, Sentence Transformers, and Groq.

The system retrieves relevant information from ShopSphere policy documents using semantic vector search and uses the retrieved context to generate grounded responses.

It uses all-MiniLM-L6-v2 for local embeddings, Pinecone for vector storage and similarity search, and Groq for LLM-based response generation.

The chatbot also includes relevance filtering, grounding rules, source citations, and out-of-scope question handling to reduce unsupported answers.

The frontend is built with React and provides a simple chat interface for questions related to ShopSphere's orders, returns, refunds, exchanges, shipping, and account information.
