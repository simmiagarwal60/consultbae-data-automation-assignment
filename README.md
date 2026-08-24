# ConsultBae Data Automation Assignment

A multi-source identity-resolution pipeline, no-code automation, and audio collection application.

## Data Quality Issues and Resolutions

The source files contained 105 raw rows across three unrelated systems. Original rows were preserved in `source_records` so every transformation and rejection remains auditable.

| Issue | Example | Resolution |
|---|---|---|
| Completely blank row | Gig Workers dataframe index 10 | Rejected with `processing_status = rejected`; original empty row preserved in `source_records`. |
| Shifted/corrupted row | Gig Workers index 18 contained skills in `email_id`, email in `worker_name`, and name in `rate` | Rejected because the email field failed structural validation. I did not attempt positional repair because the same Isha Chopra record already existed correctly elsewhere. |
| Repeated header inside data | CBNexus index 14 contained `Name, Phone Number, City, Verified, Projects Completed` | Detected through header-value comparison and rejected. |
| Duplicate Naukri applicant | `Rohit Verma` and `R. Verma` shared the same email and phone | Merged automatically using strong identifiers. Both original source records remain preserved. |
| Multiple emails for one person | Two `Nikhil Chopra` records shared a phone but had primary and alternate emails | Merged through normalized phone; both emails were stored in `person_emails`. |
| Email casing differences | `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG` versus lowercase equivalent | Trimmed and converted emails to lowercase before comparison. |
| Inconsistent phone formats | `+91-9000000131`, `919000000131`, `09000000131`, `9000000131` | Removed punctuation, country prefix and leading zero, then stored in E.164 format such as `+919000000131`. |
| Inconsistent name casing | `RAHUL MALHOTRA`, `Rahul Malhotra` | Stored a readable title-cased name and a separate punctuation-free lowercase `name_key`. |
| Abbreviated names | `R. Verma` versus `Rohit Verma` | Names were not expanded heuristically. The records were merged only because their email and phone matched. |
| Same name belonging to different people | Two `Arjun Mehta` CBNexus contacts had different phones | Name-only merging was prohibited. The records entered a review queue. |
| Unsafe name-only matches | Several Gig and CBNexus records shared names and cities but no identifiers | Flagged for explicit review instead of automatic merging. Decisions were stored in `data/review_decisions.csv`. |
| Residual one-to-one matches | Unmatched Manish Bhatia, Divya Chopra, Karan Chopra and Vikram Mehta records remained after strong matches | Resolved through documented residual name-and-city matching after eliminating already matched candidates. |
| Different people with identical names | A second Deepak Nair had a different email and city | Kept as a separate canonical person because there was insufficient evidence to merge. |
| City casing and whitespace | `PUNE`, `pune`, `Noida ` | Trimmed whitespace and normalized casing. |
| Renamed city aliases | `Gurgaon` and `Gurugram`; `Bangalore` and `Bengaluru` | Mapped to `Gurugram` and `Bengaluru`. |
| Region versus city ambiguity | `Delhi`, `New Delhi`, and `Delhi NCR` | Preserved as separate canonical values rather than incorrectly collapsing them. |
| Mixed date formats | `24-07-2026`, `2026-08-08`, `7 Jul 2026`, `07/13/2026` | Parsed into database dates and standardized as ISO dates. ISO format was handled before flexible day-first parsing. |
| Mixed CTC units | `417964` and `4.2` | Values up to 100 were interpreted as LPA and multiplied by ₹100,000; full INR values were retained. |
| Mixed gig-rate units | `1415/hr` and `15k/month` | Split into numeric `rate_amount_inr` and categorical `rate_unit`; hourly and monthly rates were not compared directly. |
| Inconsistent status casing | `Active`, `active`, `ACTIVE`, `Inactive`, `paused` | Normalized to `active`, `inactive`, or `paused`. |
| Inconsistent boolean fields | `Y`, `N`, `yes`, `Yes`, `No` | Normalized to SQLite boolean values. |
| Inconsistent skill casing | `python`, `Python`, `fastapi`, `REST APIs` | Split comma-separated skills, trimmed them, applied canonical names and deduplicated them through `skills` and `person_skills`. |
| No common ID across all systems | Naukri had email and phone, Gig Workers mainly email, and CBNexus phone | Used identifier chaining: an email could connect Gig to Naukri, while Naukri's phone connected the same canonical person to CBNexus. |
| Potential information loss during cleaning | Standardization could overwrite source-specific representations | Stored every raw row as JSON with its source, row number, hash, processing status and rejection reason. |

### Final Merge Results

| Metric | Count |
|---|---:|
| Raw source rows | 105 |
| Canonical people | 55 |
| Naukri profiles | 42 |
| Valid Gig Worker profiles | 30 |
| Valid CBNexus profiles | 30 |
| Rejected malformed rows | 3 |
| Manually reviewed records | 7 |
| Pending reviews after resolution | 0 |

Automatic merges were allowed only for exact normalized email or phone matches. Name-based matches were treated as candidates rather than facts.

## Stuck Log

### 1. Git repository initialized in the wrong directory

**Problem:** Git unexpectedly listed `AppData`, `Documents`, `Downloads`, registry files and other personal folders. `git rev-parse --show-toplevel` returned `C:/Users/DELL` rather than the project directory.

**What I checked:** I searched the Git root problem, inspected `git rev-parse`, `Test-Path .git`, `git remote -v`, and the remote tree using `git ls-tree`.

**How I got unstuck:** I initialized a nested repository inside the correct project directory, fetched the existing remote history, used a mixed reset to preserve local files, and made a corrective commit that moved the project from `Desktop/consultbae-data-automation-assignment/` to the repository root.

**Suggestion rejected:** I did not immediately delete `C:\Users\DELL\.git`, because it could have contained unrelated history. I fixed the project safely without destructively modifying the parent repository.

### 2. ISO date parsed as the wrong month

**Problem:** The test expected `2026-08-02` to mean 2 August, but flexible parsing with `dayfirst=True` returned 8 February.

**What I checked:** I inspected the failed Pytest assertion and compared flexible date parsing against ISO-8601 rules.

**How I got unstuck:** I added deterministic handling for `YYYY-MM-DD` using `date.fromisoformat()` before falling back to flexible parsing for formats such as `24-07-2026` and `7 Jul 2026`.

**Suggestion rejected:** I did not change the test expectation or globally disable day-first parsing, because doing so would silently misinterpret the other source formats.

### 3. Running self-hosted n8n on Windows

**Problem:** Docker Desktop initially failed because hardware virtualization was disabled. The npm alternative then produced dependency warnings, a missing `callsites` module, and an excessively slow installation.

**What I checked:** I searched the Docker/WSL error, ran `wsl --status`, reviewed Docker’s Windows requirements, and inspected the n8n npm error.

**How I got unstuck:** I enabled virtualization in the Dell BIOS, enabled Windows Virtual Machine Platform/WSL 2, restarted Docker Desktop, and ran n8n through Docker Compose.

**Suggestions rejected:** I rejected continuing to debug the npm dependency tree because the assignment specifically benefits from reproducible container setup. I also rejected the n8n Cloud trial because I wanted the submitted workflow to be completely self-hosted and reproducible.

### 4. n8n sent CSV values as JSON keys

**Problem:** FastAPI returned HTTP 422. Its error showed a body shaped like `{"Isha Chopra": "", "09000000138": ""}` instead of fields named `name`, `email`, and `phone`.

**What I checked:** I expanded the HTTP Request node’s full error response rather than relying on the generic n8n message.

**How I got unstuck:** I placed fixed field names in the n8n Name boxes and expressions such as `{{ $json.name }}` only in the Value boxes.

**Suggestion rejected:** I did not weaken API validation, because the API correctly exposed a malformed automation request.