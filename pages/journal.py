# Journal tab: daily prompt and entry editor.
import streamlit as st
from datetime import datetime

import db
import llm
import sentiment


def render():
    entries = db.get_all_entries()
    today_start = db.get_day_start_ms(int(datetime.now().timestamp() * 1000))
    today_entry = next((e for e in entries if db.get_day_start_ms(e["createdAt"]) == today_start), None)

    ai_enabled = llm.get_use_ai() and bool(llm.get_server_api_key())
    today_reflection = llm.get_stored_reflection()
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    force_new = st.session_state.pop("prompt_force_new", 0) > 0
    display_prompt = llm.get_prompt(force_new=force_new)

    st.markdown("**Today's prompt**")
    st.info(display_prompt)
    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("Get another prompt"):
            st.session_state.prompt_force_new = 1
            st.rerun()

    # Entry text area
    st.markdown("**Your thoughts**")
    content_key = "journal_content_" + (today_entry["id"] if today_entry else "new")
    content = st.text_area(
        "Journal content",
        value=today_entry["content"] if today_entry else "",
        placeholder="Write freely—no one else will see this.",
        height=140,
        key=content_key,
        label_visibility="collapsed",
    )

    def _on_submit():
        trimmed = (content or "").strip()
        if not trimmed and not today_entry:
            return
        if today_entry:
            if not trimmed:
                db.delete_entry(today_entry["id"])
            else:
                sent_result = sentiment.analyze_sentiment(trimmed)
                themes = sentiment.extract_themes(trimmed)
                db.update_entry(
                    today_entry["id"],
                    {
                        "content": trimmed,
                        "sentimentScore": sent_result["score"],
                        "sentimentLabel": sent_result["label"],
                        "themes": themes,
                    },
                )
        elif trimmed:
            sent_result = sentiment.analyze_sentiment(trimmed)
            themes = sentiment.extract_themes(trimmed)
            db.create_entry(trimmed, {
                "sentimentScore": sent_result["score"],
                "sentimentLabel": sent_result["label"],
                "themes": themes,
            })
        st.session_state.entries_changed = st.session_state.get("entries_changed", 0) + 1
        st.rerun()

    btn_label = "Saving…"
    if today_entry and not (content or "").strip():
        btn_label = "Remove entry"
    elif today_entry:
        btn_label = "Update entry"
    else:
        btn_label = "Save entry"
    if st.button(btn_label, type="primary"):
        _on_submit()

    # auto-generate AI reflection when opening app
    if ai_enabled and entries and (not today_reflection or today_reflection.get("generatedDate") != today_date_str):
        if "generating_reflection" not in st.session_state:
            st.session_state.generating_reflection = False
        if not st.session_state.generating_reflection:
            start_ms, end_ms = llm.get_period_range("week")
            in_range = [e for e in entries if start_ms <= e["createdAt"] <= end_ms]
            if in_range:
                st.session_state.generating_reflection = True
                try:
                    result = llm.generate_reflection_with_llm(in_range)
                    llm.set_stored_reflection(result)
                    st.session_state.generating_reflection = False
                    st.rerun()
                except Exception as e:
                    st.session_state.generating_reflection = False
                    st.error(str(e))
