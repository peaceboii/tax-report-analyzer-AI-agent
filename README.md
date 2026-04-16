# 🧾 AI Tax Report Analyzer — AI Agent

> **Production-ready multi-agent AI Tax Assistant** powered by Google Gemini, LangGraph, ChromaDB, and Supabase.

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-Streamlit_Cloud-FF4B4B?style=for-the-badge)](https://tax-report-analyzer-ai-agent-p9cy8ua9xqvkpdsj9evbq3.streamlit.app/)
[![GitHub](https://img.shields.io/badge/GitHub-peaceboii-181717?style=for-the-badge&logo=github)](https://github.com/peaceboii/tax-report-analyzer-AI-agent)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.44+-red?style=for-the-badge&logo=streamlit)](https://streamlit.io)

---

## 🌐 Live App

**→ [https://tax-report-analyzer-ai-agent-p9cy8ua9xqvkpdsj9evbq3.streamlit.app/](https://tax-report-analyzer-ai-agent-p9cy8ua9xqvkpdsj9evbq3.streamlit.app/)**

Sign in with **Google OAuth** or continue as a **Guest** to try the app instantly.

---

## ✨ Features

### 🤖 Multi-Agent LangGraph Pipeline
```
User Query
    │
    ▼
[Retrieval Agent]  ──  Searches uploaded documents via ChromaDB (per-user isolated)
    │
    ▼
[Web Search Agent] ──  Auto-scrapes Google when document context is insufficient
    │
    ▼
[Tax Analyzer]     ──  Injects country-specific tax rules (India 🇮🇳 / Australia 🇦🇺)
    │
    ▼
[Response Agent]   ──  Google Gemini synthesizes a beautifully structured answer
```

### 🔐 Authentication & Persistence
- **Google OAuth** via Supabase — secure, session-based login
- **Guest mode** — full access without sign-in, local session
- **Per-user data isolation** — ChromaDB vectors and Postgres history scoped to each user ID
- **Persistent chat history** — all sessions saved to Supabase Postgres, restored on login

### 💬 Chat Interface
| Feature | Detail |
|---------|--------|
| Sidebar | Chat history list, sign-out, document chips, status pills |
| `+` Popover | File upload, country selector, tool toggles |
| 🌙 Theme toggle | Dark / Light mode in top-right corner |
| Chat bubbles | Native `st.chat_message` — clean, no raw HTML |
| Sources expander | Web sources shown inline under AI responses |

### 📄 Document Processing
| Format | Handler |
|--------|---------|
| PDF | PyMuPDF — full text extraction |
| Excel / CSV | pandas — tabular data context |
| Images | Tesseract OCR (local) → Gemini Vision (fallback) |

### 🛠️ Analysis Tools
- ⚡ **Tax Optimization Mode** — proactively suggests legal tax-saving strategies
- 🔬 **Deep Analysis Mode** — full technical breakdown with regulatory citations
- 🌏 **Multi-country** — India (Sec 80C, LTCG, NPS, HRA…) and Australia (CGT, FBT, super…)

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Streamlit Frontend (app/main.py)                            │
│  • Supabase Auth Gate (Google OAuth + Guest Mode)            │
│  • Sidebar: history, docs, sign-out                          │
│  • Header: title, country badge, 🌙 dark/light toggle        │
│  • Bottom bar: [+] popover | st.chat_input                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  LangGraph Pipeline (agents/graph.py)                        │
│                                                              │
│  retrieval → web_search → tax_analyzer → response_agent     │
│      │                                         │             │
│  ChromaDB                              Gemini Flash          │
│  (per-user vectors)               (gemini-flash-latest)      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Supabase Postgres                                           │
│  • chat_sessions (id, user_id, title, created_at)           │
│  • messages      (id, session_id, role, content, sources)   │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Local)

### 1. Clone
```bash
git clone https://github.com/peaceboii/tax-report-analyzer-AI-agent.git
cd tax-report-analyzer-AI-agent
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

> **Optional for image OCR:** Install [Tesseract OCR](https://tesseract-ocr.github.io/)  
> Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`

### 3. Configure environment
```bash
cp .env.example .env
```
Fill in your `.env`:
```env
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-flash-latest
LLM_BACKEND=gemini

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

CHROMA_PERSIST_DIR=./data/chroma_db
```

### 4. Set up Supabase tables

Run in your **Supabase SQL Editor** (`supabase.com/dashboard → SQL Editor`):

```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);
```

### 5. Enable Google OAuth (optional)

| Step | Where | Action |
|------|-------|--------|
| 1 | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) | Create OAuth 2.0 Client ID (Web app) |
| 2 | Authorized redirect URIs | Add `https://your-project.supabase.co/auth/v1/callback` |
| 3 | [Supabase Auth Providers](https://supabase.com/dashboard/project/_/auth/providers) | Enable Google, paste Client ID + Secret |
| 4 | [Supabase URL Config](https://supabase.com/dashboard/project/_/auth/url-configuration) | Set Site URL to your app URL |

### 6. Run
```bash
python -m streamlit run app/main.py
```
Open → [http://localhost:8501](http://localhost:8501)

---

## 📁 Project Structure

```
tax-report-analyzer-AI-agent/
├── app/
│   └── main.py              # Streamlit UI — auth, sidebar, chat, theme toggle
├── agents/
│   ├── graph.py             # LangGraph 4-node multi-agent pipeline
│   └── tax_rules.py         # Country-specific tax rule context (India/Australia)
├── rag/
│   └── store.py             # Per-user ChromaDB vector store with user_id filtering
├── utils/
│   ├── parsers.py           # PDF / Excel / Image extraction with OCR fallback
│   ├── chunker.py           # Text chunking with overlap
│   ├── web_scraper.py       # Google search + BeautifulSoup scraping
│   └── db.py                # Supabase Postgres wrapper (sessions + messages)
├── ui/
│   ├── style.css            # Full dark theme with Inter font, glassmorphism pills
│   └── light.css            # Light theme override layer
├── .streamlit/
│   └── config.toml          # Streamlit server + theme config
├── .env.example             # Environment variable template
├── runtime.txt              # Python 3.11 pin for Streamlit Cloud
├── requirements.txt         # Python dependencies
└── README.md
```

---

## ☁️ Deployment (Streamlit Cloud)

The app is deployed at:  
**https://tax-report-analyzer-ai-agent-p9cy8ua9xqvkpdsj9evbq3.streamlit.app/**

### To deploy your own fork:
1. Fork this repo on GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app**
3. Select your fork, branch `main`, main file `app/main.py`
4. Under **Advanced settings → Secrets**, add:

```toml
GOOGLE_API_KEY = "your_key"
GEMINI_MODEL = "gemini-flash-latest"
LLM_BACKEND = "gemini"
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your_anon_key"
DATABASE_URL = "postgresql://postgres:password@db.your-project.supabase.co:5432/postgres"
CHROMA_PERSIST_DIR = "./data/chroma_db"
```

5. Click **Deploy**

---

## 🧠 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Streamlit 1.44+ | UI, chat interface, theming |
| Auth | Supabase + streamlit-supabase-auth | Google OAuth, session management |
| Database | Supabase Postgres | Persistent chat history per user |
| AI Orchestration | LangGraph + LangChain | Multi-agent pipeline |
| LLM | Google Gemini Flash | Response generation |
| Vector Store | ChromaDB (local persistent) | Document semantic search |
| Embeddings | Google `embedding-001` | Text vectorization |
| Document Parsing | PyMuPDF, pandas, Pillow | PDF, Excel, Image support |
| OCR | Tesseract + Gemini Vision | Image text extraction with fallback |
| Web Search | BeautifulSoup + requests | Supplementary context retrieval |

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Built With

[Google Gemini](https://ai.google.dev) · [LangGraph](https://github.com/langchain-ai/langgraph) · [Streamlit](https://streamlit.io) · [Supabase](https://supabase.com) · [ChromaDB](https://trychroma.com)
