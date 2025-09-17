import streamlit as st
import requests
from typing import List, Dict, Any

# ---- Required secrets ----
# SUPABASE_URL       = "https://<PROJECT-REF>.supabase.co"
# EDGE_BASE_URL      = "https://<PROJECT-REF>.supabase.co/functions/v1"
# (no DEFAULT_REGION needed; region is auto-detected from ACP)

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")

# Display logo at the top
st.image("ACP Pennsylvania Chapter Logo rgb_noBkgrnd.png", width=400)
EDGE_BASE_URL = st.secrets.get("EDGE_BASE_URL", "")

st.set_page_config(page_title="PA‑ACP Voting", layout="centered")
st.title("PA‑ACP Council Voting")

if not EDGE_BASE_URL:
    st.error("Missing EDGE_BASE_URL in Streamlit secrets.")
    st.stop()

# --- Region banner (auto-detected) ---
if st.session_state.get("region"):
    REGION_NAMES = {"WEST": "West", "SOUTHEAST": "Southeast", "EAST": "East"}
    pretty = REGION_NAMES.get(st.session_state["region"], st.session_state["region"])  # fallback to raw code
    st.success(f"Recognized region: **{pretty}**", icon="🌎")

# Session state
ss = st.session_state
ss.setdefault("token", None)
ss.setdefault("region", None)
ss.setdefault("resume_code", "")
ss.setdefault("draft_ids", [])

# ---- small helpers ----

def api_get(path: str, params: Dict[str, Any] | None = None):
    url = f"{EDGE_BASE_URL}/{path}"
    return requests.get(url, params=params, timeout=30)

def api_post(path: str, payload: Dict[str, Any]):
    url = f"{EDGE_BASE_URL}/{path}"
    headers = {"Content-Type": "application/json"}
    return requests.post(url, json=payload, headers=headers, timeout=45)

REGION_NAMES = {"WEST": "West", "SOUTHEAST": "Southeast", "EAST": "East"}
ALL_REGIONS = ["WEST", "SOUTHEAST", "EAST"]

@st.cache_data(ttl=120)
def fetch_candidates(region: str):
    r = api_get("public_candidates", {"region": region})
    if not r.ok:
        return []
    return r.json()

# ---- Resume block (auto-detect region) ----
with st.expander("Returning to complete your vote? Click here to enter your ACP Member ID and the resume code from your last session", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        acp_resume = st.text_input("ACP number", value="", type="default")
    with col2:
        resume_code = st.text_input("Resume code", value=ss.resume_code, max_chars=12)
    if st.button("Resume session"):
        ok = False
        last_reason = None
        for reg in ALL_REGIONS:
            payload = {"acp": acp_resume.strip(), "resume_code": resume_code.strip(), "region": reg}
            r = api_post("resume_with_code", payload)
            data = r.json() if r.text else {"ok": False}
            if r.ok and data.get("ok"):
                ss.token = data.get("token")
                ss.draft_ids = data.get("draft", [])
                ss.resume_code = resume_code.strip()
                ss.region = data.get("region", reg)
                ok = True
                break
            else:
                last_reason = data.get("reason") or data.get("error")
        if ok:
            st.success(f"Session resumed for region **{REGION_NAMES.get(ss.region, ss.region)}**.")
        else:
            st.error(last_reason or "Could not resume. Check your code.")

# ---- Step 1: Validate (auto-detect region from ACP) ----
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
            # Try all regions until one matches this ACP
            success = False
            last_reason = None
            for reg in ALL_REGIONS:
                r = api_post("validate_acp", {"acp": acp.strip(), "region": reg})
                data = r.json() if r.text else {"ok": False}
                if r.ok and data.get("ok"):
                    ss.token = data.get("token")
                    ss.draft_ids = data.get("draft", [])
                    ss.resume_code = data.get("resume_code", "")
                    ss.region = data.get("region", reg)
                    st.success(f"Validated for region **{REGION_NAMES.get(ss.region, ss.region)}**. Your session is active.")
                    if ss.resume_code:
                        st.info(f"Your resume code: **{ss.resume_code}** (save this if you need to come back)")
                    success = True
                    break
                else:
                    last_reason = data.get("reason") or data.get("error")
            if not success:
                if last_reason == "already_voted":
                    st.error("Our records show you have already submitted a ballot.")
                elif last_reason == "not_eligible":
                    st.error("We could not find an eligible voter record for this ACP number.")
                else:
                    st.error(last_reason or "Validation failed.")

# ---- Step 2: Candidates ----
st.subheader("2) Review candidates and choose up to 3")
if not ss.token or not ss.region:
    st.info("Validate first to begin voting.")
else:
    st.caption(f"Region: **{REGION_NAMES.get(ss.region, ss.region)}**")
    candidates = fetch_candidates(ss.region)
    if not candidates:
        st.warning("No candidates available for this region yet.")
    else:
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

        chosen_list = list(chosen)
        if len(chosen_list) > 3:
            st.error("You can select at most 3 candidates. Uncheck some choices.")

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
                        ss.region = None
                    else:
                        st.error(data.get("reason") or data.get("error") or "Could not submit your vote.")

st.caption("If you close this page before submitting, use your resume code above to continue later.")


