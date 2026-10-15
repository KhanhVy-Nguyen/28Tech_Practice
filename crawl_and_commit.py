import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("OJ_USERNAME", "Khanh_Vy_NN_2007")
BASE_URL = "https://oj.28tech.com.vn"
ROOT = Path(__file__).resolve().parent
SUBMISSION_LINK = re.compile(r"/(?:submission|source)/(\d+)(?:/|$)")


def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_").rstrip(". ") or "Unknown_Problem"


def git(*args, **kwargs):
    # Trust only this checkout for this invocation, without changing global settings.
    return subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT, check=True, capture_output=True, text=True, **kwargs
    )


def fetch(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    if "login" in urlparse(response.url).path or soup.select_one('input[type="password"]'):
        raise RuntimeError("Chua dang nhap hoac SESSION_ID da het han. Cap nhat GitHub Secret SESSION_ID.")
    return soup


def submission_rows(soup):
    """Find the enclosing submission row, rather than assuming sub-info.parent."""
    found = {}
    for row in soup.select('.submission-row[id]'):
        sid = row.get('id', '')
        if sid.isdigit() and row.select_one('a[href*="/problem/"]'):
            found[sid] = row
    for link in soup.find_all("a", href=True):
        match = SUBMISSION_LINK.search(link["href"])
        if not match:
            continue
        for parent in link.parents:
            if parent.name in ("body", "html"):
                break
            # A complete row has a problem link; stop before enclosing multiple rows.
            if parent.select_one('a[href*="/problem/"]'):
                ids = {m.group(1) for a in parent.find_all("a", href=True)
                       if (m := SUBMISSION_LINK.search(a["href"]))}
                if ids == {match.group(1)}:
                    found.setdefault(match.group(1), parent)
                    break
    return found


def is_accepted(row):
    if re.search(r"\b(?:AC|Accepted)\b", row.get_text(" ", strip=True), re.I):
        return True
    return bool(row.select_one('.AC, .ac, [data-result="AC"], [title="Accepted"]'))


def get_submission_code(session, submission_id):
    soup = fetch(session, f"{BASE_URL}/src/{submission_id}")
    copy = soup.find(attrs={"data-clipboard-text": True})
    if copy and copy["data-clipboard-text"].strip():
        return copy["data-clipboard-text"]
    code = soup.select_one("#content pre code, #content pre, pre code, pre, textarea#source, textarea#id_source")
    if code and code.get_text().strip():
        return code.get_text()
    raise RuntimeError(f"Khong lay duoc source bai nop {submission_id}; kiem tra quyen xem source va SESSION_ID.")


def run():
    if not os.environ.get("SESSION_ID"):
        raise RuntimeError("Thieu SESSION_ID. Dat bien moi truong hoac GitHub Actions Secret SESSION_ID.")
    git("rev-parse", "--show-toplevel")
    if git("diff", "--cached", "--name-only").stdout.strip():
        raise RuntimeError("Dang co file staged. Hay commit/unstage truoc khi chay.")
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (28tech personal solutions backup)"
    session.cookies.set("sessionid", os.environ["SESSION_ID"], domain="oj.28tech.com.vn")
    seen = set()
    commits = 0
    failures = 0
    page = 1
    while True:
        url = f"{BASE_URL}/submissions/user/{USERNAME}/" + (str(page) if page > 1 else "")
        print(f"\n--- Dang cao trang {page}: {url} ---", flush=True)
        soup = fetch(session, url)
        rows = submission_rows(soup)
        if not rows:
            if page == 1 or soup.select_one(".sub-info"):
                raise RuntimeError("Khong nhan dien duoc dong bai nop. Kiem tra username, dang nhap va HTML cua 28tech.")
            break
        fresh = {sid: row for sid, row in rows.items() if sid not in seen}
        if not fresh:
            raise RuntimeError("Trang bi lap: server khong chuyen trang. Dung de tranh vong lap.")
        seen.update(fresh)
        accepted = [(sid, row) for sid, row in fresh.items() if is_accepted(row)]
        print(f"Tim thay {len(fresh)} bai nop, {len(accepted)} bai AC.")
        for sid, row in accepted:
            # Stable per-submission paths preserve different accepted attempts and languages.
            relative = Path("solutions") / f"submission_{sid}" / "source.txt"
            path = ROOT / relative
            if path.exists():
                continue
            try:
                code = get_submission_code(session, sid)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(code, encoding="utf-8")
                git("add", "--", relative.as_posix())
                problem = row.select_one('a[href*="/problem/"]')
                name = problem.get_text(" ", strip=True)
                env = os.environ.copy()
                timestamp = row.select_one("[data-iso]")
                if timestamp:
                    # Retain the original UTC offset instead of truncating it.
                    env["GIT_AUTHOR_DATE"] = timestamp["data-iso"]
                    env["GIT_COMMITTER_DATE"] = timestamp["data-iso"]
                git("commit", "-m", f"Solve {name} (submission {sid})", "--", relative.as_posix(), env=env)
                commits += 1
                print(f"Da commit: {name} ({sid})", flush=True)
            except (requests.RequestException, RuntimeError) as exc:
                failures += 1
                print(f"LOI bai {sid}: {exc}", file=sys.stderr)
            time.sleep(0.5)
        # An AC-free page is not the end of the submission history.
        next_link = soup.select_one('a[rel="next"], .pagination a.next, a.next-page')
        numeric_next = soup.find("a", href=lambda href: href and re.search(rf"[?&]page={page + 1}(?:&|$)", href))
        if not numeric_next:
            numeric_next = next((a for a in soup.select('.pagination a[href]')
                                 if a.get('href') == str(page + 1)), None)
        if not next_link and not numeric_next:
            break
        page += 1
    print(f"Hoan tat: {commits} commit moi, {failures} loi tai source.")
    if failures:
        raise RuntimeError("Mot so bai chua tai duoc. Xem log loi phia tren va chay lai.")


if __name__ == "__main__":
    try:
        run()
    except (requests.RequestException, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"LOI: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr or exc.stdout, file=sys.stderr)
        sys.exit(1)
