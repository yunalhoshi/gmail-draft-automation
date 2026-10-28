#!/usr/bin/env python3
"""
reply_in_thread.py — IN-THREAD reply drafts -> Gmail
For each contact in replies.csv, finds the most recent existing
email thread with that person and creates a DRAFT REPLY inside that thread
(Subject auto becomes "Re: <original>"). If no thread exists, it SKIPS the
person and reports them at the end (so nobody gets a stray new email).

Resume-safe: drafted-reply.log records done emails and skips them on re-run.
Nothing is ever sent — scope only allows reading + creating drafts.

IMPORTANT — NEW SCOPE
---------------------
This script needs to READ your mail (to find the thread) plus create drafts.
That is a different scope than create_drafts.py uses, so:
  -> DELETE token.json (if present) before the first run, then re-authorize.
Same credentials.json works.

SETUP / RUN are identical to create_drafts.py otherwise:
  py reply_in_thread.py --dry-run     # find threads, create nothing
  py reply_in_thread.py               # create the in-thread reply drafts
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

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.path.join(HERE, "token.json")
CREDS = os.path.join(HERE, "credentials.json")
DONE_LOG = os.path.join(HERE, "drafted-reply.log")


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
        return {l.strip().lower() for l in f if l.strip()}


def mark_done(email):
    with open(DONE_LOG, "a", encoding="utf-8") as f:
        f.write(email.lower() + "\n")


def header(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def find_latest_message(service, email):
    """Return (threadId, rfc822_message_id, subject) for the newest thread
    with this person, or None if no thread exists."""
    q = f"from:{email} OR to:{email}"
    res = service.users().messages().list(
        userId="me", q=q, maxResults=1).execute()
    msgs = res.get("messages", [])
    if not msgs:
        return None
    thread_id = msgs[0]["threadId"]
    thread = service.users().threads().get(
        userId="me", id=thread_id, format="metadata",
        metadataHeaders=["Message-ID", "Subject"]).execute()
    last = thread["messages"][-1]
    return (thread_id, header(last, "Message-ID"), header(last, "Subject"))


def make_reply_raw(to_addr, subject, body, in_reply_to):
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to_addr
    if subject and not subject.lower().startswith("re:"):
        subject = "Re: " + subject
    msg["Subject"] = subject or "Re: following up"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "replies.csv"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    done = load_done()
    service = get_service()   # read needed even for dry-run (to find threads)

    created = skipped = nothread = failed = 0
    no_thread_list = []
    for i, r in enumerate(rows, 1):
        name = (r.get("Name") or "").strip()
        email = (r.get("Email") or "").strip()
        body = (r.get("Body") or "").rstrip("\n")
        if not email:
            continue
        if email.lower() in done:
            skipped += 1
            continue
        try:
            found = find_latest_message(service, email)
        except HttpError as e:
            failed += 1
            print(f"[{i}/{len(rows)}] FAIL(search) {name:<12} {email} -> {e}")
            continue

        if not found:
            nothread += 1
            no_thread_list.append((name, email))
            print(f"[{i}/{len(rows)}] NO THREAD   {name:<12} {email}")
            continue

        thread_id, in_reply_to, subject = found
        if args.dry_run:
            created += 1
            print(f"[{i}/{len(rows)}] DRY  {name:<12} {email}  thread={thread_id}  re='{subject[:40]}'")
            continue
        try:
            raw = make_reply_raw(email, subject, body, in_reply_to)
            service.users().drafts().create(
                userId="me",
                body={"message": {"raw": raw, "threadId": thread_id}},
            ).execute()
            mark_done(email)
            created += 1
            print(f"[{i}/{len(rows)}] OK   {name:<12} {email}  (in-thread)")
            time.sleep(0.4)
        except HttpError as e:
            failed += 1
            print(f"[{i}/{len(rows)}] FAIL {name:<12} {email} -> {e}")
            time.sleep(2)

    print(f"\nDone. created={created} skipped(already)={skipped} "
          f"no_thread={nothread} failed={failed}")
    if no_thread_list:
        print("\nNo existing thread (left untouched — handle manually if needed):")
        for n, e in no_thread_list:
            print(f"  - {n}: {e}")
    print("\nReply drafts are in Gmail > Drafts, inside each original thread. Nothing sent.")


if __name__ == "__main__":
    main()
