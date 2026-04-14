import streamlit as st
import pandas as pd
import io

from api_client import APIClient

st.set_page_config(page_title="Aqqrue — CSV Agent", layout="wide")

# Initialize
if "api" not in st.session_state:
    st.session_state.api = APIClient()
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "csv_loaded" not in st.session_state:
    st.session_state.csv_loaded = False
if "current_metadata" not in st.session_state:
    st.session_state.current_metadata = None

api: APIClient = st.session_state.api

# ─── Sidebar ───
with st.sidebar:
    st.title("Aqqrue")
    st.caption("AI-powered CSV processor for accountants")

    # Upload CSV
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file and not st.session_state.csv_loaded:
        with st.spinner("Creating session & uploading..."):
            try:
                session_id = api.create_session()
                st.session_state.session_id = session_id
                result = api.upload_csv(
                    session_id, uploaded_file.getvalue(), uploaded_file.name
                )
                st.session_state.csv_loaded = True
                st.session_state.current_metadata = result.get("metadata")
                st.session_state.messages = []
                st.success(f"Uploaded: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    # Actions
    if st.session_state.csv_loaded:
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇ Download CSV", use_container_width=True):
                try:
                    csv_bytes = api.download_csv(st.session_state.session_id)
                    st.download_button(
                        "Save file",
                        csv_bytes,
                        file_name="output.csv",
                        mime="text/csv",
                    )
                except Exception as e:
                    st.error(str(e))
        with col2:
            if st.button("↩ Undo", use_container_width=True):
                try:
                    result = api.undo(st.session_state.session_id)
                    if result["success"]:
                        st.session_state.current_metadata = result.get("metadata")
                        st.session_state.messages.append(
                            {"role": "assistant", "content": result["message"]}
                        )
                        st.rerun()
                    else:
                        st.warning(result["message"])
                except Exception as e:
                    st.error(str(e))

        # Version info
        if st.session_state.current_metadata:
            meta = st.session_state.current_metadata
            st.divider()
            st.markdown(f"**Version:** v{meta.get('version', 0)}")
            st.markdown(f"**Rows:** {meta.get('rows', '?')}")
            st.markdown(f"**Columns:** {len(meta.get('columns', []))}")

        # History
        if st.button("📋 Show History", use_container_width=True):
            try:
                history = api.get_history(st.session_state.session_id)
                for v in history.get("versions", []):
                    st.text(f"v{v['version']}: {v['operation']}")
            except Exception as e:
                st.error(str(e))

        # New session
        st.divider()
        if st.button("🆕 New Session", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.csv_loaded = False
            st.session_state.messages = []
            st.session_state.current_metadata = None
            st.rerun()

# ─── Main Area ───
if not st.session_state.csv_loaded:
    st.markdown("## Welcome to Aqqrue")
    st.markdown(
        "Upload a CSV file in the sidebar to get started. Then tell me what changes you'd like to make."
    )
    st.stop()

# Show current CSV preview
if st.session_state.current_metadata:
    meta = st.session_state.current_metadata
    with st.expander("📊 Current CSV Preview", expanded=False):
        if meta.get("sample_rows"):
            st.dataframe(pd.DataFrame(meta["sample_rows"]), use_container_width=True)

# Chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("preview"):
            preview = msg["preview"]
            if preview.get("sample_after"):
                st.caption("Preview (after change):")
                st.dataframe(
                    pd.DataFrame(preview["sample_after"]), use_container_width=True
                )

# Chat input
if prompt := st.chat_input("Describe the change you want to make..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Working on it..."):
            try:
                result = api.chat(st.session_state.session_id, prompt)
                response_text = result.get("response", "Done.")
                st.markdown(response_text)

                preview = result.get("preview")
                if preview and preview.get("sample_after"):
                    st.caption("Preview (after change2):")
                    st.dataframe(
                        pd.DataFrame(preview["sample_after"]), use_container_width=True
                    )

                # Update metadata
                if result.get("metadata"):
                    st.session_state.current_metadata = result["metadata"]

                # Store message
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response_text,
                        "preview": preview,
                    }
                )

                if result.get("error"):
                    st.error(result["error"])

            except Exception as e:
                error_msg = f"Error: {e}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
