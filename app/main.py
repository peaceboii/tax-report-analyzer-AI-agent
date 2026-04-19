from __future__ import annotations

"""
app/main.py — AI Tax Assistant (Streamlit)
───────────────────────────────────────────
Features:
  • Supabase OAuth (Google) login gate
  • Sidebar: user info, sign-out, chat history from Supabase
  • Header: title + 🌙 Dark/Light toggle
  • (+) popover: file upload, country select, tool toggles
  • Native st.chat_message rendering
  • All messages persisted to Supabase Postgres
"""

# ── SQLite monkeypatch — MUST be first (fixes ChromaDB on Streamlit Cloud) ───
# Streamlit Cloud ships with a system SQLite too old for chromadb (needs >=3.35.0)
# pysqlite3-binary bundles a modern SQLite and we swap it in at import time.
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass  # Running locally with a modern SQLite — no patch needed
# ─────────────────────────────────────────────────────────────────────────────


import hashlib
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import streamlit as st

# ── Page config (MUST be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="AI Tax Assistant",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local imports ────────────────────────────────────────────────────────────
from agents.graph import run_graph
from rag.store import VectorStore
from utils.chunker import chunk_text
from utils.parsers import extract_file
from utils.db import (
    get_supabase, fetch_chat_sessions, fetch_messages,
    create_chat_session, save_message,
)

# ── Constants ────────────────────────────────────────────────────────────────
COUNTRIES = ["India", "Australia"]
COUNTRY_FLAGS = {"India": "🇮🇳", "Australia": "🇦🇺"}
CHROMA_DIR = str(ROOT / os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db").lstrip("./"))

SUGGESTIONS = [
    "💡 Best tax-saving options under Section 80C?",
    "📂 How do I classify my freelance income?",
    "📈 Explain long-term capital gains tax for stocks",
    "🏠 What deductions can I claim for home loan?",
]


# ══════════════════════════════════════════════════════════════════════════════
# THEME & CSS
# ══════════════════════════════════════════════════════════════════════════════
def inject_theme():
    css_path = ROOT / "ui" / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    if st.session_state.get("theme", "dark") == "light":
        light_path = ROOT / "ui" / "light.css"
        if light_path.exists():
            with open(light_path, encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# STATE INIT
# ══════════════════════════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "user": None,
        "theme": "dark",
        "current_session_id": None,
        "messages": [],
        "history_sessions": [],
        "country": "India",
        "tax_optimization": False,
        "deep_analysis": False,
        "uploaded_docs": [],
        "pending_query": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


@st.cache_resource
def get_store() -> VectorStore:
    return VectorStore(persist_dir=CHROMA_DIR)


# ══════════════════════════════════════════════════════════════════════════════
# FILE PROCESSING
# ══════════════════════════════════════════════════════════════════════════════
def process_file(file_bytes: bytes, filename: str) -> str:
    try:
        sid = hashlib.md5(file_bytes).hexdigest()[:12]
        text = extract_file(file_bytes, filename)
        if not text.strip():
            raise ValueError("No text could be extracted from this file.")
            
        chunks = chunk_text(text, chunk_size=800, overlap=120)
        if chunks:
            uid = st.session_state.user["id"] if st.session_state.user else "anon"
            store = get_store()
            store.add_chunks(chunks, filename=filename, source_id=sid, user_id=uid)
        return sid
    except Exception as e:
        raise RuntimeError(f"Processing failed: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════
def render_auth():
    """Show login screen. Falls back to guest mode if SUPABASE_KEY is missing."""
    inject_theme()

    st.markdown(
        "<div style='text-align:center;padding:60px 20px 20px;'>"
        "<span style='font-size:64px;'>🧾</span>"
        "<h1 style='margin:16px 0 8px;'>AI Tax Assistant</h1>"
        "<p style='color:#718096;font-size:15px;'>Sign in to save your history across sessions</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if supabase_url and supabase_key:
            try:
                from streamlit_supabase_auth import login_form
                session = login_form(
                    url=supabase_url,
                    apiKey=supabase_key,
                    providers=["google"],
                )
                if session:
                    st.session_state.user = session.get("user", {})
                    _load_user_history()
                    st.rerun()
            except ImportError:
                st.warning("Install `streamlit-supabase-auth`: `pip install streamlit-supabase-auth`")
                _offer_guest_mode()
            except Exception as e:
                st.error(f"Auth error: {e}")
                _offer_guest_mode()
        else:
            st.info(
                "**Supabase key not configured.** "
                "Add `SUPABASE_KEY=your_anon_key` to `.env` for cloud auth.\n\n"
                "You can continue as a **guest** — history will be local only."
            )
            _offer_guest_mode()


def _offer_guest_mode():
    st.divider()
    if st.button("🚀 Continue as Guest", use_container_width=True, type="primary"):
        st.session_state.user = {
            "id": f"guest_{uuid.uuid4().hex[:8]}",
            "email": "guest@local",
            "is_guest": True,
        }
        st.rerun()


def _load_user_history():
    if not st.session_state.user or st.session_state.user.get("is_guest"):
        return
    uid = st.session_state.user["id"]
    sessions = fetch_chat_sessions(uid)
    st.session_state.history_sessions = sessions or []
    if sessions:
        _load_session(sessions[0]["id"])
    else:
        st.session_state.messages = []
        st.session_state.current_session_id = None


def _load_session(session_id: str):
    msgs = fetch_messages(session_id)
    st.session_state.current_session_id = session_id
    st.session_state.messages = []
    for m in msgs:
        st.session_state.messages.append({
            "role": m["role"],
            "content": m["content"],
            "sources": m.get("sources") or [],
            "ts": str(m.get("created_at", ""))[:16].replace("T", " "),
        })


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='padding:4px 0 14px;border-bottom:1px solid #1E2A40;margin-bottom:14px;'>"
            "<div style='font-size:18px;font-weight:700;display:flex;align-items:center;gap:8px;'>"
            "🧾 TaxAI Assistant</div>"
            "<div style='font-size:11px;color:#4A5568;margin-top:4px;'>Powered by Gemini + LangGraph</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        email = st.session_state.user.get("email", "Guest")
        is_guest = st.session_state.user.get("is_guest", False)
        st.caption(f"👤 {email}" + (" *(guest)*" if is_guest else ""))

        if st.button("🚪 Sign Out", use_container_width=True, key="logout_btn"):
            st.session_state.clear()
            st.rerun()

        st.divider()

        # Status pills
        flag = COUNTRY_FLAGS.get(st.session_state.country, "🌏")
        st.markdown(
            f'<div style="display:flex;gap:6px;margin-bottom:14px;">'
            f'<span class="pill pill-green"><span class="pulse-dot"></span> Online</span>'
            f'<span class="pill pill-blue">{flag} {st.session_state.country}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if st.button("✏️ New Chat", use_container_width=True, key="new_chat_btn"):
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.session_state.uploaded_docs = []
            st.rerun()

        # History
        st.markdown(
            '<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.08em;color:#4A5568;margin:10px 0;">💬 History</div>',
            unsafe_allow_html=True,
        )

        if not st.session_state.history_sessions:
            st.caption("No history yet")
        else:
            for sess in st.session_state.history_sessions[:15]:
                title = sess.get("title", "Chat")[:24]
                if st.button(f"💬 {title}", key=f"hist_{sess['id']}", use_container_width=True):
                    _load_session(sess["id"])
                    st.rerun()

        # Uploaded docs
        if st.session_state.uploaded_docs:
            st.divider()
            st.markdown(
                '<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
                'letter-spacing:0.08em;color:#4A5568;margin-bottom:8px;">📎 Documents</div>',
                unsafe_allow_html=True,
            )
            for doc in st.session_state.uploaded_docs:
                st.markdown(
                    f'<div class="doc-chip">📄 {doc["name"][:22]}</div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        st.markdown(
            '<div style="font-size:10px;color:#4A5568;text-align:center;">'
            '🔒 Your data stays local · ChromaDB persisted</div>',
            unsafe_allow_html=True,
        )

        # System Status (Debug info)
        with st.expander("🛠️ System Status", expanded=False):
            import sqlite3
            st.caption(f"SQLite: `{sqlite3.sqlite_version}`")
            st.caption(f"Root: `{ROOT.name}`")
            st.caption(f"Persist: `{Path(CHROMA_DIR).name}`")
            try:
                test_file = Path(CHROMA_DIR) / ".write_test"
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text("ok")
                test_file.unlink()
                st.caption("Disk: `✅ Writable`")
            except Exception as e:
                st.caption(f"Disk: `❌ {str(e)[:20]}...`")


# ══════════════════════════════════════════════════════════════════════════════
# HEADER (with theme toggle)
# ══════════════════════════════════════════════════════════════════════════════
def render_header():
    cols = st.columns([8, 2])
    with cols[0]:
        flag = COUNTRY_FLAGS.get(st.session_state.country, "🌏")
        docs_n = len(st.session_state.uploaded_docs)
        docs_badge = f" · 📎 {docs_n}" if docs_n else ""
        st.markdown(
            f'<div style="font-size:19px;font-weight:700;padding:4px 0 8px;display:flex;align-items:center;gap:10px;">'
            f'🧾 AI Tax Advisor'
            f'<span class="pill pill-blue" style="font-size:11px;">{flag} {st.session_state.country}{docs_badge}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with cols[1]:
        is_dark = st.session_state.theme == "dark"
        toggled = st.toggle("🌙 Dark Mode", value=is_dark, key="theme_toggle")
        new_theme = "dark" if toggled else "light"
        if new_theme != st.session_state.theme:
            st.session_state.theme = new_theme
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# (+) POPOVER
# ══════════════════════════════════════════════════════════════════════════════
def render_plus_popover():
    with st.popover("➕", help="Upload files, change country, toggle tools"):
        st.markdown("### ⚙️ Options")

        # File upload
        st.markdown("**📎 Upload Documents**")
        st.caption("PDF, Excel, CSV, or Images")
        uploaded = st.file_uploader(
            "Upload", accept_multiple_files=True,
            type=["pdf", "xlsx", "xls", "csv", "png", "jpg", "jpeg", "webp"],
            key="file_uploader_pop", label_visibility="collapsed",
        )
        if uploaded:
            for uf in uploaded:
                if not any(d["name"] == uf.name for d in st.session_state.uploaded_docs):
                    with st.spinner(f"Processing {uf.name}…"):
                        try:
                            sid = process_file(uf.read(), uf.name)
                            st.session_state.uploaded_docs.append({"name": uf.name, "source_id": sid})
                            st.success(f"✅ {uf.name} indexed!")
                        except Exception as e:
                            st.error(f"❌ {uf.name}: {e}")

        st.divider()

        # Country
        st.markdown("**🌏 Select Country**")
        new_country = st.selectbox(
            "Country", COUNTRIES,
            index=COUNTRIES.index(st.session_state.country),
            label_visibility="collapsed", key="country_sel_pop",
        )
        if new_country != st.session_state.country:
            st.session_state.country = new_country
            st.rerun()

        st.divider()

        # Tools
        st.markdown("**🛠️ Tools**")
        st.session_state.tax_optimization = st.toggle(
            "⚡ Tax Optimization Mode",
            value=st.session_state.tax_optimization, key="tog_opt",
        )
        st.session_state.deep_analysis = st.toggle(
            "🔬 Deep Analysis Mode",
            value=st.session_state.deep_analysis, key="tog_deep",
        )


# ══════════════════════════════════════════════════════════════════════════════
# CHAT RENDERING
# ══════════════════════════════════════════════════════════════════════════════
def render_empty_state():
    st.markdown(
        "<div style='text-align:center;padding:50px 20px 20px;'>"
        "<span style='font-size:56px;display:block;margin-bottom:16px;'>🧾</span>"
        "<h2>Your AI Tax Advisor</h2>"
        "<p style='color:#718096;max-width:420px;margin:0 auto 28px;line-height:1.6;'>"
        "Upload financial documents, ask about deductions, income classification, "
        "or tax optimization. Click <strong>+</strong> to upload files.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, tip in enumerate(SUGGESTIONS):
        if cols[i % 2].button(tip, key=f"sug_{i}", use_container_width=True):
            st.session_state.pending_query = tip
            st.rerun()


def render_messages():
    for msg in st.session_state.messages:
        avatar = "🧾" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            att = msg.get("attachments", [])
            if att:
                st.caption("📎 " + "  ·  ".join(f"`{a}`" for a in att))
            st.markdown(msg["content"])
            sources = msg.get("sources") or []
            if sources:
                with st.expander(f"🌐 {len(sources)} source(s)"):
                    for src in sources:
                        url = src.get("url", "")
                        if url:
                            st.markdown(f"🔗 [{src.get('title', url)[:55]}]({url})")


# ══════════════════════════════════════════════════════════════════════════════
# AGENT EXECUTION
# ══════════════════════════════════════════════════════════════════════════════
def handle_user_input(prompt: str, attachments: list):
    user = st.session_state.user
    uid = user["id"]
    is_guest = user.get("is_guest", False)

    # Ensure a session exists in Supabase (non-guest only)
    if not st.session_state.current_session_id and not is_guest:
        new_sess = create_chat_session(uid, prompt[:48])
        if new_sess:
            st.session_state.current_session_id = new_sess["id"]
            st.session_state.history_sessions.insert(0, new_sess)

    ts = datetime.now().strftime("%H:%M")

    # Save user message
    st.session_state.messages.append({
        "role": "user", "content": prompt,
        "attachments": attachments, "ts": ts,
    })
    sid = st.session_state.current_session_id
    if sid and not is_guest:
        save_message(sid, "user", prompt)

    # Render user bubble
    with st.chat_message("user", avatar="👤"):
        if attachments:
            st.caption("📎 " + "  ·  ".join(f"`{a}`" for a in attachments))
        st.markdown(prompt)

    # Run agent
    with st.chat_message("assistant", avatar="🧾"):
        placeholder = st.empty()
        with st.spinner("Analyzing…"):
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
                if m["role"] in ("user", "assistant")
            ]
            try:
                result = run_graph(
                    query=prompt,
                    user_id=uid,
                    country=st.session_state.country,
                    chat_history=history,
                    tax_optimization=st.session_state.tax_optimization,
                    deep_analysis=st.session_state.deep_analysis,
                )
                response = result.get("response", "No response generated.")
                sources = result.get("sources", [])
            except Exception as e:
                response = f"❌ **Error:** `{e}`\n\nCheck your `GOOGLE_API_KEY` and `GEMINI_MODEL` in `.env`."
                sources = []

        placeholder.markdown(response)

        if sources:
            with st.expander(f"🌐 {len(sources)} source(s)"):
                for src in sources:
                    url = src.get("url", "")
                    if url:
                        st.markdown(f"🔗 [{src.get('title', url)[:55]}]({url})")

    # Persist assistant message
    st.session_state.messages.append({
        "role": "assistant", "content": response,
        "sources": sources, "ts": ts,
    })
    if sid and not is_guest:
        save_message(sid, "assistant", response, sources)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    init_state()
    inject_theme()

    # Auth gate
    if not st.session_state.get("user"):
        render_auth()
        return

    render_sidebar()
    render_header()

    # Pending suggestion click
    if st.session_state.pending_query:
        q = st.session_state.pending_query
        st.session_state.pending_query = None
        handle_user_input(q, [])
        st.rerun()

    # Chat area
    if not st.session_state.messages:
        render_empty_state()
    else:
        render_messages()

    # Bottom bar: [+] | chat input
    col_plus, col_input = st.columns([1, 14])
    with col_plus:
        render_plus_popover()
    with col_input:
        prompt = st.chat_input(
            f"Ask me anything about {st.session_state.country} taxes…"
        )

    if prompt:
        attachments = [d["name"] for d in st.session_state.uploaded_docs]
        handle_user_input(prompt, attachments)


if __name__ == "__main__":
    main()
