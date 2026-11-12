import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="Personal AI", page_icon="🧠", layout="wide")

def api(method, path, **kwargs):
    try:
        response = requests.request(method, API + path, timeout=120, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Backend connection error: {exc}")
        return None

st.title("🧠 Personal AI Assistant")
st.caption("Version 1 prototype • Projects, files, memory, and learning tools")
with st.sidebar:
    st.header("Projects")
    projects = api("GET", "/projects") or []
    labels = ["General chat"] + [f"{p['name']} (#{p['id']})" for p in projects]
    selected = st.selectbox("Choose a project", labels)
    project_id = projects[labels.index(selected)-1]["id"] if selected != "General chat" else None
    st.divider()
    st.subheader("Create project")
    with st.form("new_project"):
        pname = st.text_input("Project name")
        pdesc = st.text_area("Description")
        if st.form_submit_button("Create project") and pname.strip():
            api("POST", "/projects", json={"name": pname, "description": pdesc})
            st.rerun()
    if project_id and st.button("Delete selected project"):
        api("DELETE", f"/projects/{project_id}")
        st.rerun()

tab_chat, tab_files, tab_memory, tab_code, tab_writing = st.tabs(["Chat", "Documents", "Memory", "Coding analysis", "Writing style"])
with tab_chat:
    st.subheader("Chat")
    if project_id:
        for msg in api("GET", f"/projects/{project_id}/messages") or []:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
    prompt = st.chat_input("What are you working on?")
    if prompt:
        with st.chat_message("user"): st.markdown(prompt)
        with st.spinner("Thinking..."):
            result = api("POST", "/chat", json={"message": prompt, "project_id": project_id})
        if result:
            with st.chat_message("assistant"): st.markdown(result["answer"])
            st.rerun()
    if not project_id: st.info("Choose or create a project to save chat history. General chat is not stored.")
with tab_files:
    st.subheader("Upload project documents")
    if not project_id: st.info("Select a project first.")
    else:
        upload = st.file_uploader("TXT, MD, PDF, DOCX, or code files (max 10 MB)")
        if upload and st.button("Upload file"):
            result = api("POST", f"/upload/{project_id}", files={"file": (upload.name, upload.getvalue(), upload.type)})
            if result: st.success(f"Uploaded {result['filename']} — extracted {result['characters_extracted']} characters.")
        for doc in api("GET", f"/projects/{project_id}/documents") or []:
            st.write(f"📄 **{doc['filename']}** — {doc['characters']} extracted characters")
with tab_memory:
    st.subheader("Long-term memory")
    st.caption("Only information you explicitly add is saved. You can review and delete it.")
    with st.form("memory_form"):
        category = st.selectbox("Category", ["preference", "project", "coding habit", "writing habit", "feedback"])
        content = st.text_area("What should the assistant remember?")
        if st.form_submit_button("Save memory") and content.strip():
            api("POST", "/memories", json={"category": category, "content": content})
            st.rerun()
    for memory in api("GET", "/memories") or []:
        c1, c2 = st.columns([5, 1])
        c1.write(f"**{memory['category']}** — {memory['content']}")
        if c2.button("Delete", key=f"del_{memory['id']}"):
            api("DELETE", f"/memories/{memory['id']}")
            st.rerun()
with tab_code:
    st.subheader("Coding analysis")
    language = st.selectbox("Language", ["python", "javascript", "typescript", "java", "c++"])
    code = st.text_area("Paste code to analyze", height=260)
    if st.button("Analyze code") and code.strip():
        with st.spinner("Analyzing code..."):
            result = api("POST", "/analyze/code", json={"code": code, "language": language})
        if result:
            st.markdown(result["analysis"])
            for pattern, explanation in result["detected_patterns"]: st.write(f"- `{pattern}` — {explanation}")
            st.caption(result["note"])
            if result["pattern_history"]: st.json(result["pattern_history"])
with tab_writing:
    st.subheader("Writing-style analysis")
    sample = st.text_area("Paste a writing sample (at least 30 characters)", height=240)
    if st.button("Analyze writing") and len(sample.strip()) >= 30:
        with st.spinner("Analyzing writing style..."):
            result = api("POST", "/analyze/writing", json={"sample": sample})
        if result: st.markdown(result["analysis"])
