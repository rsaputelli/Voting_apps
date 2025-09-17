import streamlit as st
import requests
from typing import List, Dict, Any

# ---- Required secrets ----
# SUPABASE_URL       = "https://<PROJECT-REF>.supabase.co"
# EDGE_BASE_URL      = "https://<PROJECT-REF>.supabase.co/functions/v1"
# DEFAULT_REGION     = "WEST"  # or SOUTHEAST / EAST per app

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
EDGE_BASE_URL = st.secrets.get("EDGE_BASE_URL", "")
DEFAULT_REGION = st.secrets.get("DEFAULT_REGION", "WEST")

st.set_page_config(page_title="PA‑ACP Voting", layout="centered")
st.title("PA‑ACP Council Voting")

if not EDGE_BASE_URL:
    st.error("Missing EDGE_BASE_URL in Streamlit secrets.")
    st.stop()

# Session state
ss = st.session_state
if "token" not in ss: ss.token = None
if "region" not in ss: ss.region = DEFAULT_REGION
if "resume_code" not in ss: ss.resume_code = ""
if "draft_ids" not in ss: ss.draft_ids = []

# ---- small helpers ----

def api_get(path: str, params: Dict[str, Any] | None = None):
    url = f"{EDGE_BASE_URL}/{path}"
    return requests.get(url, params=params, timeout=30)

def api_post(path: str, payload: Dict[str, Any]):
    url = f"{EDGE_BASE_URL}/{path}"
    headers = {"Content-Type": "application/json"}
    return requests.post(url, json=payload, headers=headers, timeout=45)

@st.cache_data(ttl=120)
def fetch_candidates(region: str):
    r = api_get("public_candidates", {"region": region})
    if not r.ok:
        return []
    return r.json()

# ---- Steps UI ----

st.sidebar.header("Your Region")
ss.region = st.sidebar.selectbox("Select region", ["WEST", "SOUTHEAST", "EAST"],
                                 index=["WEST","SOUTHEAST","EAST"].index(ss.region))

with st.expander("Need to resume? Enter your ACP and resume code", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        acp_resume = st.text_input("ACP number", value="", type="default")
    with col2:
        resume_code = st.text_input("Resume code", value=ss.resume_code, max_chars=12)
    if st.button("Resume session"):
        payload = {"acp": acp_resume.strip(), "resume_code": resume_code.strip(), "region": ss.region}
        r = api_post("resume_with_code", payload)
        data = r.json() if r.text else {"ok": False}
        if r.ok and data.get("ok"):
            ss.token = data.get("token")
            ss.draft_ids = data.get("draft", [])
            ss.resume_code = resume_code.strip()
            st.success("Session resumed. You can review and submit your vote below.")
        else:
            st.error(data.get("error") or data.get("reason") or "Could not resume. Check your code and region.")

st.subheader("1) Validate yourself to vote")
col1, col2 = st.columns([2,1])
with col1:
    acp = st.text_input("Enter your ACP number", value="")
with col2:
    st.write("")
    if st.button("Validate"):
        if not acp.strip():
            st.warning("Please enter your ACP number.")
        else:
            r = api_post("validate_acp", {"acp": acp.strip(), "region": ss.region})
            data = r.json() if r.text else {"ok": False}
            if r.ok and data.get("ok"):
                ss.token = data.get("token")
                ss.draft_ids = data.get("draft", [])
                ss.resume_code = data.get("resume_code", "")
                st.success("Validated. Your session is active.")
                if ss.resume_code:
                    st.info(f"Your resume code: **{ss.resume_code}** (save this if you need to come back)")
            else:
                reason = data.get("reason") or data.get("error")
                if reason == "not_eligible":
                    st.error("We could not find an eligible voter record for this ACP number in your region.")
                elif reason == "already_voted":
                    st.error("Our records show you have already submitted a ballot.")
                else:
                    st.error(reason or "Validation failed.")

st.subheader("2) Review candidates and choose up to 3")
if not ss.token:
    st.info("Validate first to begin voting.")
else:
    candidates = fetch_candidates(ss.region)
    if not candidates:
        st.warning("No candidates available for this region yet.")
    else:
        # Build selection UI
        chosen = set(ss.draft_ids or [])
        for c in candidates:
            with st.container(border=True):
                st.markdown(f"**{c['name']}**")
                if c.get("bio"):
                    st.caption(c["bio"])
                if c.get("qa"):
                    with st.expander("Read Q&A"):
                        for qa in sorted(c["qa"], key=lambda x: x.get("sort_order", 999)):
                            st.markdown(f"**{qa['label']}**")
                            st.write(qa['answer'])
                checked = c["id"] in chosen
                new_val = st.checkbox("Select", value=checked, key=f"cand_{c['id']}")
                if new_val:
                    chosen.add(c["id"])
                else:
                    chosen.discard(c["id"])

        # Enforce max 3 locally
        chosen_list = list(chosen)
        if len(chosen_list) > 3:
            st.error("You can select at most 3 candidates. Uncheck some choices.")
        # Save draft
        save_col, submit_col = st.columns(2)
        with save_col:
            if st.button("Save draft"):
                r = api_post("save_draft", {"token": ss.token, "candidate_ids": chosen_list})
                data = r.json() if r.text else {}
                if r.ok and data.get("ok"):
                    ss.draft_ids = chosen_list
                    st.success("Draft saved.")
                else:
                    st.error(data.get("error") or "Could not save draft.")
        with submit_col:
            if st.button("Submit vote", type="primary"):
                if len(chosen_list) != 3:
                    st.error("Please select exactly 3 candidates before submitting.")
                else:
                    r = api_post("submit_vote", {"token": ss.token, "candidate_ids": chosen_list})
                    data = r.json() if r.text else {}
                    if r.ok and data.get("ok"):
                        st.success("Thank you! Your vote has been recorded.")
                        ss.token = None
                        ss.draft_ids = []
                    else:
                        st.error(data.get("reason") or data.get("error") or "Could not submit your vote.")

st.caption("If you close this page before submitting, use your resume code above to continue later.")
