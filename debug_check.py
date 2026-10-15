import os
import requests
from bs4 import BeautifulSoup

USERNAME = "Khanh_Vy_NN_2007"
SESSION_ID = os.environ.get("SESSION_ID", "vn7ovt39amqy61faw88t2o4kohzli1p0")

BASE_URL = "https://oj.28tech.com.vn"
URL = f"{BASE_URL}/submissions/user/{USERNAME}/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
COOKIES = {"sessionid": SESSION_ID}

res = requests.get(URL, headers=HEADERS, cookies=COOKIES)
soup = BeautifulSoup(res.text, "html.parser")

name_div = soup.find("div", class_="name")
if name_div:
    # Lấy khối cha bọc toàn bộ dòng bài nộp
    row_container = name_div.parent
    print("--- CẤU TRÚC ĐẦY ĐỦ 1 HÀNG BÀI NỘP ---")
    print(row_container.prettify()[:1500])