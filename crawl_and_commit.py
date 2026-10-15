import os
import re
import subprocess
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup 

# ================= CẤU HÌNH =================
USERNAME = "Khanh_Vy_NN_2007"

# Nếu chạy trên máy tính cá nhân, bạn có thể dán tạm cookie sessionid vào chuỗi rỗng bên dưới:
SESSION_ID = os.environ.get("SESSION_ID", "")

BASE_URL = "https://oj.28tech.com.vn"
USER_SUBMISSIONS_URL = f"{BASE_URL}/submissions/user/{USERNAME}/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
COOKIES = {
    "sessionid": SESSION_ID
}

def clean_filename(name):
    # Loại bỏ ký tự đặc biệt để tạo tên file/folder hợp lệ
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    return name.strip().replace(" ", "_")

def parse_submission_time(raw_time_str):
    """
    Chuyển đổi các định dạng thời gian nộp bài sang chuẩn ISO (YYYY-MM-DDTHH:MM:SS) cho Git
    """
    clean_str = raw_time_str.strip()
    date_formats = [
        "%I:%M:%S %p, %d/%m/%Y",  # 8:37:36 am, 05/09/2026
        "%H:%M:%S, %d/%m/%Y",     # 08:37:36, 05/09/2026
        "%d/%m/%Y %H:%M:%S",     # 05/09/2026 08:37:36
        "%d/%m/%Y %H:%M",        # 05/09/2026 08:37
    ]
    for fmt in date_formats:
        try:
            dt = datetime.strptime(clean_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def get_submission_code(source_url):
    """Truy cập trang view source để lấy code"""
    try:
        res = requests.get(source_url, headers=HEADERS, cookies=COOKIES, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Thử lấy từ nút Copy trên giao diện DMOJ
        copy_btn = soup.find(attrs={"data-clipboard-text": True})
        if copy_btn:
            return copy_btn["data-clipboard-text"]

        # 2. Thử tìm trong thẻ <code> hoặc <pre>
        code_tag = soup.find("code") or soup.find("pre")
        if code_tag:
            return code_tag.get_text()
    except Exception as e:
        print(f"Lỗi khi tải mã nguồn từ {source_url}: {e}")
    return None

def run():
    page = 1
    total_commits = 0

    while True:
        url = f"{USER_SUBMISSIONS_URL}?page={page}"
        print(f"\n--- Đang cào trang {page}: {url} ---")
        try:
            res = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=10)
        except Exception as e:
            print(f"Lỗi kết nối tới server: {e}")
            break

        if res.status_code != 200:
            print(f"Không thể tải trang (Mã lỗi: {res.status_code}) hoặc đã hết danh sách.")
            break

        soup = BeautifulSoup(res.text, "html.parser")
        
        # Tìm bảng danh sách bài nộp
        table = soup.find("table")
        rows = []
        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")
        else:
            rows = soup.find_all("div", class_=re.compile(r"submission-row|submission"))

        if not rows:
            print("Không tìm thấy hàng bài nộp nào trên trang này. Dừng cào.")
            break

        has_submission_in_page = False

        for row in rows:
            row_text = row.get_text()

            # 1. Kiểm tra trạng thái AC / Accepted
            if not re.search(r"\b(AC|Accepted)\b", row_text, re.I):
                continue

            # 2. Tìm link view source hoặc submission ID
            source_link_tag = row.find("a", href=re.compile(r"/(source|submission)/\d+"))
            if not source_link_tag:
                continue

            source_url = BASE_URL + source_link_tag["href"]

            # 3. Lấy tên bài
            prob_tag = row.find("a", href=re.compile(r"/problem/"))
            prob_name = clean_filename(prob_tag.text) if prob_tag else "Unknown_Problem"

            # 4. Lấy thời gian nộp bài linh hoạt
            time_tag = row.find(string=re.compile(r"\d{1,2}:\d{2}", re.I))
            if time_tag:
                iso_date = parse_submission_time(time_tag)
            else:
                time_elem = row.find("time")
                if time_elem and time_elem.has_attr("datetime"):
                    iso_date = time_elem["datetime"][:19]
                else:
                    iso_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            has_submission_in_page = True

            # 5. Tải source code bài nộp
            print(f"-> Đang tải: {prob_name} ({iso_date})...")
            code_text = get_submission_code(source_url)
            if not code_text:
                print(f"   [!] Không lấy được mã nguồn của bài {prob_name}")
                continue

            # 6. Ghi file và thực hiện Git Commit quay ngược thời gian
            folder_path = os.path.join("solutions", prob_name)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, "solution.cpp")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code_text)

            subprocess.run(["git", "add", file_path], check=True)

            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = iso_date
            env["GIT_COMMITTER_DATE"] = iso_date

            commit_msg = f"Solve {prob_name}"
            commit_res = subprocess.run(["git", "commit", "-m", commit_msg], env=env, capture_output=True, text=True)
            if commit_res.returncode == 0:
                total_commits += 1

            time.sleep(0.3)  # Giảm độ trễ nhẹ nhàng để tải mượt hơn

        if not has_submission_in_page:
            print("Đã duyệt hết các bài nộp hợp lệ.")
            break

        page += 1

    print("\n==========================================")
    print(f"Hoàn tất! Đã tạo thành công {total_commits} commit.")
    print("==========================================")

if __name__ == "__main__":
    run()