#!/usr/bin/env python3
"""
create_drafts.py — bulk personalised drafts -> Gmail
Reads drafts.csv and creates a Gmail DRAFT for each row.
Resume-safe: already-created rows are logged and skipped on re-run.

SETUP (one time)
----------------
1) pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
2) Google Cloud Console -> enable "Gmail API" -> create OAuth client (Desktop app)
   -> download as credentials.json, put it next to this script.
3) First run opens a browser to authorize. Scope used:
   https://www.googleapis.com/auth/gmail.compose  (create drafts only, cannot send)

RUN
---
python create_drafts.py                      # uses drafts.csv in same folder
python create_drafts.py --csv other.csv      # custom csv
python create_drafts.py --dry-run            # print what it would do, create nothing

The CSV must have columns: Name, Email, Subject, Body
"""

import argparse
import base64
import csv
import os
import sys
import time
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.path.join(HERE, "token.json")
CREDS = os.path.join(HERE, "credentials.json")
DONE_LOG = os.path.join(HERE, "drafted.log")   # one email per line = already done


def get_service():
    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS):
                sys.exit("Missing credentials.json — see SETUP in this file.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def load_done():
    if not os.path.exists(DONE_LOG):
        return set()
    with open(DONE_LOG, encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


def mark_done(email):
    with open(DONE_LOG, "a", encoding="utf-8") as f:
        f.write(email.lower() + "\n")


def make_raw(to_addr, subject, body):
    msg = MIMEText(body, "plain", "utf-8")   # UTF-8 so ğ / em-dash survive
    msg["To"] = to_addr
    msg["Subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "drafts.csv"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    done = load_done()
    service = None if args.dry_run else get_service()

    created = skipped = failed = 0
    for i, r in enumerate(rows, 1):
        name = (r.get("Name") or "").strip()
        email = (r.get("Email") or "").strip()
        subject = (r.get("Subject") or "").strip()
        body = (r.get("Body") or "").rstrip("\n")
        if not email:
            continue
        if email.lower() in done:
            skipped += 1
            continue

        if args.dry_run:
            print(f"[{i}/{len(rows)}] DRY  {name:<14} {email}")
            created += 1
            continue

        try:
            raw = make_raw(email, subject, body)
            service.users().drafts().create(
                userId="me", body={"message": {"raw": raw}}
            ).execute()
            mark_done(email)
            created += 1
            print(f"[{i}/{len(rows)}] OK   {name:<14} {email}")
            time.sleep(0.4)   # gentle on rate limits
        except HttpError as e:
            failed += 1
            print(f"[{i}/{len(rows)}] FAIL {name:<14} {email}  -> {e}")
            time.sleep(2)

    print(f"\nDone. created={created} skipped(already)={skipped} failed={failed}")
    print("Drafts are in Gmail > Drafts. Nothing was sent.")


if __name__ == "__main__":
    main()
