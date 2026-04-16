"""
utils/db.py
Supabase Database Wrapper for AI Tax Assistant
"""

import os
from supabase import create_client, Client

_supabase_client = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY missing in .env")
        _supabase_client = create_client(url, key)
    return _supabase_client

def fetch_chat_sessions(user_id: str):
    try:
        supabase = get_supabase()
        response = supabase.table("chat_sessions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        print("Fetch sessions error:", e)
        return []

def create_chat_session(user_id: str, title: str):
    try:
        supabase = get_supabase()
        response = supabase.table("chat_sessions").insert({
            "user_id": user_id,
            "title": title
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print("Create session error:", e)
        return None

def fetch_messages(session_id: str):
    try:
        supabase = get_supabase()
        response = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
        return response.data
    except Exception as e:
        print("Fetch messages error:", e)
        return []

def save_message(session_id: str, role: str, content: str, sources: list = None):
    try:
        supabase = get_supabase()
        data = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "sources": sources or []
        }
        supabase.table("messages").insert(data).execute()
    except Exception as e:
        print("Save message error:", e)
