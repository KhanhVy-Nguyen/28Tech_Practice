import os
import requests
from bs4 import BeautifulSoup

# Never store login cookies in source control or print them in logs.
session_id = os.environ.get("SESSION_ID")
if not session_id:
    raise SystemExit("Missing SESSION_ID environment variable")
response = requests.get(
    "https://oj.28tech.com.vn/submissions/user/Khanh_Vy_NN_2007/",
    cookies={"sessionid": session_id}, timeout=30,
)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")
from crawl_and_commit import submission_rows
rows = submission_rows(soup)
print("Detected submission rows:", len(rows))
if rows:
    print(next(iter(rows.values())).prettify()[:10000])
