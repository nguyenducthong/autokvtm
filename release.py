import subprocess
import re
import sys
import os

def main():
    try:
        # 1. Nhập phiên bản mới
        version = input("Nhập phiên bản mới (ví dụ: 1.0.1): ").strip()
        if not version:
            print("Phiên bản không được để trống!")
            return
            
        # Chuẩn hóa tag (v1.0.1) và số phiên bản (1.0.1)
        tag = f"v{version}" if not version.lower().startswith("v") else version
        version_num = tag[1:] if tag.lower().startswith("v") else tag

        # Nhập ghi chú / nội dung cập nhật của phiên bản
        notes = input("Nhập ghi chú / nội dung cập nhật cho phiên bản này: ").strip()
        if not notes:
            notes = f"Phát hành phiên bản {tag}"
        
        # 2. Cập nhật file config.py
        config_path = "config.py"
        if not os.path.exists(config_path):
            print("Không tìm thấy file config.py ở thư mục hiện tại!")
            return
            
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Tìm và thay thế CURRENT_VERSION = "..."
        pattern = r'(CURRENT_VERSION\s*=\s*")[^"]*(")'
        if not re.search(pattern, content):
            print("Không tìm thấy biến CURRENT_VERSION trong config.py!")
            return
            
        new_content = re.sub(pattern, f'\\g<1>{version_num}\\g<2>', content)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"-> Đã cập nhật CURRENT_VERSION = '{version_num}' trong config.py")

        # Lưu ghi chú vào file release_notes.txt để GitHub Actions làm mô tả Release
        with open("release_notes.txt", "w", encoding="utf-8") as f:
            f.write(notes)
        print(f"-> Đã lưu nội dung cập nhật vào release_notes.txt")
        
        # 3. Chạy các lệnh Git
        print("\n-> Đang thêm thay đổi vào git (git add)...")
        subprocess.run(["git", "add", "."], check=True)
        
        commit_msg = f"Cập nhật phiên bản {tag}\n\n{notes}"
        print("-> Đang commit thay đổi (git commit)...")
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        print(f"-> Đang tạo tag {tag} kèm ghi chú...")
        # Xóa tag cục bộ cũ nếu trùng lặp để tránh lỗi
        subprocess.run(["git", "tag", "-d", tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "tag", "-a", tag, "-m", notes], check=True)
        
        print("-> Đang đẩy code lên nhánh main (git push)...")
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        print(f"-> Đang đẩy tag {tag} lên GitHub...")
        # Đẩy tag đè lên nếu đã có trên remote (tùy chọn)
        subprocess.run(["git", "push", "origin", f":refs/tags/{tag}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "push", "origin", tag], check=True)
        
        print(f"\n[THÀNH CÔNG] Đã đẩy phiên bản {tag} lên GitHub!")
        print("GitHub Actions đang tự động đóng gói ứng dụng và tạo Release mới.")
        print("Bạn có thể lên trang GitHub -> tab Actions để kiểm tra tiến trình.")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[LỖI GIT]: Quá trình chạy lệnh Git thất bại: {e}")
    except Exception as e:
        print(f"\n[LỖI]: {e}")

if __name__ == "__main__":
    main()
    print("\n" + "="*50)
    input("Nhấn Enter để thoát...")
