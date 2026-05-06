#!/usr/bin/env python3
"""Bulk-ingest CoA PDFs from a Google Drive folder into the running CoA Tracker.

Two modes:

1. **Public folder (anyone with link)** — uses `gdown` to download, then POSTs
   each PDF to /coas/upload.

   pip install gdown httpx
   python scripts/seed_from_drive.py \
       --folder-url 'https://drive.google.com/drive/folders/18Egoy3N5CDRlpHsPIPtFnb--19UEY9NU' \
       --api http://localhost:8000 \
       --email admin@example.com --password admin

2. **Private folder** — supply a Google service account JSON via
   `--service-account creds.json`, share the folder with the SA email, and
   the script will list + download via the official API.

Both modes upload one-by-one and print the resulting CoA IDs.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import httpx


def login(api: str, email: str, password: str) -> str:
    r = httpx.post(f"{api}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def upload(api: str, token: str, pdf: Path, method: str) -> dict:
    with pdf.open("rb") as f:
        r = httpx.post(
            f"{api}/coas/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"ingestion_method": method},
            files={"file": (pdf.name, f, "application/pdf")},
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


def list_via_service_account(folder_id: str, sa_path: Path) -> list[tuple[str, str]]:
    """Returns [(file_id, name)] for PDFs in folder. Requires google-api-python-client."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        str(sa_path), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    files: list[tuple[str, str]] = []
    page_token = None
    while True:
        resp = svc.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
            spaces="drive",
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
            pageSize=200,
        ).execute()
        files.extend((f["id"], f["name"]) for f in resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def download_via_service_account(file_id: str, dest: Path, sa_path: Path) -> None:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    creds = service_account.Credentials.from_service_account_file(
        str(sa_path), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    request = svc.files().get_media(fileId=file_id)
    with dest.open("wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def parse_folder_id(url_or_id: str) -> str:
    if "/folders/" in url_or_id:
        return url_or_id.split("/folders/")[1].split("/")[0].split("?")[0]
    return url_or_id


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--folder-url", required=True, help="Drive folder URL or ID")
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--email", default="admin@example.com")
    p.add_argument("--password", default="admin")
    p.add_argument("--method", default="upload", choices=["upload", "scan", "email", "api"])
    p.add_argument("--service-account", help="Path to Google service-account JSON (private folders)")
    p.add_argument("--limit", type=int, default=0, help="Max files (0 = all)")
    args = p.parse_args()

    folder_id = parse_folder_id(args.folder_url)
    print(f"[i] folder_id = {folder_id}")
    print(f"[i] api       = {args.api}")
    token = login(args.api, args.email, args.password)
    print(f"[i] auth ok as {args.email}")

    pdfs: list[Path] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if args.service_account:
            print("[i] using service account to list & download")
            files = list_via_service_account(folder_id, Path(args.service_account))
            print(f"[i] {len(files)} PDFs in folder")
            if args.limit:
                files = files[: args.limit]
            for fid, name in files:
                dest = tmp_dir / name
                download_via_service_account(fid, dest, Path(args.service_account))
                pdfs.append(dest)
        else:
            try:
                import gdown  # noqa
            except ImportError:
                print("ERROR: install gdown (pip install gdown) or pass --service-account",
                      file=sys.stderr)
                return 2
            import gdown
            print("[i] using gdown (public folder mode)")
            gdown.download_folder(
                f"https://drive.google.com/drive/folders/{folder_id}",
                output=str(tmp_dir),
                quiet=False,
                use_cookies=False,
            )
            pdfs = sorted(p for p in tmp_dir.rglob("*.pdf"))
            if args.limit:
                pdfs = pdfs[: args.limit]
            print(f"[i] {len(pdfs)} PDFs downloaded")

        ok, fail = 0, 0
        for pdf in pdfs:
            try:
                res = upload(args.api, token, pdf, args.method)
                ok += 1
                print(f"[+] {pdf.name} -> {res['id']} (doc {res.get('doc_code')}, batch {res.get('batch_number')})")
            except Exception as e:
                fail += 1
                print(f"[!] {pdf.name}: {e}", file=sys.stderr)

    print(json.dumps({"uploaded": ok, "failed": fail, "total": len(pdfs)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
