# PA-ACP Council Voting

This site lets eligible members vote for **exactly 3** candidates in their region.

## For Voters
1. Open the voting page.
2. Enter your **ACP number** and press **Validate**.
3. Review your **region’s** candidates (your region is detected automatically).
4. Select **exactly 3** candidates.
5. Click **Submit vote**.

> **Resume later?**  
> After validating you’ll see a **Resume Code**. If you save a draft and need to come back, open the page, click **Resume**, and enter your **ACP + Resume Code**. Once your vote is **submitted**, it’s final and cannot be changed.

### Troubleshooting
- **“Not eligible”**: We couldn’t find an active/graced membership for your ACP in your region. Contact the chapter office.
- **“Already voted”**: Our records show a completed ballot. Votes can’t be changed once submitted.
- **No candidates shown**: Please refresh; if it persists, contact the chapter office.

## Privacy & Security
- Your ACP number is **hashed** at rest; the plaintext ACP is not stored in the database.
- One ballot per ACP number. Drafts can be resumed; **submitted ballots are final**.

---

## For Admins
### Admin Dashboard
- **Upload Registry**: upload a CSV with `RegionCode` (PAW/PAS/PAE), `CustomerID`, `Email`, `MemberStatus`.
  - **Sync mode** (optional): marks anyone **not** in the uploaded file as **ineligible** for the regions present.
- **Non-Voters**: list/download of eligible members who haven’t voted yet (per region).
- **Live Tallies**: real-time vote totals per candidate (per region).

### Opening/Closing Voting
- **Open**: upload final registry (optionally with **Sync**), verify counts, then announce the voting link.
- **Close**: simply stop accepting submissions (optional window enforcement) and export tallies.

### Contacts
- Chapter office: <insert email/phone>
