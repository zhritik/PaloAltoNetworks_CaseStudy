# Reflection tab: AI (Diary) week-in-reflection.
import streamlit as st
from datetime import datetime

import db
import llm


def render():
    entries = db.get_all_entries()
    ai_enabled = llm.get_use_ai() and bool(llm.get_server_api_key())
    stored = llm.get_stored_reflection()

    if ai_enabled:
        st.markdown("### Your week in reflection by your Diary")
        if stored:
            st.caption(f"Generated {datetime.fromtimestamp(stored['generatedAt']/1000.0).strftime('%B %d, %Y')}")
            st.write(stored["reflection"])

        if st.button("Regenerate (last 7 days)" if stored else "Generate reflection (last 7 days)", key="ai_generate"):
            start_ms, end_ms = llm.get_period_range("week")
            in_range = [e for e in entries if start_ms <= e["createdAt"] <= end_ms]
            if not in_range:
                st.error("No entries in the last 7 days. Write a few journal entries first.")
            else:
                with st.spinner("Generating…"):
                    try:
                        result = llm.generate_reflection_with_llm(in_range)
                        llm.set_stored_reflection(result)
                        st.success("Reflection generated.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
    else:
        st.markdown("### Your week in reflection by your Diary")
        st.caption(
            "Enable **Use AI** in **Settings** to get reflections from Diary for your last 7 days. "
            "When enabled, your entries are sent to the server to generate the reflection and journal prompts. "
            "When AI is enabled, your data can be read by OpenAI."
        )
