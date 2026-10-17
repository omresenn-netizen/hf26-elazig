"""Shared light corporate styling and authentication UI."""
import html

import streamlit as st

import db

ROLE_TABS = (
    ("kobi", "KOBİ Girişi"),
    ("finansor", "Finansör Girişi"),
    ("denetim", "Denetim Girişi"),
)


def apply_styles():
    st.markdown(
        """
        <style>
        #MainMenu, footer, div[data-testid="stToolbar"],
        div[data-testid="stDecoration"], div[data-testid="stStatusWidget"],
        div[data-testid="stAppDeployButton"] { visibility: hidden; height: 0; }
        header[data-testid="stHeader"] { background: transparent; }
        .block-container { max-width: 1100px; padding-top: 1.5rem; padding-bottom: 1rem; }
        div[data-testid="stHorizontalBlock"]:has(.vadesiz-header-brand) {
            align-items: center;
            position: relative;
            z-index: 1;
            width: 100vw;
            margin-left: calc((100% - 100vw) / 2);
            padding: 14px max(24px, calc((100vw - 1100px) / 2));
            box-sizing: border-box;
            gap: 14px;
            background: #0B3D91;
            border-bottom: 3px solid #C8102E;
        }
        div[data-testid="stHorizontalBlock"]:has(.vadesiz-header-brand)::before {
            position: absolute;
            inset: 0;
            z-index: -1;
            content: "";
            background: #0B3D91;
        }
        .vadesiz-header-brand { color: #fff; font-size: 17px; font-weight: 700; white-space: nowrap; }
        .vadesiz-header-user { color: #fff; text-align: right; line-height: 1.35; }
        .vadesiz-role-badge {
            display: inline-block; margin-left: 8px; padding: 3px 9px; border-radius: 12px;
            color: #0B3D91; background: #fff; font-size: 12px; font-weight: 700;
        }
        div[data-testid="stHorizontalBlock"]:has(.vadesiz-header-brand) button {
            color: #fff; background: transparent; border: 1px solid #fff; border-radius: 6px;
        }
        div[data-testid="stHorizontalBlock"]:has(.vadesiz-header-brand) button:hover {
            color: #0B3D91; background: #fff; border-color: #fff;
        }
        h1, h2, h3 { color: #16345F; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid #E5E7EB; border-radius: 8px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, .05);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 24px; }
        .stButton > button, .stFormSubmitButton > button {
            border-radius: 6px; font-weight: 600;
        }
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
            color: #fff; background: #0B3D91; border-color: #0B3D91;
        }
        .stButton > button[kind="secondary"], .stFormSubmitButton > button[kind="secondary"] {
            color: #0B3D91; background: #fff; border-color: #0B3D91;
        }
        div[data-testid="stDataFrame"] thead tr th { background: #F4F6FA; }
        div[data-testid="stDataFrame"] tbody tr:nth-child(even) { background: #F8FAFC; }
        .vadesiz-login-mark { margin: 4px 0 2px; color: #0B3D91; font-size: 28px; font-weight: 800; }
        .vadesiz-login-subtitle { margin: 0 0 18px; color: #64748B; }
        .vadesiz-footer {
            margin: 36px 0 12px; color: #6B7280; text-align: center; font-size: 12px;
        }
        .vadesiz-audit-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .vadesiz-audit-table th { background: #F4F6FA; text-align: left; }
        .vadesiz-audit-table th, .vadesiz-audit-table td {
            border-bottom: 1px solid #E5E7EB; padding: 9px 10px; vertical-align: top;
        }
        .vadesiz-audit-table tbody tr:nth-child(even) { background: #F8FAFC; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar(user=None):
    brand, identity, exit_column = st.columns([0.67, 0.25, 0.08], vertical_alignment="center")
    with brand:
        st.markdown(
            '<div class="vadesiz-header-brand">VADESİZ · Fatura Finansman Platformu</div>',
            unsafe_allow_html=True,
        )
    with identity:
        if user:
            display_name = html.escape(user.get("display_name") or user["username"])
            role = html.escape(db.ROLE_LABELS[user["role"]])
            st.markdown(
                f'<div class="vadesiz-header-user">{display_name}'
                f'<span class="vadesiz-role-badge">{role}</span></div>',
                unsafe_allow_html=True,
            )
    with exit_column:
        return st.button("Çıkış", key="logout", use_container_width=True) if user else False


def render_login(authenticate, ip_address):
    left, center, right = st.columns([1, 2, 1])
    with center:
        with st.container(border=True):
            st.markdown('<div class="vadesiz-login-mark">VADESİZ</div>', unsafe_allow_html=True)
            st.markdown(
                '<p class="vadesiz-login-subtitle">Fatura finansman platformuna güvenli demo girişi</p>',
                unsafe_allow_html=True,
            )
            tabs = st.tabs([label for _, label in ROLE_TABS])
            authenticated_user = None
            for (role, label), tab in zip(ROLE_TABS, tabs):
                with tab:
                    with st.form(f"login_{role}", clear_on_submit=True):
                        username = st.text_input("Kullanıcı adı / VKN", key=f"username_{role}")
                        password = st.text_input(
                            "Şifre",
                            type="password",
                            key=f"password_{role}",
                        )
                        submitted = st.form_submit_button(
                            f"{label} yap",
                            type="primary",
                            use_container_width=True,
                        )
                    if submitted:
                        authenticated_user = authenticate(username, password, role, ip_address)
                        if not authenticated_user:
                            st.error("Giriş bilgileri geçersiz. Demo hesap bilgilerini kontrol edin.")
        with st.expander("Demo hesapları"):
            sme_users = db.list_users("kobi")
            st.markdown("**KOBİ** — tüm şirketler için kullanıcı adı VKN, şifre `demo1234`.")
            st.code("\n".join(user["username"] for user in sme_users))
            st.markdown(
                "**Finansör** — `anadolu_faktoring`, `firat_finans`, `harput_katilim`  \n"
                "**Denetim** — `denetim`  \n"
                "**Tüm demo hesaplarının şifresi:** `demo1234`"
            )
    return authenticated_user


def render_footer():
    st.markdown(
        '<div class="vadesiz-footer">Demo amaçlıdır · GİB, Findex, banka ve e-imza '
        "entegrasyonları mock'tur</div>",
        unsafe_allow_html=True,
    )


def market_styles():
    st.markdown(
        """
        <style>
        .market-table-wrap { overflow-x: auto; margin: 12px 0 20px; }
        .market-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .market-table th { background: #F4F6FA; color: #334155; text-align: left; }
        .market-table th, .market-table td {
            border-bottom: 1px solid #E5E7EB; padding: 11px 10px; vertical-align: top;
        }
        .market-table tbody tr:nth-child(even) { background: #F8FAFC; }
        .market-risk { display: inline-block; padding: 3px 9px; border-radius: 12px; font-weight: 700; }
        .market-risk-low { color: #166534; background: #DCFCE7; }
        .market-risk-medium { color: #9A3412; background: #FFEDD5; }
        .market-risk-high { color: #991B1B; background: #FEE2E2; }
        </style>
        """,
        unsafe_allow_html=True,
    )
