"""Streamlit router for the Vadesiz demo."""
import streamlit as st

import db
import fraud
import ui
import views.denetim
import views.finansor
import views.kobi
from views.common import _request_metadata


def main():
    st.set_page_config(page_title="Vadesiz", page_icon="\U0001F9FE", layout="wide")
    ui.apply_styles()
    db.init_db()
    user = st.session_state.get("authenticated_user")
    ip_address, _ = _request_metadata()
    if not user:
        ui.render_topbar()
        authenticated_user = ui.render_login(db.authenticate_user, ip_address)
        if authenticated_user:
            st.session_state["authenticated_user"] = authenticated_user
            st.rerun()
        ui.render_footer()
        return

    if ui.render_topbar(user):
        db.logout_user(user, ip_address)
        st.session_state.pop("authenticated_user", None)
        st.rerun()

    st.caption("KOB\u0130'ler i\u00e7in fatura finansman\u0131 \u2022 Yerel yapay zek\u00e2 ile demo")
    companies, invoices = fraud.load_demo_data()
    if user["role"] == "finansor":
        ui.market_styles()
        views.finansor.render(user, companies, invoices, ip_address)
        ui.render_footer()
        return
    if user["role"] == "denetim":
        ui.market_styles()
        views.denetim.render(user, companies, invoices, ip_address)
        ui.render_footer()
        return

    ui.kobi_styles()
    views.kobi.render(user, companies, invoices, ip_address)
    ui.render_footer()


if __name__ == "__main__":
    main()
