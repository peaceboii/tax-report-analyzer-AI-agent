# AI Tax Report Analyzer — AI Agent

> **Production-ready AI Tax Assistant** powered by Gemini + LangGraph + Supabase

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.44%2B-red?logo=streamlit)](https://streamlit.io)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)](https://github.com/langchain-ai/langgraph)
[![Supabase](https://img.shields.io/badge/Supabase-Auth%20%26%20DB-green?logo=supabase)](https://supabase.com)
[![Gemini](https://img.shields.io/badge/Gemini-Flash-blue?logo=google)](https://ai.google.dev)

---

## 📸 Screenshots

| Login Screen | Main Chat | Light Mode |
|---|---|---|
| OAuth + Email login via Supabase | Sidebar history, `+` popover, chat | Full light theme toggle |

---

## 🌟 Features

### 🤖 AI Pipeline (LangGraph Multi-Agent)
- **Retrieval Agent** — Searches ChromaDB vector store for uploaded document context
- **Web Search Agent** — Auto-scrapes Google when RAG context is insufficient
- **Tax Analyzer** — Injects country-specific tax rules (India, Australia)
- **Response Agent** — Gemini Flash synthesizes a beautifully structured answer

### 🔐 Authentication
- Supabase OAuth (Google) login with Magic Link / Email fallback
- **Guest mode** for quick access without sign-in
- Per-user data isolation in both ChromaDB (vector store) and Postgres (history)

### 💬 Chat Interface
- Sidebar with persistent chat history fetched from Supabase Postgres
- `+` popover menu for file upload, country selection, tool toggles
- 🌙 **Dark / Light theme toggle** in the top-right corner
- Native `st.chat_message` rendering — no raw HTML bleed

### 📄 Document Processing
- Supports **PDF** (PyMuPDF), **Excel/CSV** (pandas), **Images** (Tesseract OCR + Gemini Vision fallback)
- Documents embedded with Google's `embedding-001` model and stored per-user in ChromaDB

### 🛠️ Tools
- ⚡ **Tax Optimization Mode** — Proactively suggests legal tax-saving strategies
- 🔬 **Deep Analysis Mode** — Full technical breakdown with regulatory citations
- 🌏 **Multi-country** — India (Section 80C, LTCG, etc.) and Australia (CGT, FBT, etc.)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│  Streamlit Frontend (app/main.py)                   │
│  • Supabase Auth Gate                               │
│  • st.chat_message + st.sidebar + st.popover       │
│  • Dark/Light Theme Toggle                          │
└───────────────┬─────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────┐
│  LangGraph Pipeline (agents/graph.py)               │
│                                                     │
│  retrieval ──► web_search ──► tax_analyzer ──► response │
│      │                                        │     │
│  ChromaDB                               Gemini Flash│
│  (per user)                          (gemini-flash) │
└─────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────┐
│  Supabase Postgres                                  │
│  • chat_sessions  (user_id, title, created_at)      │
│  • messages       (session_id, role, content)       │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/peaceboii/tax-report-analyzer-AI-agent.git
cd tax-report-analyzer-AI-agent
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

> **Optional:** Install Tesseract OCR for image processing  
> Windows: Download from [tesseract-ocr.github.io](https://tesseract-ocr.github.io/)

### 3. Configure environment
```bash
cp .env.example .env
# Fill in your credentials
```

```env
# .env
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-flash-latest

LLM_BACKEND=gemini   # or: ollama

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

CHROMA_PERSIST_DIR=./data/chroma_db
```

### 4. Set up Supabase tables

Run this SQL in your **Supabase SQL Editor**:

```sql
-- Chat sessions per user
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- Messages per session
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- Enable Row Level Security
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
```

Also enable **Google OAuth** in your Supabase dashboard:  
`Authentication → Providers → Google → Enable`

### 5. Run the app
```bash
python -m streamlit run app/main.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## 📁 Project Structure

```
tax-report-analyzer-AI-agent/
├── app/
│   └── main.py              # Streamlit UI — auth, chat, theme
├── agents/
│   ├── graph.py             # LangGraph multi-agent pipeline
│   └── tax_rules.py         # Country-specific tax rule context
├── rag/
│   └── store.py             # ChromaDB vector store (per-user)
├── utils/
│   ├── parsers.py           # PDF / Excel / Image extraction
│   ├── chunker.py           # Text chunking utility
│   ├── web_scraper.py       # Google search + web scraping
│   └── db.py                # Supabase Postgres wrapper
├── ui/
│   ├── style.css            # Dark theme
│   └── light.css            # Light theme overrides
├── .streamlit/
│   └── config.toml          # Streamlit server config
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies
└── README.md
```

---

## 🌐 Deployment

### Streamlit Cloud
1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Set **Main file path:** `app/main.py`
4. Add secrets in the Streamlit Cloud dashboard (from your `.env`)

### Environment Variables for Deployment
| Key | Description |
|-----|-------------|
| `GOOGLE_API_KEY` | Gemini API key from [ai.google.dev](https://ai.google.dev) |
| `GEMINI_MODEL` | e.g., `gemini-flash-latest` |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/publishable key |
| `DATABASE_URL` | Postgres connection string |
| `CHROMA_PERSIST_DIR` | Local path for ChromaDB persistence |

---

## 🧠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit 1.44+ |
| AI Orchestration | LangGraph + LangChain |
| LLM | Google Gemini Flash |
| Vector Store | ChromaDB (local persistent) |
| Auth & Database | Supabase (Postgres + OAuth) |
| Embeddings | Google `embedding-001` |
| PDF Parsing | PyMuPDF |
| OCR | Tesseract + Gemini Vision fallback |
| Web Search | BeautifulSoup + requests |

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

Built with [LangGraph](https://github.com/langchain-ai/langgraph), [Streamlit](https://streamlit.io), [Supabase](https://supabase.com), and [Google Gemini](https://ai.google.dev).
