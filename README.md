# Gmail Draft Automation

Two small Python tools that turn a CSV of personalised messages into **Gmail drafts**, so a large outreach or re-engagement campaign can be reviewed and sent by hand instead of typed one by one. Nothing is ever sent automatically.

Used in production for creator re-engagement campaigns of 140+ contacts, cutting a multi-hour manual workflow to minutes of review.

## Tools

| Script | What it does | Gmail scope |
|---|---|---|
| `create_drafts.py` | Creates a new draft for every row in `drafts.csv` (`Name, Email, Subject, Body`) | `gmail.compose` (drafts only, cannot read mail) |
| `reply_in_thread.py` | Finds the latest existing thread with each contact in `replies.csv` and creates the draft **inside that thread** (`Re:` subject, `In-Reply-To` / `References` headers). Contacts with no thread are skipped and listed, so nobody gets a stray cold email | `gmail.compose` + `gmail.readonly` |

## Design choices

- **Human in the loop:** both tools only create drafts; sending stays manual.
- **Least privilege:** the first tool cannot read the inbox at all; the second adds read-only access only because it has to locate threads.
- **Resume-safe:** every completed address is appended to a log file and skipped on the next run, so a crash or rate limit never creates duplicates.
- **Dry run:** `--dry-run` prints exactly what would happen without touching Gmail.
- **Gentle on limits:** short pause between calls, longer pause after an error.
- **UTF-8 bodies:** non-ASCII characters (Turkish, Arabic, em dashes) survive intact.

## Usage

```bash
pip install -r requirements.txt
# Google Cloud Console → enable Gmail API → OAuth client (Desktop app) → save as credentials.json

python create_drafts.py --csv examples/drafts.csv --dry-run
python create_drafts.py --csv examples/drafts.csv

python reply_in_thread.py --csv examples/replies.csv --dry-run
```

The first run opens a browser for Google sign-in and stores `token.json` locally. `credentials.json`, `token.json`, logs and real CSV files are git-ignored.

## Tech stack

Python 3 · Gmail API · Google OAuth 2.0

---

© 2026 yunalhoshi. All rights reserved. See [NOTICE](NOTICE).
