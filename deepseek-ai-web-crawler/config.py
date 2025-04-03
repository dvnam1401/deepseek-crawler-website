# config.py
import os
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

# Cấu hình cơ bản
BASE_URL = "https://www.bachhoaxanh.com/"
CATEGORY_CSS_SELECTOR = ".mb-2.flex.flex-wrap .cate"  # Nhắm đến các .cate bên trong .mb-2.flex.flex-wrap
PRODUCT_CSS_SELECTOR = ".box_product"  # Để sau kiểm tra tương tự

# Selector backup để trích xuất thông tin sản phẩm
SELECTORS = {
    "name": [
        "h1.title", 
        ".product_name", 
        "h1", 
        ".product-title", 
        "meta[property='og:title']"
    ],
    "price": [
        ".product_price", 
        ".price span", 
        ".current-price", 
        "span.price"
    ],
    "original_price": [
        "div.line-through", 
        ".text-[#9da7bc].line-through", 
        ".original-price"
    ],
    "discount": [
        "span.bg-red", 
        ".promotion-badge", 
        ".discount"
    ],
    "description": [
        ".detail-style p", 
        ".mb-4px.block.leading-3", 
        ".product-description", 
        ".detail-content"
    ]
}

# Trường dữ liệu bắt buộc cho sản phẩm
REQUIRED_KEYS = [
    "name",
    "category",
    "price",
    "description",
    "product_url",
]

# Cấu hình output
OUTPUT_DIR = "data"  # Thư mục lưu dữ liệu
OUTPUT_FILE_CSV = "products.csv"  # Tên file CSV mặc định
OUTPUT_FILE_JSON = "products.json"  # Tên file JSON mặc định

# Cấu hình crawler
MAX_RETRIES = 3  # Số lần thử lại tối đa
WAIT_TIME = 45   # Thời gian chờ tối đa (giây)
CRAWL_DELAY = 2  # Thời gian chờ giữa các request (giây)
SCROLL_TIME = 20  # Thời gian tối đa để scroll trang (giây)

# Cấu hình đa luồng/đa tiến trình
MAX_WORKERS = 4  # Số worker tối đa cho đa luồng/đa tiến trình
BATCH_SIZE = 10  # Số sản phẩm tối đa trong một batch

# Cấu hình LLM (AI)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq/deepseek-r1-distill-llama-70b")  # Provider mặc định
LLM_API_KEY = os.getenv("GROQ_API_KEY")  # API key (được tải từ .env)

# Cấu hình proxy (nếu cần)
USE_PROXY = os.getenv("USE_PROXY", "False").lower() == "true"
PROXY_URL = os.getenv("PROXY_URL", "")

# Cấu hình timeout
CONNECTION_TIMEOUT = 30  # Timeout kết nối (giây)
READ_TIMEOUT = 60  # Timeout đọc (giây)

# Cấu hình user agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
