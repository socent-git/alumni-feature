# Prompt: feed the Script 1 output to Claude

Paste everything below the line into Claude. Attach the **Schema** tab as CSV
(File > Download > CSV), or paste the **Tree** tab (column A).

---

You are helping reorganise our team's Google Drive (SocEnt, The^Delta). Attached is
the full folder schema: one row per folder with ID, path, depth, file counts,
dates and auto-flags. It has no file contents.

## Target structure (agreed by the team; preliminary)

| Top folder | Rule |
|---|---|
| 00 START HERE | Readme, register, naming rules. Nothing else |
| 01 STRATEGY & OPERATIONS | By content. Nothing that belongs to one org or one funder. Subfolders: Decks (CURRENT / _superseded), Strategy, reviews & deepdives, Process & templates, Team operations, Thought leadership, Product (N/Core, Seeds, Jobs, Delta Seed/Equity), Network & ecosystem, AIC N-Core (by tranche; do not reorganise files inside; legal papers go to 03) |
| 02 RESEARCH & IMPACT | Landscape & studies, Impact data (one folder per year), Data rooms (shortcuts only, originals stay where they are) |
| 03 LEGAL & COMPLIANCE | Signed documents only, drafts stay with the programme. 01 Agreements & MoUs (folder per year signed), 02 Utilisation certificates (by FY), 03 Registrations & statutory, 04 Templates |
| 04 BRAND & MEDIA | Our brand only. Logos (ours and funders'), Collaterals & campaigns, Events (one folder per event, date first: `2024-11 Alumni event`), Films & photo library |
| 05 ORGANISATIONS | One folder per org, A-Z, each with the same 6 subfolders: 01 Profile & pitch deck, 02 Readiness & assessments, 03 Budgets & utilisation, 04 Photos, videos & logos, 05 Recommendations & nominations, 06 Partner-supplied. Plus `_Programme docs` (programme > cohort/year) and `_Programme resources` |
| 06 FUNDING PROPOSALS | Year > funder (submitted locked PDF + WIP inside). Plus CSR & volunteering, Reporting to funders, _FR resources |
| 07 TO BE SORTED | Flat. Cleared monthly |

Naming rules: name things for what they are; add a date only when it matters
(`2025-04 Mphasis proposal`); mark the final one (`... FINAL.pdf`). No ad hoc years
in folder names ("Strategy 2024", "Proposals 2025"), except where the structure
asks for them (Legal year, Events date, Proposals year, Programme cohort/year).

## What I need

1. **Issues found**, grouped as:
   - Duplicates: same or near-same name (use the DUP flags, plus fuzzy matches such as "Socent"/"SocEnt", trailing spaces, "(1)", "Copy of").
   - Inconsistent naming: case, slashes, abbreviations, ad hoc years, vague names (Misc, Other, New folder).
   - Structural: empty folders, folders deeper than 5 levels, overloaded folders (>150 files), org-specific content outside 05, signed vs draft legal docs mixed.
2. **Mapping table** in exactly these columns, one row per folder that should change:
   `Source Folder ID | Current Path | Action | Target Path | New Name | Reason | Status | Result | Confidence`
   - Action is one of MOVE, MERGE, RENAME, SHORTCUT, CREATE, SKIP.
   - Target Path is relative to the drive root, e.g. `05 ORGANISATIONS/_Programme docs/Incubator`.
   - Use MERGE when the target folder already exists, or will be created by the skeleton.
   - Put parent moves before child moves. Leave Status and Result blank.
   - Confidence is H/M/L. Use L whenever you are guessing from the name alone.
   - When a folder's subfolders need to go to different places, map the subfolders, not the parent.
3. **Org list**: every partner organisation you can identify, so we can pre-create their `05 ORGANISATIONS/<Org>` folders.
4. **Open decisions**: anything the structure doesn't cover (for example finance records like invoices, expense claims and donation receipts).

Output the mapping as CSV in a code block so I can paste it into the Mapping tab.
