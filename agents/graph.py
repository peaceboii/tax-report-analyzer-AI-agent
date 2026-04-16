"""
agents/graph.py
────────────────
LangGraph multi-agent orchestration for the AI Tax Assistant.

Nodes:
  1. retrieval_agent   – Fetches context from ChromaDB
  2. web_search_agent  – Scrapes web if RAG score is low
  3. tax_analyzer      – Injects country-specific rules
  4. response_agent    – Generates final structured answer
"""

from __future__ import annotations

import os
from typing import Any, Optional, TypedDict

from dotenv import load_dotenv

load_dotenv()


# ── State ─────────────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    query: str
    user_id: str
    country: str
    chat_history: list[dict]
    tax_optimization: bool
    deep_analysis: bool
    rag_context: str
    rag_score: float
    web_context: str
    web_sources: list[dict]
    tax_rules_context: str
    use_web: bool
    response: str
    sources: list[dict]


# ── LLM factory (fixed model names) ──────────────────────────────────────────
def _get_llm():
    """Return a LangChain-compatible LLM based on LLM_BACKEND env var."""
    backend = os.getenv("LLM_BACKEND", "gemini").lower()

    if backend == "ollama":
        from langchain_community.llms import Ollama
        return Ollama(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3"),
        )
    else:
        # Use gemini-1.5-flash – stable, fast, supports v1beta generateContent
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.3,
            convert_system_message_to_human=True,  # Gemini requires this
        )


# ── Node: retrieval ───────────────────────────────────────────────────────────
def retrieval_agent(state: AgentState) -> AgentState:
    """Search ChromaDB for document + memory context."""
    try:
        from rag.store import VectorStore
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
        store = VectorStore(persist_dir=persist_dir)

        results = store.search_docs(state["query"], user_id=state.get("user_id", ""), k=6)
        mem = store.search_memory(state["query"], user_id=state.get("user_id", ""), k=2)

        if results:
            avg_score = sum(r["score"] for r in results) / len(results)
            parts = [r["text"] for r in results]
            if mem:
                parts.insert(0, "## Prior conversation context:\n" + "\n".join(mem))
            rag_ctx = "\n\n".join(parts)
        else:
            avg_score = 0.0
            rag_ctx = ""

        use_web = avg_score < 0.45 or not rag_ctx.strip()

    except Exception as e:
        rag_ctx = ""
        avg_score = 0.0
        use_web = True

    return {**state, "rag_context": rag_ctx, "rag_score": avg_score, "use_web": use_web}


# ── Node: web search ──────────────────────────────────────────────────────────
def web_search_agent(state: AgentState) -> AgentState:
    """Scrape web for context when RAG is insufficient."""
    if not state.get("use_web", False):
        return {**state, "web_context": "", "web_sources": []}

    try:
        from utils.web_scraper import web_search_and_scrape
        country = state.get("country", "India")
        query = f"{state['query']} {country} tax rules 2024"
        result = web_search_and_scrape(query, num_results=3, max_chars_per_page=1500)
        return {**state, "web_context": result["context"], "web_sources": result["sources"]}
    except Exception as e:
        return {**state, "web_context": "", "web_sources": [], "web_error": str(e)}


# ── Node: tax analyzer ────────────────────────────────────────────────────────
def tax_analyzer(state: AgentState) -> AgentState:
    """Inject country-specific tax rules into state."""
    from agents.tax_rules import get_country_context
    rules_ctx = get_country_context(state.get("country", "India"))
    return {**state, "tax_rules_context": rules_ctx}


# ── Node: response ────────────────────────────────────────────────────────────
def response_agent(state: AgentState) -> AgentState:
    """Synthesize all contexts → structured LLM response."""
    llm = _get_llm()

    country = state.get("country", "India")
    tax_opt = state.get("tax_optimization", False)
    deep = state.get("deep_analysis", False)

    mode_notes = []
    if tax_opt:
        mode_notes.append("TAX OPTIMIZATION MODE ON: Proactively suggest legal tax-saving strategies.")
    if deep:
        mode_notes.append("DEEP ANALYSIS MODE ON: Provide thorough technical analysis with citations.")

    system_text = f"""You are an expert AI Tax Advisor specializing in {country} taxation.
{chr(10).join(mode_notes)}

Always structure your response using these sections (use markdown):

## 📋 Summary
Brief, direct answer to the user's question.

## 💡 Tax-Saving Insights
Specific actionable tips with amounts/percentages where applicable.

## ⚠️ Risk Flags
Any compliance risks or red flags.

## 📊 Data Tables
Present financial data in clean markdown tables if applicable.

{"## 🔍 Detailed Reasoning" if deep else ""}
{"Thorough technical explanation with regulatory citations." if deep else ""}

Be precise. Cite sections (e.g., Section 80C, Schedule FA). Use markdown formatting.
"""

    # Assemble context blocks
    context_blocks = []
    if state.get("tax_rules_context"):
        context_blocks.append(f"### Tax Reference\n{state['tax_rules_context']}")
    if state.get("rag_context"):
        context_blocks.append(f"### Document Context\n{state['rag_context']}")
    if state.get("web_context"):
        context_blocks.append(f"### Web Research\n{state['web_context']}")

    # Build LangChain messages
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    messages = [SystemMessage(content=system_text)]

    # Last 6 conversation turns for context
    for turn in (state.get("chat_history") or [])[-6:]:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))

    # Final user message with all injected context
    if context_blocks:
        combined = "\n\n".join(context_blocks)
        user_content = f"{combined}\n\n---\n**User Question:** {state['query']}"
    else:
        user_content = state["query"]

    messages.append(HumanMessage(content=user_content))

    try:
        result = llm.invoke(messages)
        raw_content = result.content
        
        # Parse content blocks if the model returns a list/stringified list
        if isinstance(raw_content, str):
            if raw_content.startswith("[{'type': 'text'"):
                try:
                    import ast
                    parsed = ast.literal_eval(raw_content)
                    response_text = parsed[0].get('text', raw_content)
                except Exception:
                    response_text = raw_content
            else:
                response_text = raw_content
        elif isinstance(raw_content, list) and len(raw_content) > 0 and isinstance(raw_content[0], dict):
            response_text = raw_content[0].get("text", str(raw_content))
        else:
            response_text = str(raw_content)
            
    except Exception as e:
        response_text = f"❌ **LLM Error:** {e}\n\nPlease check your API key and model name in `.env`."

    return {
        **state,
        "response": response_text,
        "sources": list(state.get("web_sources") or []),
    }


# ── Graph compilation ─────────────────────────────────────────────────────────
def build_graph():
    from langgraph.graph import END, StateGraph

    g = StateGraph(AgentState)
    g.add_node("retrieval", retrieval_agent)
    g.add_node("web_search", web_search_agent)
    g.add_node("tax_analyzer", tax_analyzer)
    g.add_node("response", response_agent)

    g.set_entry_point("retrieval")
    g.add_edge("retrieval", "web_search")
    g.add_edge("web_search", "tax_analyzer")
    g.add_edge("tax_analyzer", "response")
    g.add_edge("response", END)

    return g.compile()


_GRAPH = None


def run_graph(
    query: str,
    user_id: str,
    country: str = "India",
    chat_history: Optional[list[dict]] = None,
    tax_optimization: bool = False,
    deep_analysis: bool = False,
) -> dict[str, Any]:
    """Run the agent graph and return result state."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()

    initial: AgentState = {
        "query": query,
        "user_id": user_id,
        "country": country,
        "chat_history": chat_history or [],
        "tax_optimization": tax_optimization,
        "deep_analysis": deep_analysis,
    }
    return _GRAPH.invoke(initial)
