import streamlit as st
import pandas as pd
import requests
from io import StringIO

st.set_page_config(page_title="PA-ACP Admin Dashboard", layout="wide")

# --- Secrets ---
ADMIN_API_KEY = st.secrets.get("ADMIN_API_KEY", "")
EDGE_BASE_URL = st.secrets.get("EDGE_BASE_URL", "")

# --- Consistent header ---
def render_header(title: str):
    col1, col2 = st.columns([1, 5], vertical_alignment="center")
    with col1:
        st.image("assets/ACP_PA_Chapter_Logo.png", width=300)
    with col2:
        st.markdown(
            f"<div style='padding-top:6px'><h1 style='margin:0'>{title}</h1></div>",
            unsafe_allow_html=True,
        )

render_header("PA-ACP Admin Dashboard")

# --- Admin login gate ---
LOGIN_KEY = "admin_authed"
PORTAL_PASS = st.secrets.get("ADMIN_PORTAL_PASS", "")

if not st.session_state.get(LOGIN_KEY, False):
    st.header("Administrator Login")
    pw = st.text_input("Enter admin passphrase", type="password", key="admin_pw")
    if st.button("Unlock"):
        if PORTAL_PASS and pw == PORTAL_PASS:
            st.session_state[LOGIN_KEY] = True
            st.success("Access granted.")
            st.rerun()   # ensure the dashboard renders
        else:
            st.error("Incorrect passphrase.")
    st.stop()

if not ADMIN_API_KEY or not EDGE_BASE_URL:
    st.error("Missing secrets. Please set ADMIN_API_KEY and EDGE_BASE_URL in Streamlit secrets.")
    st.stop()

# --- Sidebar ---
regions = ["WEST", "SOUTHEAST", "EAST"]

with st.sidebar:
    if st.button("Lock admin"):
        st.session_state.pop(LOGIN_KEY, None)
        st.rerun()

    st.header("Admin Help")
    st.markdown(
        """
**For Admins**

**Admin Dashboard**
- **Upload Registry**: CSV with `RegionCode` (PAW/PAS/PAE), `CustomerID`, `Email`, `MemberStatus`.
  - **Sync mode** (optional): marks anyone **not** in the uploaded file as **ineligible** for the regions present.
- **Non-Voters**: list/download of eligible members who haven’t voted yet (per region).
- **Live Tallies**: real-time vote totals per candidate (per region).

**Opening / Closing Voting**
- **Open**: upload final registry (optionally with **Sync**), verify counts, then announce the voting link.
- **Close**: stop accepting submissions and export tallies.
        """
    )

    st.subheader("Region")
    region = st.selectbox("Select region", regions, index=0)

# Small helper to call admin endpoints with Authorization header
def admin_get(path: str, params: dict | None = None):
    url = f"{EDGE_BASE_URL}/{path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {ADMIN_API_KEY}"}, params=params, timeout=60)
    return resp

def admin_post(path: str, json_body: dict):
    url = f"{EDGE_BASE_URL}/{path}"
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {ADMIN_API_KEY}",
        "Content-Type": "application/json",
    }, json=json_body, timeout=120)
    return resp

st.sidebar.markdown("**Edge Base URL:**")
st.sidebar.code(EDGE_BASE_URL)

# Tabs for core admin actions
upload_tab, nonvoters_tab, tallies_tab = st.tabs(["Upload Registry", "Non‑voters", "Live tallies"]) 

# --- Upload Registry ---
with upload_tab:
    st.subheader("Upload consolidated membership CSV → voter_registry")
    st.caption("File must include columns: RegionCode (PAW/PAS/PAE), CustomerID, Email, MemberStatus.")

    file = st.file_uploader("Select CSV or Excel", type=["csv", "xlsx"])
    strict = st.checkbox("Strict parsing (fail on malformed rows)", value=False)
    sync = st.checkbox("Sync mode: mark anyone NOT in the file as ineligible (per region present in upload)", value=False)

    def read_table(uploaded_file) -> pd.DataFrame:
        import io, csv
        name = uploaded_file.name.lower()

        # Read raw bytes once so we can retry parsers
        raw = uploaded_file.read()
        uploaded_file.seek(0)

        # Excel path
        if name.endswith(".xlsx"):
            return pd.read_excel(io.BytesIO(raw), dtype=str)

        # CSV path (try fast engine first)
        try:
            return pd.read_csv(io.BytesIO(raw), dtype=str)
        except Exception as e1:
            # Lenient fallback: python engine + explicit quoting + skip bad lines (if not strict)
            try:
                return pd.read_csv(
                    io.BytesIO(raw),
                    dtype=str,
                    engine="python",
                    sep=",",
                    quotechar='"',
                    escapechar="\\",
                    skipinitialspace=True,
                    on_bad_lines=("error" if strict else "skip"),
                )
            except Exception as e2:
                raise RuntimeError(f"CSV parse failed.\nFast parser: {e1}\nLenient parser: {e2}")

    if file is not None:
        try:
            df = read_table(file)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        # Show shape + preview
        st.write(f"Parsed rows: **{len(df):,}**, columns: **{len(df.columns)}**")
        st.dataframe(df.head(50), use_container_width=True)

        required = {"RegionCode", "CustomerID"}
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"Missing required column(s): {missing}")
        else:
            # Ensure optional columns exist
            for col in ["Email", "MemberStatus"]:
                if col not in df.columns:
                    df[col] = ""

            rows = (
                df[["RegionCode", "CustomerID", "Email", "MemberStatus"]]
                .fillna("")
                .to_dict(orient="records")
            )

            if st.button("Upsert now", type="primary"):
                with st.spinner("Uploading to Supabase…"):
                    r = admin_post("admin_upsert_registry", {"rows": rows, "sync": sync})
                st.code(r.text, language="json")
                if r.ok:
                    st.success("Registry updated successfully.")
                else:
                    st.error("Upload failed. See response above.")

# --- Non‑voters ---
with nonvoters_tab:
    st.subheader("Download non‑voters (eligible but has_voted = false)")
    if st.button("Fetch non‑voters"):
        with st.spinner("Querying…"):
            r = admin_get("non_voters", params={"region": region})
        if r.ok:
            data = r.json().get("non_voters", [])
            if not data:
                st.info("No non‑voters found for this region.")
            else:
                df_nv = pd.DataFrame(data)
                st.dataframe(df_nv, use_container_width=True)
                csv = df_nv.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", csv, file_name=f"non_voters_{region}.csv", mime="text/csv")
        else:
            st.error(f"Error: {r.status_code}")
            st.code(r.text, language="json")

# --- Live tallies ---
with tallies_tab:
    st.subheader("Live tallies by candidate")
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Refresh tallies"):
            with st.spinner("Querying…"):
                r = admin_get("live_tallies", params={"region": region})
            if r.ok:
                tallies = r.json().get("tallies", [])
                if not tallies:
                    st.info("No tallies yet.")
                else:
                    df_t = pd.DataFrame(tallies)
                    st.dataframe(df_t, use_container_width=True)
            else:
                st.error(f"Error: {r.status_code}")
                st.code(r.text, language="json")
    with col2:
        st.caption("Tallies are computed from submitted ballots in real time.")

st.divider()
st.caption("Admin actions require a valid ADMIN_API_KEY. This dashboard does not store plaintext ACP numbers; hashing occurs in the Edge Function.")
