#!/usr/bin/env python3
"""
File cấu hình cho Crawler
"""

# URL cơ sở của trang web cần crawl
BASE_URL = "https://www.bachhoaxanh.com"

# CSS Selector để tìm các phần tử danh mục chính
CATEGORY_CSS_SELECTOR = ".cate_parent .text-14.font-semibold.uppercase"

# Các selector để tìm danh mục con
SUBCATEGORY_SELECTORS = [
    ".cate_parent .cate",
    ".overflow-hidden .cate"
]

# Thư mục lưu dữ liệu
OUTPUT_DIR = "data"

# Thời gian chờ tối đa khi tải trang (giây)
WAIT_TIME = 60

# Số lần thử lại tối đa khi gặp lỗi
MAX_RETRIES = 3

# Thời gian chờ giữa các request (giây)
CRAWL_DELAY = 1

# Cấu hình cho trình duyệt
BROWSER_CONFIG = {
    "headless": False,  # True để chạy ẩn, False để hiển thị UI
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
} 