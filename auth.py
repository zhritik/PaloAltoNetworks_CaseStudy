# Vault setup, unlock, lock, passphrase UI.
import streamlit as st

import crypto
import db

TEST_PLAINTEXT = "journal-companion-ok"


def setup_vault(passphrase: str) -> None:
    existing = db.get_vault()
    if existing:
        raise ValueError("Passphrase already set.")
    salt = crypto.generate_salt()
    key = crypto.derive_key(passphrase, salt)
    ciphertext, iv = crypto.encrypt(TEST_PLAINTEXT, key)
    db.set_vault({
        "id": "vault",
        "salt": crypto.salt_to_b64(salt),
        "testCipher": ciphertext,
        "testIv": iv,
    })
    crypto.set_key(key)


def unlock_vault(passphrase: str) -> None:
    v = db.get_vault()
    if not v:
        raise ValueError("Set a passphrase first.")
    salt = crypto.b64_to_salt(v["salt"])
    key = crypto.derive_key(passphrase, salt)
    crypto.decrypt(v["testCipher"], v["testIv"], key)
    crypto.set_key(key)


def reset_vault() -> None:
    db.delete_vault()
    crypto.clear_key()


def render_set_passphrase() -> None:
    st.markdown("### Set a passphrase")
    st.markdown(
        "Your data is encrypted and secure. Only you can read it—use a passphrase only you know."
    )
    with st.form("set_passphrase"):
        p1 = st.text_input(
            "Passphrase", type="password", placeholder="At least 8 characters", key="set_p1"
        )
        p2 = st.text_input(
            "Confirm passphrase", type="password", placeholder="Confirm passphrase", key="set_p2"
        )
        submitted = st.form_submit_button("Set passphrase")
        if submitted:
            if len(p1) < 8:
                st.error("Passphrase must be at least 8 characters.")
            elif p1 != p2:
                st.error("Passphrases do not match.")
            else:
                try:
                    setup_vault(p1)
                    st.session_state.has_vault = True
                    st.session_state.unlocked = True
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def render_unlock() -> None:
    st.markdown("### Unlock your journal")
    st.markdown("Enter your passphrase to continue.")
    with st.form("unlock"):
        p = st.text_input(
            "Passphrase", type="password", placeholder="Enter passphrase", key="unlock_p"
        )
        submitted = st.form_submit_button("Unlock")
        if submitted and p.strip():
            try:
                unlock_vault(p)
                st.session_state.unlocked = True
                st.rerun()
            except Exception as e:
                st.error(str(e))
