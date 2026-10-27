"""Writes draft_mapping_top_level.csv: a first-pass Mapping for the top-level
folders of the SocEnt shared drive (as listed on 2026-10-27). Paste the CSV
into the "Mapping" tab of the Script 1 output, review, then run Script 2.

Confidence: H = clear from the name, M = likely, L = guess, team to confirm.
"""
import csv
import os

PD = "05 ORGANISATIONS/_Programme docs"
MP = PD + "/Meta Pragati AI for Impact"
S = "01 STRATEGY & OPERATIONS"
R = "02 RESEARCH & IMPACT"
L = "03 LEGAL & COMPLIANCE"
B = "04 BRAND & MEDIA"
F = "06 FUNDING PROPOSALS"
TBS = "07 TO BE SORTED"

# (id, current name, action, target path, new name, confidence, reason)
# Order matters: a folder is MOVEd before other rows target paths inside it.
ROWS = [
    # Programme folders (moved first so the FY rows below land inside them)
    ("11m2TqVgf4IZAWTtMe2RiCKEd3tJMgQD7", "Meta Pragati", "MOVE", PD, "Meta Pragati AI for Impact", "M", "Becomes the programme folder. FY/cohort folders go inside"),
    ("199yuvxTSVhx7AdOA25r5Yx7tHVP6C6Zc", "Incubator", "MOVE", PD, "", "H", "Programme"),
    ("1Fhz5S1ZLrvDknyCnJZwoQ-Fcgy7mGrFt", "Accelerator", "MOVE", PD, "", "H", "Programme"),
    ("1HQ_ypsTBgxwAohcRxygRaMU3Ww0Fmef_", "AlumConnect", "MOVE", PD, "", "M", "Alumni programme"),
    ("1dWAKSPxmTS9FZo15YsYVwys4v1CPgyXa", "Launchpad ", "MOVE", PD, "Launchpad", "M", "Programme. Trailing space removed"),
    ("1TtpKxdvdtJuWndJR0TiUN8VcgNLmkAcj", "Skill Uplift Organisation Notes", "MOVE", PD, "Skill Uplift", "L", "Looks like a programme. Notes per org may belong in org folders"),
    ("1WTM-Ihcii_XR9gPRdUKQg1vuOf81gPfQ", "Project Pioneer", "MOVE", PD, "", "L", "Assumed to be a programme. Confirm"),
    ("1glQ4x4U_f4jAur0HetjK82Q98Lb7uCSX", "Meta Pragati AI for Impact FY 25", "MOVE", MP, "FY25", "H", "Programme > year"),
    ("1FRkwe8-oICqggftjBQ_Hvg-lnN0C1y0g", "Meta Pragati AI for Impact FY 25 (duplicate)", "MERGE", MP + "/FY25", "", "M", "DUPLICATE of the row above (same name and modified date). Check it is a copy before merging"),
    ("172ytpYnHmeCX5Tly_eGidIa0VOPUM0qM", "Meta Pragati AI for Impact FY 26", "MOVE", MP, "FY26", "H", "Programme > year"),
    ("13VuZ36Okvp7tBcrTs-0kUrrpwTDEgh8j", "Meta Pragati AI for Impact FY 27", "MOVE", MP, "FY27", "H", "Programme > year"),
    ("1wdJz2J38ZyojsJgWNq0JtYv3P5zXmn0V", "Pragati AI for Impact 3 Applications", "MOVE", MP + "/FY27", "Applications", "M", "Assumes cohort 3 = FY27. Confirm"),
    ("1JVeNGiEApBDns3dObtj8y3Gi2xYTpj95", "Pragati Backend documents", "MOVE", MP, "Backend documents", "M", "Programme-level docs"),
    ("1-hQqJEFU1SrfdBmhqrljLMHgYGfgUOmY", "DATA ROOM: Meta Pragati <> Deloitte", "MOVE", MP, "Data room - Deloitte", "M", "Original stays with the programme"),
    ("1-hQqJEFU1SrfdBmhqrljLMHgYGfgUOmY", "DATA ROOM: Meta Pragati <> Deloitte", "SHORTCUT", R + "/Data rooms", "Meta Pragati - Deloitte", "H", "Data rooms hold shortcuts only"),
    ("1MQf7oYrgix7Rpd2jjz9WPcZiThZvVmtJ", "Accelerator Cohort A/1 (Series/N)", "MOVE", PD + "/Accelerator", "Cohort A1 (Series N)", "M", "Programme > cohort. Slashes removed from name"),
    ("1rihP-WoktKxK41ZVi7QBXFW_U4gBToih", "Cohort books", "MOVE", PD, "Cohort books (to split by programme)", "M", "Cohort books belong in each programme/cohort folder. Split by hand"),
    ("1taGIipmDS4jL8VwcSrLw8PZY4Mmf5wij", "Knowledge Sessions", "MOVE", "05 ORGANISATIONS/_Programme resources", "", "M", "Used across programmes"),
    ("1DOZXeCY8Xt74ByUto2DVXvQBi1a2X_hT", "Statestreet Org Presentations", "MOVE", TBS, "", "L", "Org decks: split into each org's 01 Profile & pitch deck"),
    ("1NUqHsLKS5Iut36Jf180OsijNtgDrjYnv", "Recommendation for Fellowships", "MOVE", TBS, "", "M", "Split into each org's 05 Recommendations & nominations"),

    # 01 STRATEGY & OPERATIONS
    ("1LUwQrDl8H8gocgRcYNhVlJgQyQJ5EPgm", "Master Deck", "MERGE", S + "/Decks", "", "H", "Then move live deck to CURRENT, rest to _superseded"),
    ("18gFqEeWPdQVO7eJT2-r2iqO06qnujuL2", "SocEnt The^Delta ALM Deck ", "MOVE", S + "/Decks", "ALM deck", "M", "Deck"),
    ("1t45lS4k0qZlNe7WPSEHxO5P6X-kWKMFK", "The^delta strategy", "MERGE", S + "/Strategy, reviews & deepdives", "", "H", "Strategy papers"),
    ("1aAlzGyVzh29S1rqNe5VQlzmQ39fGrvlt", "The^delta strategy (duplicate)", "MERGE", S + "/Strategy, reviews & deepdives", "", "M", "DUPLICATE name and modified date as row above. Check for duplicate files after merge"),
    ("1jF2zKI1ob4qEN2XT054INX-x9iAhGefH", "Quarterly Deepdives", "MOVE", S + "/Strategy, reviews & deepdives", "Quarterly deepdives", "H", ""),
    ("17R7BP1sSi_Gakt_Bp3gyB58ME-QIlWHR", "2023 - Presentation for reviews", "MOVE", S + "/Strategy, reviews & deepdives", "Review presentations", "M", "Year moved out of folder name. Put the year in the file names"),
    ("1sugcvnVkYGCtgHtUlskODrMRpyYm80RQ", "Field Building - Top Of Funnel", "MOVE", S + "/Strategy, reviews & deepdives", "Field building - top of funnel", "M", ""),
    ("1LqkgvYa3kTXLB2xd6qe_tEjEXCTTnaXw", "ALM Updates", "MOVE", S + "/Strategy, reviews & deepdives", "", "L", "Confirm what ALM is"),
    ("1VWMPj_cJC3YHbf44wSHXusQpX9flipN7", "Process Document-Narrative Documents", "MERGE", S + "/Process & templates", "", "H", "SOPs"),
    ("16LRoFSqlpJRC9Gc2UfPEMLcMGq9ybbz3", "Impact Checklist Documents", "MOVE", S + "/Process & templates", "Impact checklists", "M", "Checklists. Could go to 02 if it holds data"),
    ("1dYqpno-uT9N7-f4J-CgLJLGpnBavEcXd", "Socent KT", "MOVE", S + "/Team operations", "Knowledge transfer", "M", ""),
    ("144HySkzqBnX_smiKwq9B4pTp9axxAQsf", "JD", "MOVE", S + "/Team operations", "Job descriptions", "M", "Name expanded"),
    ("14Ni8sWj571X0HP3xF9jYOk_0-Pvh15zK", "Thought Leadership", "MERGE", S + "/Thought leadership", "", "H", ""),
    ("1teEcNKnoehTQlWhs9GtPfmPyPeZxkZMJ", "Social Entrepreneurship Documents_Times", "MOVE", S + "/Thought leadership", "Times - social entrepreneurship", "L", "Published pieces?"),
    ("1N25ItMIFA3snjnCZCqwiupexMWxWVhgn", "N/Core Product", "MOVE", S + "/Product", "N-Core product", "H", "Slash removed from name"),
    ("1VE__5BZuWiflt3K8L2o5SPSZMfUFABZe", "N/Core Seeds", "MOVE", S + "/Product", "N-Core Seeds", "H", "Slash removed from name"),
    ("1NaH0Iad-lYIaMiCGYIvNrWFNvpKZG6yo", "Delta Seed/ Equity (CSR Equity) thinking", "MOVE", S + "/Product", "Delta Seed - Equity (CSR equity)", "H", "Slash removed from name"),
    ("1OM_Qg4-j0iWk0JowDPSkP1FGdeJJbkGZ", "N_Core_Fundraising", "MOVE", S + "/Product", "N-Core fundraising", "L", "Could be 06 instead"),
    ("1FZfUE1AJirE9zZnq30Kb4-Hoh_CTjFQo", "Socent Partners Database", "MOVE", S + "/Network & ecosystem", "Partners database", "H", ""),
    ("1HuYKvMb2XcF92zay2yAjFPfUUuKBuG_M", "Gujarat SocEnt Cell", "MOVE", S + "/Network & ecosystem", "", "M", "Government mapping"),
    ("1XJUUZBYiF2pp0fAXGfgIs6htleRnVNha", "MoRD", "MOVE", S + "/Network & ecosystem", "MoRD (Ministry of Rural Development)", "L", "Could be a proposal instead"),
    ("1ZyTqEgNj1BtP_-2s-9KvDmcaUw2vOZrG", "AIC NCORE DEVELOPMENTAL IMPACT FOUNDATION", "MERGE", S + "/AIC N-Core", "", "H", "Do not reorganise files inside. Legal papers go to 03 by hand"),

    # 02 RESEARCH & IMPACT
    ("1GCz_isANorQB5BcimIB6FBe9GpbDhVDQ", "Social Entrepreneurship Landscape Report", "MOVE", R + "/Landscape & studies", "Landscape report", "H", ""),
    ("1pQJmCMMx5fpZ94pkmzeaEuv0pyyvhK1W", "70+ livelihood book", "MOVE", R + "/Landscape & studies", "", "M", ""),
    ("1rxoVYdsAbSn6E4DTnH6Yiq4mC5i9jgKA", "Roadmap to livelihoods - SocEnt", "MOVE", R + "/Landscape & studies", "Roadmap to livelihoods", "M", ""),
    ("1GZgovyDpTig9CEzliocAzqKQjtlS0tiU", "Stepback Data Analysis", "MOVE", R + "/Landscape & studies", "Stepback data analysis", "M", ""),
    ("11xdAL8mSa1bG2rgK6fvMeiHmWa7MJqI4", "Social Stock Exchange", "MOVE", R + "/Landscape & studies", "", "M", ""),
    ("1MWdCTfPZFWSGI5y5KyDarQoN6gEawsxB", "Impact data questionnaire", "MOVE", R + "/Impact data", "", "M", "Split by year if it holds responses"),
    ("1MTiF4EkEGenePjhlrKgysBbhPGNKmtcO", "Impact Data Backup", "MOVE", R + "/Impact data", "_Backup (check for duplicates)", "M", "Probably duplicates live impact data"),

    # 03 LEGAL & COMPLIANCE (signed only)
    ("1Y-fx-v6gik7FttMmwvHQs36lIuhlNb_K", "Current Agreements", "MERGE", L + "/01 Agreements & MoUs", "", "H", "Then sort into year-signed folders"),
    ("1uGI9E1aVHy13T7SavcdFQT1n4Xsy5kel", "Meta MoUs Jan 2024", "MOVE", L + "/01 Agreements & MoUs/2024", "Meta Pragati MoUs", "H", "Year folder per signing year"),
    ("1ge0FZIuaTri8-r_o6PQjY6Zs0UiOThYq", "NLF Service Agreement", "MOVE", L + "/01 Agreements & MoUs/2025", "", "M", "Only if signed. Drafts stay with programme"),
    ("1KakP-NOQsP3h_0UkyRXHaEwVQCWzccl6", "Mukkamaar- DE Shaw resolution", "MOVE", L + "/03 Registrations & statutory", "Mukkamaar - DE Shaw resolution", "M", ""),
    ("1P5UlwhzsxBHcF_Dpuw1_Su6wwe4VI2eM", "Utilization Reports N core", "MOVE", L + "/02 Utilisation certificates", "N-Core utilisation reports", "M", "Split by FY"),

    # 04 BRAND & MEDIA
    ("1M7Wb76I_oTuvmOu4qKX7CzmhVvuPGNq7", "SocEnt Newsletters", "MOVE", B + "/Collaterals & campaigns", "Newsletters", "H", ""),
    ("1pW7irTZrBwG4I_HIOsKddWMWtEa2R2vu", "SocEnt Newsletters (duplicate)", "MERGE", B + "/Collaterals & campaigns/Newsletters", "", "H", "DUPLICATE folder name. Merged into the one above"),
    ("1QbcFjyZTI9IyxnwwkWXMRJihF74tfhB2", "Marketing", "MERGE", B + "/Collaterals & campaigns", "", "M", ""),
    ("107Bdd89SxnLQwejjizMM7mfHd4VVu8QG", "Website Updates 2024", "MOVE", B + "/Collaterals & campaigns", "Website updates", "H", "Ad hoc year removed"),
    ("1POTthKMh4t5-wfmRXI-JQWU3Xgj9nV6b", "10 years of Nudge", "MOVE", B + "/Collaterals & campaigns", "", "M", "Or Events if it was an event"),
    ("1xfFMwyHgh8upCvDZed3TW9DotXq5Buq6", "Soiree 2024", "MOVE", B + "/Events", "2024-MM Soiree", "M", "Fill in the month"),
    ("1OECbu3XIE--pGpeQv8uo3svUgBPWxxek", "Soiree 2026", "MOVE", B + "/Events", "2026-MM Soiree", "M", "Fill in the month"),
    ("1Da-pKxnFC8S4h-oOIkQGsbeo9-Cjvfsp", "100+ Alumni event pix", "MOVE", B + "/Events", "2024-11 Alumni event", "M", "Date taken from naming example. Confirm"),
    ("10GUV7zyIQWxsOGtJ_gJkRnb9wxAch-Bw", "Artisan roundtable", "MOVE", B + "/Events", "YYYY-MM Artisan roundtable", "M", "Fill in date"),
    ("1QDHH96ablLmeLABvInCTLlVP2YClcf0P", "Mulago huddle pictures", "MOVE", B + "/Events", "YYYY-MM Mulago huddle", "M", "Fill in date"),
    ("1IHJ6dQShX3m3rNlAr_L_uDvAVjNh9Oya", "Demo installations at LBSNAA", "MOVE", B + "/Events", "YYYY-MM LBSNAA demo installations", "M", "Fill in date"),
    ("1Xc5AhRCMgWHkFsrlQflsERMmp44TaZxz", "SD Delta Pictures", "MOVE", B + "/Films & photo library", "", "M", ""),
    ("1HVuLQ7L0murHBXS3utSI75_a-3QgDTjw", "Camera Photos ", "MOVE", B + "/Films & photo library", "Camera photos", "M", ""),
    ("1nW2iFmXy_QDTA7Ba02LAsnDx9UGZoNSP", "Previous cohort pic", "MOVE", B + "/Films & photo library", "Cohort photos", "M", ""),
    ("10_LTbcNvzVxC6aiikJ_NCT5t19VuFItq", "Meta Movies", "MOVE", B + "/Films & photo library", "", "M", ""),
    ("1ba58WTTUQ12e0a5M8aQ080fzRHX6vTd4", "Carrot Movies - Incubator and Accelerator", "MOVE", B + "/Films & photo library", "", "M", ""),

    # 06 FUNDING PROPOSALS (year, then funder)
    ("1VJ66Q63kGQHq-SF53ILCkuIx-xlge37g", "Proposals", "MERGE", F, "", "M", "Then sort contents into year > funder"),
    ("1Jal3PDBLMgkc_oXBw8wpl4FkILHqQgf9", "FR Folder", "MERGE", F, "", "M", "Then sort contents into year > funder / _FR resources"),
    ("1kGXfWUedl1hl19RADGUkJiDGL-L3bPYZ", "Meta Pragati Proposal October 23", "MOVE", F + "/2023", "Meta Pragati", "H", ""),
    ("1HolS0QeQmaGbLPTC4KzKCX_HCebVkr0W", "Koita Proposals 2023", "MOVE", F + "/2023", "Koita", "H", ""),
    ("1H-tLRtsxP6UC3qS5PfBF9fPHfNh5qOhq", "Mphasis FY 24-25 Proposal", "MOVE", F + "/2023", "Mphasis", "M", "Year = year submitted (2023). Team to confirm submission year vs FY"),
    ("1ZNmADOrQDouuTnTqoP1lWCt9nSrI5QA5", "Grant Thornton", "MOVE", F + "/2023", "", "L", "Assumed to be a funder"),
    ("17QC264OLiHfGZMgWB_Fkp9XdlM5ANvFR", "Skoll Profiles", "MOVE", F + "/2024", "Skoll", "M", ""),
    ("1hpsJ4OZycc_ij9Q7nBx4u6UZnWShD8nS", "CSR Sep 2024", "MOVE", F + "/2024", "CSR (Sep)", "L", "Confirm funder"),
    ("18xn7RFwmv4wYy4YtFhF-OmYoSRn2DOXm", "MOSJE SocEnt Fund", "MOVE", F + "/2024", "MoSJE", "M", ""),
    ("1wMecKP-4005pFrZVKetJmWMrueezDZNp", "MOSJE SocEnt Fund (duplicate)", "MERGE", F + "/2024/MoSJE", "", "M", "DUPLICATE name and modified date as row above"),
    ("1UeK_fIln56taZ_HJxrS53DxpvnAZ2xNj", "DST ", "MOVE", F + "/2026", "DST", "L", "Assumed to be a proposal to the Dept of Science & Technology"),
    ("15yE6lbs5vUtNXBcCzwc2ibqS_POUcBtE", "Target Volunteering <>TNI", "MOVE", F + "/CSR & volunteering", "Target", "H", ""),
    ("1-rCVF3N57WP42L2EiDOdGQNs9YgGrBM1", "Mphasis Quarterly Reporting", "MOVE", F + "/Reporting to funders", "Mphasis", "H", ""),

    # 07 TO BE SORTED: no home yet in the agreed structure
    ("17IIZIVP4aVz3xaswKjZL6BsRFbrV_Qln", "Misc", "MERGE", TBS, "", "H", "Per structure"),
    ("1V1x60k9bonoXCRu5mtw00p-rkg_eCF7H", "Other", "MERGE", TBS, "", "H", "Per structure"),
    ("1iVBfUV2lLgyEFv9p09rAJg63dO_QyO4E", "Tech Docs ", "MERGE", TBS, "", "H", "Per structure"),
    ("1VTd4j7fACwoeEPq_-uSt4wvMOIDc2nsA", "Donors", "MOVE", TBS, "", "L", "Split: proposals > 06, reports > Reporting to funders"),
    ("1PTj7D1WjS33-Gr-Hv40QcE-Z-m4R9mqO", "Catalysts for Change", "MOVE", TBS, "", "L", "Unknown. Programme, event or proposal?"),
    ("1pqc8m5sZsjb9380GkU9Kut3iB4U8-Yxg", "CSI 3.0", "MOVE", TBS, "", "L", "Unknown"),
    ("1rQ70-Br97QIT8Fenf8CeBTu_1cQ0pEmf", "BIC", "MOVE", TBS, "", "L", "Unknown"),
    ("1ADH_5BeEog8nK-M_0RlQp98hl_fPIMO9", "Archana Pillai ", "MOVE", TBS, "", "L", "Named after a person. Check contents"),
    ("1Qa-GhdOtgOZZQaC05mEAuKzhf04nWJaU", "Tax Invoices", "MOVE", TBS, "", "L", "DECISION: no finance home in new structure"),
    ("1-Quqen1RPUkLfRf8J1usZ2QCZ_u91FMe", "Expense Claim", "MOVE", TBS, "", "L", "DECISION: no finance home in new structure"),
    ("1FMAhXutODFhp3hw93_70mlnFCJ1fzHNm", "2019 - 2020 Donation receipts for finance", "MOVE", TBS, "", "L", "DECISION: no finance home in new structure"),
]

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "draft_mapping_top_level.csv")
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["Source Folder ID", "Current Path", "Action", "Target Path", "New Name",
                "Reason", "Status", "Result", "Confidence"])
    for fid, name, action, target, new, conf, reason in ROWS:
        w.writerow([fid, "/" + name, action, target, new, reason, "", "", conf])
print(len(ROWS), "rows ->", out)
