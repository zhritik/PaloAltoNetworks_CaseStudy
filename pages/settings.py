# Settings tab: AI toggle, export/import, data reset.
import json
import streamlit as st
from datetime import datetime

import auth
import db
import llm
import sentiment


def _export_entries(entries):
    out = []
    for e in entries:
        out.append({
            "id": e.get("id"),
            "content": e.get("content", ""),
            "createdAt": e.get("createdAt"),
            "sentimentScore": e.get("sentimentScore"),
            "sentimentLabel": e.get("sentimentLabel"),
            "themes": e.get("themes") or [],
        })
    return json.dumps(out, indent=2)


def render():
    st.markdown("### Settings")
    st.caption("App and data options.")

    st.markdown("### AI")
    st.caption("When enabled, AI reflections and journal prompts use the server. Entries are sent for generation. When AI is enabled, your data can be read by OpenAI.")
    use_ai = st.toggle("Use AI", value=llm.get_use_ai(), key="use_ai_toggle")
    if use_ai != llm.get_use_ai():
        llm.set_use_ai(use_ai)
        st.rerun()

    st.markdown("### Export your data")
    st.caption("Download all entries as JSON. Encrypted—only you can read it.")
    entries = db.get_all_entries()
    if st.button("Export as JSON", key="export_btn", disabled=not entries):
        data = _export_entries(entries)
        st.download_button(
            "Download JSON",
            data=data,
            file_name=f"journal-export-{datetime.now().strftime('%Y-%m-%d')}.json",
            mime="application/json",
            key="download_export",
        )

    st.markdown("### Import data")
    st.caption("Import from a previously exported JSON. Same date: content is merged below.")
    uploaded = st.file_uploader("Choose a JSON file", type=["json"], key="import_file")
    if uploaded and st.button("Import from JSON", key="import_btn"):
        try:
            text = uploaded.read().decode("utf-8")
            data = json.loads(text)
            list_data = data if isinstance(data, list) else []
            if not list_data:
                st.warning("No entries found in file.")
            else:
                existing = db.get_all_entries()
                day_to_entry = {}
                for e in existing:
                    day = db.get_day_start_ms(e["createdAt"])
                    if day not in day_to_entry:
                        day_to_entry[day] = e
                imported = 0
                for item in list_data:
                    content = (item.get("content") or "").strip()
                    created_at = item.get("createdAt") or int(datetime.now().timestamp() * 1000)
                    if not content:
                        continue
                    day = db.get_day_start_ms(created_at)
                    existing_entry = day_to_entry.get(day)
                    if existing_entry:
                        if (existing_entry.get("content") or "").strip() == content:
                            continue
                        merged = (existing_entry.get("content") or "").strip() + "\n\n" + content
                        sent_result = sentiment.analyze_sentiment(merged)
                        themes = sentiment.extract_themes(merged)
                        db.update_entry(existing_entry["id"], {
                            "content": merged,
                            "sentimentScore": sent_result["score"],
                            "sentimentLabel": sent_result["label"],
                            "themes": themes,
                        })
                        day_to_entry[day] = {**existing_entry, "content": merged}
                    else:
                        sent_result = sentiment.analyze_sentiment(content)
                        themes = sentiment.extract_themes(content)
                        new_entry = db.insert_entry({
                            "content": content,
                            "createdAt": created_at,
                            "sentimentScore": sent_result["score"],
                            "sentimentLabel": sent_result["label"],
                            "themes": themes,
                        })
                        day_to_entry[day] = new_entry
                    imported += 1
                st.session_state.entries_changed = st.session_state.get("entries_changed", 0) + 1
                st.success(f"Imported {imported} entries.")
                st.rerun()
        except Exception as e:
            st.error(str(e))

    st.markdown("### Delete all data")
    st.caption("Permanently delete all entries. Export before deletion. This cannot be undone.")
    if "delete_confirm" not in st.session_state:
        st.session_state.delete_confirm = False
    if st.button("Delete all data", key="delete_btn", disabled=not entries):
        st.session_state.delete_confirm = True
    if st.session_state.delete_confirm:
        st.warning("Export your data and then permanently delete all entries?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, export and delete", key="delete_confirm_btn"):
                data = _export_entries(db.get_all_entries())
                db.clear_all_entries()
                llm.clear_all_llm_keys()
                llm.clear_stored_reflections()
                auth.reset_vault()
                st.session_state.has_vault = False
                st.session_state.unlocked = False
                st.session_state.delete_confirm = False
                st.session_state.entries_changed = 0
                st.success("All data deleted. Download your export below if you haven't.")
                st.download_button("Download backup", data=data, file_name=f"journal-backup-{datetime.now().strftime('%Y-%m-%d')}.json", mime="application/json", key="backup_dl")
                st.rerun()
        with col2:
            if st.button("Cancel", key="delete_cancel"):
                st.session_state.delete_confirm = False
                st.rerun()
