# Dear Diary — entry point: config, CSS, auth, tab routing.
import streamlit as st
from datetime import datetime
from pathlib import Path

import auth
import crypto
import db

APP_NAME = "Dear Diary"
TAGLINE = "A personal AI journaling companion"
FOOTER_TEXT = "Your data is encrypted and secure. Only you can read it."
NAV_TABS = ["Journal", "Insights", "Reflection", "Settings"]

st.set_page_config(
    page_title=APP_NAME,
    page_icon="📔",
    layout="centered",
    initial_sidebar_state="collapsed",
)
_css_path = Path(__file__).resolve().parent / "styles.css"
if _css_path.exists():
    st.markdown(f"<style>\n{_css_path.read_text()}\n</style>", unsafe_allow_html=True)

if "db_inited" not in st.session_state:
    db.init_db()
    st.session_state.db_inited = True

if "has_vault" not in st.session_state:
    st.session_state.has_vault = None
if "unlocked" not in st.session_state:
    st.session_state.unlocked = False
if "page" not in st.session_state:
    st.session_state.page = "Journal"
if "entries_changed" not in st.session_state:
    st.session_state.entries_changed = 0


# --- Helpers ---

def _load_has_vault():
    st.session_state.has_vault = db.get_vault() is not None


def _load_write_dates():
    st.session_state.write_dates = db.get_write_dates()
    dates = st.session_state.write_dates
    if not dates:
        st.session_state.streak = 0
        return
    date_set = set(dates)
    today_start = db.get_day_start_ms(int(datetime.now().timestamp() * 1000))
    yesterday_start = today_start - db.MS_DAY_MS
    if today_start in date_set:
        end_day = today_start
    elif yesterday_start in date_set:
        end_day = yesterday_start
    else:
        st.session_state.streak = 0
        return
    count = 0
    t = end_day
    while t in date_set:
        count += 1
        t -= db.MS_DAY_MS
    st.session_state.streak = count


def _refresh_write_dates_if_needed():
    if st.session_state.get("entries_changed", 0) > 0:
        _load_write_dates()
        st.session_state.entries_changed = 0


if st.session_state.has_vault is None:
    _load_has_vault()
if "write_dates" not in st.session_state:
    _load_write_dates()
_refresh_write_dates_if_needed()

streak = st.session_state.get("streak", 0)


def _render_header(with_nav=True):
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.markdown(f"# {APP_NAME}")
        st.markdown(f'<p class="tagline">{TAGLINE}</p>', unsafe_allow_html=True)
    with top_col2:
        streak_col, lock_col = st.columns([1, 1])
        with streak_col:
            st.markdown(f"**🔥 {streak}**")
        with lock_col:
            if st.button("🔒 Lock", key="lock_btn"):
                crypto.clear_key()
                st.session_state.unlocked = False
                st.rerun()
    if with_nav:
        with st.container(key="nav_tabs"):
            tab_cols = st.columns(len(NAV_TABS))
            for i, tab in enumerate(NAV_TABS):
                with tab_cols[i]:
                    is_active = st.session_state.page == tab
                    if st.button(tab, key=f"nav_{tab}", type="primary" if is_active else "secondary"):
                        st.session_state.page = tab
                        st.rerun()
        st.markdown('<hr class="nav-tabs-separator" />', unsafe_allow_html=True)


def main():
    if st.session_state.has_vault is None:
        _load_has_vault()
        st.rerun()

    if not st.session_state.has_vault:
        st.markdown(f"# {APP_NAME}")
        st.markdown(f"**{TAGLINE}**")
        with st.container(key="auth_card"):
            auth.render_set_passphrase()
        st.caption(FOOTER_TEXT)
        return

    if not st.session_state.unlocked:
        st.markdown(f"# {APP_NAME}")
        st.markdown(f"**{TAGLINE}**")
        with st.container(key="auth_card"):
            auth.render_unlock()
        st.caption(FOOTER_TEXT)
        return

    _render_header()
    page = st.session_state.page
    if page == "Journal":
        from pages import journal
        journal.render()
    elif page == "Insights":
        from pages import insights
        insights.render()
    elif page == "Reflection":
        from pages import reflection
        reflection.render()
    else:
        from pages import settings
        settings.render()
    st.caption(FOOTER_TEXT)


if __name__ == "__main__":
    main()
