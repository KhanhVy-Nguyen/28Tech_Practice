import os
import re
import subprocess
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup 

# ================= CẤU HÌNH =================
USERNAME = "Khanh_Vy_NN_2007"

# Nếu chạy trên máy tính cá nhân, bạn hãy dán cookie sessionid thật vào giữa 2 dấu "" bên dưới:
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

def get_submission_code(source_url):
    """Truy cập trang view source để lấy code"""
    try:
        res = requests.get(source_url, headers=HEADERS, cookies=COOKIES, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Thử lấy từ thuộc tính data-clipboard-text của nút Copy
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
        
        # 28tech hiển thị danh sách bài qua các khối thẻ div class="sub-info"
        sub_info_elements = soup.find_all("div", class_="sub-info")

        if not sub_info_elements:
            print("Không tìm thấy bài nộp nào trên trang này. Dừng cào.")
            break

        has_submission_in_page = False

        for sub_info in sub_info_elements:
            # Khối cha bọc ngoài cùng chứa cả trạng thái bài làm và link source
            row_container = sub_info.parent
            row_text = row_container.get_text()

            # 1. Kiểm tra trạng thái AC / Accepted
            if not re.search(r"\b(AC|Accepted)\b", row_text, re.I):
                continue

            # 2. Tìm link view source hoặc submission ID
            source_link_tag = row_container.find("a", href=lambda h: h and ("/source/" in h or "/submission/" in h))
            if not source_link_tag:
                continue

            source_url = BASE_URL + source_link_tag["href"]

            # 3. Lấy tên bài từ link /problem/ bên trong sub-info
            prob_tag = sub_info.find("a", href=lambda h: h and "/problem/" in h)
            prob_name = clean_filename(prob_tag.text) if prob_tag else "Unknown_Problem"

            # 4. Lấy thời gian ISO trực tiếp từ thuộc tính data-iso trên 28tech
            time_elem = sub_info.find("span", attrs={"data-iso": True})
            if time_elem and time_elem.get("data-iso"):
                # Cắt chuỗi ISO dạng 2026-10-04T11:18:32.152568+00:00 lấy 19 ký tự chuẩn Git
                iso_date = time_elem["data-iso"][:19]
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
            print("Đã duyệt hết các bài nộp AC.")
            break

        page += 1

    print("\n==========================================")
    print(f"Hoàn tất! Đã tạo thành công {total_commits} commit.")
    print("==========================================")

if __name__ == "__main__":
    run()