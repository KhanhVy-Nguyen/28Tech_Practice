import os
import re
import subprocess
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup 

# ================= CẤU HÌNH =================
USERNAME = "Khanh_Vy_NN_2007"

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
    Chuyển đổi chuỗi "8:37:36 am, 05/09/2026" sang định dạng ISO cho Git
    """
    clean_str = raw_time_str.strip()
    dt = datetime.strptime(clean_str, "%I:%M:%S %p, %d/%m/%Y")
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def get_submission_code(source_url):
    """Truy cập trang view source để lấy code từ nút Copy"""
    res = requests.get(source_url, headers=HEADERS, cookies=COOKIES)
    if res.status_code != 200:
        return None
    soup = BeautifulSoup(res.text, "html.parser")

    copy_btn = soup.find("span", class_="btn-clipboard")
    if copy_btn and copy_btn.has_attr("data-clipboard-text"):
        return copy_btn["data-clipboard-text"]

    return None


'''gemini
def get_submission_code(source_url):
    """Truy cập trang view source để lấy code"""
    res = requests.get(source_url, headers=HEADERS, cookies=COOKIES)
    if res.status_code != 200:
        return None
    soup = BeautifulSoup(res.text, "html.parser")
    
    # Mã nguồn thường nằm trong thẻ <code> hoặc <pre>
    code_tag = soup.find("code") or soup.find("pre")
    if code_tag:
        return code_tag.get_text()
    return None
'''
def run():
    page = 1
    total_commits = 0

    while True:
        url = f"{USER_SUBMISSIONS_URL}?page={page}"
        print(f"--- Đang cào trang {page}: {url} ---")
        res = requests.get(url, headers=HEADERS, cookies=COOKIES)
        if res.status_code != 200:
            print("Không thể tải trang hoặc đã hết danh sách.")
            break

        soup = BeautifulSoup(res.text, "html.parser")
        
        # Tìm tất cả các hàng bài nộp
        # Trên DMOJ thông thường mỗi hàng là một thẻ chứa thông tin bài nộp
        rows = soup.find_all("div", class_=re.compile(r"submission-row|submission"))
        
        # Nếu giao diện dùng bảng table:
        if not rows:
            table = soup.find("table")
            if table:
                rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")

        if not rows:
            print("Không tìm thấy bài nộp nào trên trang này. Dừng cào.")
            break

        has_submission_in_page = False

        for row in rows:
            # 1. Kiểm tra trạng thái AC
            status_tag = row.find(text=re.compile(r"AC"))
            if not status_tag:
                # Nếu chỉ muốn lưu bài AC thì bỏ qua bài không AC
                continue

            # 2. Tìm link view source
            source_link_tag = row.find("a", href=re.compile(r"/source/|/submission/"))
            if not source_link_tag or "view" not in source_link_tag.text.lower():
                # Tìm thẻ a có chữ view source
                source_link_tag = row.find("a", string=re.compile(r"view\s*source", re.I))

            if not source_link_tag:
                continue

            source_url = BASE_URL + source_link_tag["href"]

            # 3. Lấy tên bài
            # Tìm thẻ link trỏ về problem
            prob_tag = row.find("a", href=re.compile(r"/problem/"))
            prob_name = clean_filename(prob_tag.text) if prob_tag else "Unknown_Problem"

            # 4. Lấy thời gian nộp bài
            time_tag = row.find(text=re.compile(r"\d{1,2}:\d{2}:\d{2}\s*(am|pm),\s*\d{2}/\d{2}/\d{4}", re.I))
            if not time_tag:
                continue

            iso_date = parse_submission_time(time_tag)
            has_submission_in_page = True

            # 5. Tải source code bài nộp
            print(f"Đang tải: {prob_name} ({iso_date})...")
            code_text = get_submission_code(source_url)
            if not code_text:
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

            time.sleep(0.5) # Tránh gửi request quá dồn dập

        if not has_submission_in_page:
            print("Đã duyệt hết các trang có bài.")
            break

        page += 1

    print(f"\n Hoàn tất! Đã tạo thành công {total_commits} commit.")

if __name__ == "__main__":
    run()