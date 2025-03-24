# config.py
BASE_URL = "https://www.bachhoaxanh.com/"
CATEGORY_CSS_SELECTOR = ".mb-2.flex.flex-wrap .cate"  # Nhắm đến các .cate bên trong .mb-2.flex.flex-wrap
PRODUCT_CSS_SELECTOR = ".box_product"  # Để sau kiểm tra tương tự
REQUIRED_KEYS = [
    "name",
    "category",
    "price",
    "description",
    "product_url",
]
