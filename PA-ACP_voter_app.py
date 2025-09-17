import streamlit as st
import requests
from typing import List, Dict, Any
st.set_page_config(page_title="PA-ACP Voting", layout="wide") 

# ---- Required secrets ----
# SUPABASE_URL       = "https://<PROJECT-REF>.supabase.co"
# EDGE_BASE_URL      = "https://<PROJECT-REF>.supabase.co/functions/v1"
# (no DEFAULT_REGION needed; region is auto-detected from ACP)

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
EDGE_BASE_URL = st.secrets.get("EDGE_BASE_URL", "")

def render_header(title: str):
    # consistent, compact header across apps
    col1, col2 = st.columns([1, 5], vertical_alignment="center")
    with col1:
        st.image("assets/ACP_PA_Chapter_Logo.png", width=300)
    with col2:
        st.markdown(
            f"<div style='padding-top:6px'><h1 style='margin:0'>{title}</h1></div>",
            unsafe_allow_html=True,
        )
render_header("Council Voting")

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

# --- Sidebar: How to Vote / Help ---
with st.sidebar:
    st.header("How to Vote")
    st.markdown("""
1. **Enter your ACP number** and click **Validate**.
2. We’ll detect your **region** automatically.
3. Review candidates and **select exactly 3**.
4. Click **Submit vote**.

> **Resume later?**  
> After validating you’ll see a **Resume Code**. If you save a draft and need to come back,
> click **Resume**, then enter your **ACP + Resume Code**.  
> Once your vote is **submitted**, it’s final and cannot be changed.
    """)

    st.subheader("Troubleshooting")
    st.markdown("""
- **“Not eligible”**: We couldn’t find an Active/Graced membership for your ACP.  
  Please contact the chapter office.
- **“Already voted”**: A completed ballot is on file; votes can’t be changed.
- **No candidates shown**: Refresh the page. If it persists, contact the office.
    """)

    # optional: pull contact from secrets so you don’t hardcode it
    CONTACT = st.secrets.get("CHAPTER_CONTACT", "chapter@yourdomain.org")
    st.subheader("Contact")
    st.markdown(f"Chapter office: **{CONTACT}**")

    st.divider()
    st.subheader("Privacy & Security")
    st.markdown("""
- Your ACP number is **hashed** at rest (plaintext ACP is **not** stored).
- One ballot per ACP number.
- Drafts can be resumed; **submitted ballots are final**.
    """)
    st.divider()
    st.subheader("Administrator Access")
    ADMIN_APP_URL = st.secrets.get("ADMIN_APP_URL", "")
    ADMIN_PORTAL_PASS = st.secrets.get("ADMIN_PORTAL_PASS", "")
    pw = st.text_input("Admin passphrase", type="password", key="admin_link_pw_sidebar")
    if st.button("Unlock admin link", key="unlock_admin_sidebar"):
        if pw and ADMIN_PORTAL_PASS and pw == ADMIN_PORTAL_PASS:
            st.session_state["admin_link_ok"] = True
            st.success("Unlocked.")
        else:
            st.error("Incorrect passphrase.")
    if st.session_state.get("admin_link_ok") and ADMIN_APP_URL:
        st.link_button("Open Admin Dashboard", ADMIN_APP_URL, type="secondary")

# ---- small helpers ----

def api_get(path: str, params: Dict[str, Any] | None = None):
    url = f"{EDGE_BASE_URL}/{path}"
    return requests.get(url, params=params, timeout=30)

def api_post(path: str, payload: Dict[str, Any]):
    url = f"{EDGE_BASE_URL}/{path}"
    headers = {"Content-Type": "application/json"}
    return requests.post(url, json=payload, headers=headers, timeout=45)

def validate_acp_any_region(acp: str, regions: list[str]) -> dict:
    """
    Try validate_acp across regions. Prefer 'already_voted' if seen.
    Returns {'ok': True, 'data': <full JSON>, 'region': 'WEST' } on success,
            {'ok': False, 'reason': 'already_voted'|'not_eligible'|<other>}
    """
    best_reason = None  # remember the most informative failure
    for reg in regions:
        r = api_post("validate_acp", {"acp": acp, "region": reg})
        data = r.json() if r.text else {"ok": False}
        if r.ok and data.get("ok"):
            return {"ok": True, "data": data, "region": data.get("region", reg)}
        reason = (data.get("reason") or data.get("error") or "").strip().lower()
        # Prefer 'already_voted' over other reasons, but keep looking in case of success
        if reason == "already_voted":
            return {"ok": False, "reason": "already_voted"}
        if not best_reason:
            best_reason = reason or "validation_failed"
    return {"ok": False, "reason": best_reason or "validation_failed"}

def resume_any_region(acp: str, resume_code: str, regions: list[str]) -> dict:
    """
    Try resume_with_code across regions with similar preference rules.
    """
    best_reason = None
    for reg in regions:
        r = api_post("resume_with_code", {"acp": acp, "resume_code": resume_code, "region": reg})
        data = r.json() if r.text else {"ok": False}
        if r.ok and data.get("ok"):
            return {"ok": True, "data": data, "region": data.get("region", reg)}
        reason = (data.get("reason") or data.get("error") or "").strip().lower()
        if reason == "already_voted":
            return {"ok": False, "reason": "already_voted"}
        if not best_reason:
            best_reason = reason or "resume_failed"
    return {"ok": False, "reason": best_reason or "resume_failed"}

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
        rr = resume_any_region(acp_resume.strip(), resume_code.strip(), ALL_REGIONS)
        if rr["ok"]:
            data, reg = rr["data"], rr["region"]
            ss.token = data.get("token")
            ss.draft_ids = data.get("draft", [])
            ss.resume_code = resume_code.strip()
            ss.region = reg
            st.success(f"Session resumed for region **{REGION_NAMES.get(ss.region, ss.region)}**.")
        else:
            if rr["reason"] == "already_voted":
                st.error("Our records show you have already submitted a ballot.")
            elif rr["reason"] == "not_eligible":
                st.error("We could not find an eligible voter record for this ACP number.")
            else:
                st.error("Could not resume. Check your code and try again.")


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
            vr = validate_acp_any_region(acp.strip(), ALL_REGIONS)
            if vr["ok"]:
                data, reg = vr["data"], vr["region"]
                ss.token = data.get("token")
                ss.draft_ids = data.get("draft", [])
                ss.resume_code = data.get("resume_code", "")
                ss.region = reg
                st.success(f"Validated for region **{REGION_NAMES.get(ss.region, ss.region)}**. Your session is active.")
                if ss.resume_code:
                    st.info(f"Your resume code: **{ss.resume_code}** (save this if you need to come back)")
            else:
                if vr["reason"] == "already_voted":
                    st.error("Our records show you have already submitted a ballot.")
                elif vr["reason"] == "not_eligible":
                    st.error("We could not find an eligible voter record for this ACP number.")
                else:
                    st.error("Validation failed. Please try again or contact the chapter office.")


# ---- Step 2: Candidates ----
st.subheader("2) Review candidates and choose 3")
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
                        



