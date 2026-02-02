# Insights tab: calendar, day popup, recurring themes.
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from calendar import monthrange

import db
import sentiment

EMOJI = {"positive": "☺️", "neutral": "😐", "negative": "☹️"}


def _day_sentiments(entries):
    out = {}
    for e in entries:
        day_ms = db.get_day_start_ms(e["createdAt"])
        if day_ms not in out:
            out[day_ms] = e.get("sentimentLabel") or "neutral"
    return out


def _render_calendar(write_dates, day_sentiments, month_start, on_month, on_day):
    write_set = set(write_dates)
    dt = datetime.fromtimestamp(month_start / 1000.0)
    y, m = dt.year, dt.month
    pad = (datetime(y, m, 1).weekday() + 1) % 7
    _, ndays = monthrange(y, m)
    st.markdown(f"**{dt.strftime('%B %Y')}**")
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("← Previous month", key="cal_prev"):
            prev = datetime(y, m, 1) - timedelta(days=1)
            on_month(int(datetime(prev.year, prev.month, 1).timestamp() * 1000))
    with col_next:
        if st.button("Next month →", key="cal_next"):
            nxt = datetime(y, m + 1, 1) if m < 12 else datetime(y + 1, 1, 1)
            on_month(int(nxt.timestamp() * 1000))
    weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    header_cols = st.columns(7)
    for i, wd in enumerate(weekdays):
        with header_cols[i]:
            st.markdown(f'<p class="insights-cal-weekday">{wd}</p>', unsafe_allow_html=True)
    cells = [None] * pad
    for d in range(1, ndays + 1):
        cell_dt = datetime(y, m, d)
        cells.append((d, int(cell_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)))
    while len(cells) % 7:
        cells.append(None)
    for i in range(0, len(cells), 7):
        row, cols = cells[i:i + 7], st.columns(7)
        for j, cell in enumerate(row):
            with cols[j]:
                if cell is None:
                    st.write("")
                else:
                    day_num, day_ms = cell
                    lbl = day_sentiments.get(day_ms)
                    em = EMOJI.get(lbl, "") if lbl else ""
                    if st.button(f"{day_num} {em}".strip(), key=f"cal_{day_ms}"):
                        on_day(day_ms)
                        st.rerun()


def _render_day_popup(day_ms, on_close, on_prev, on_next):
    entries_list = db.get_entries_by_date_range(day_ms, day_ms + db.MS_DAY_MS - 1)
    entry = entries_list[0] if entries_list else None
    key_suffix = str(day_ms)
    day_str = datetime.fromtimestamp(day_ms / 1000.0).strftime("%A, %B %d, %Y")

    st.markdown(f"### {day_str}")
    if st.button("× Close", key=f"close_{key_suffix}"):
        on_close()
        st.rerun()

    if not entry:
        st.markdown("No entry for this day. Add one below.")
        content = st.text_area("Entry content", key=f"new_{key_suffix}", height=160, placeholder="What happened that day?")
        if st.button("Add entry", key=f"add_{key_suffix}") and (content or "").strip():
            sent_result = sentiment.analyze_sentiment(content.strip())
            themes = sentiment.extract_themes(content.strip())
            db.insert_entry({
                "content": content.strip(),
                "createdAt": day_ms,
                "sentimentScore": sent_result["score"],
                "sentimentLabel": sent_result["label"],
                "themes": themes,
            })
            st.session_state.entries_changed = st.session_state.get("entries_changed", 0) + 1
            on_close()
            st.rerun()
    else:
        content = st.text_area("Entry content", value=entry["content"], key=f"edit_{key_suffix}", height=160)
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("Save", key=f"save_{key_suffix}"):
                if (content or "").strip() and content.strip() != entry.get("content", ""):
                    sent_result = sentiment.analyze_sentiment(content.strip())
                    themes = sentiment.extract_themes(content.strip())
                    db.update_entry(entry["id"], {
                        "content": content.strip(),
                        "sentimentScore": sent_result["score"],
                        "sentimentLabel": sent_result["label"],
                        "themes": themes,
                    })
                    st.session_state.entries_changed = st.session_state.get("entries_changed", 0) + 1
                st.rerun()
        with btn_col2:
            if st.button("Remove entry", key=f"rm_{key_suffix}"):
                db.delete_entry(entry["id"])
                st.session_state.entries_changed = st.session_state.get("entries_changed", 0) + 1
                on_close()
                st.rerun()

    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("← Previous day", key=f"prev_{key_suffix}"):
            on_prev()
            st.rerun()
    with nav_col2:
        if st.button("Next day →", key=f"next_{key_suffix}"):
            on_next()
            st.rerun()


def render():
    write_dates = db.get_write_dates()
    entries = db.get_all_entries()
    day_sentiments = _day_sentiments(entries)

    if "insights_month_start" not in st.session_state:
        now = datetime.now()
        st.session_state.insights_month_start = int(datetime(now.year, now.month, 1).timestamp() * 1000)
    if "insights_selected_day" not in st.session_state:
        st.session_state.insights_selected_day = None

    st.markdown("### Entries by day")
    st.caption("Click a date to view or edit that day's entry.")

    def on_month_change(ms):
        st.session_state.insights_month_start = ms
        st.rerun()

    def on_day_click(ms):
        st.session_state.insights_selected_day = ms
        st.rerun()

    def on_close():
        st.session_state.insights_selected_day = None
        st.rerun()

    _render_calendar(write_dates, day_sentiments, st.session_state.insights_month_start, on_month_change, on_day_click)

    selected = st.session_state.insights_selected_day
    if selected is not None:
        st.markdown("---")
        _render_day_popup(
            selected,
            on_close,
            lambda: setattr(st.session_state, "insights_selected_day", selected - db.MS_DAY_MS),
            lambda: setattr(st.session_state, "insights_selected_day", selected + db.MS_DAY_MS),
        )

    st.markdown("### Recurring themes")
    st.caption("Topics that appear often. Top 5 below.")
    theme_data = sentiment.aggregate_themes(entries)[:5]
    if theme_data:
        st.bar_chart(pd.DataFrame(theme_data).set_index("theme"), y="count", x_label="Theme", y_label="Count")
    else:
        st.caption("Write more entries to see themes here.")
