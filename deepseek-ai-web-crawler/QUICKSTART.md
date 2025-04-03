# Hướng Dẫn Nhanh Chóng Chạy Web Crawler

Đây là hướng dẫn nhanh để bắt đầu sử dụng web crawler Bách Hoá Xanh. Để biết hướng dẫn chi tiết hơn, xem file [README.md](README.md).

## Bước 1: Cài đặt môi trường

```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt môi trường ảo (Windows)
venv\Scripts\activate

# Kích hoạt môi trường ảo (macOS/Linux)
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt

# Cài đặt trình duyệt Playwright
playwright install
```

## Bước 2: Thu thập danh mục

```bash
python category_crawler.py
```

## Bước 3: Thu thập sản phẩm

### Ví dụ 1: Thu thập 10 sản phẩm từ 1 danh mục con

```bash
python playwright_product_crawler.py --subcategories 1 --products 10
```

### Ví dụ 2: Thu thập 20 sản phẩm từ 2 danh mục con và xuất ra CSV, Excel

```bash
python playwright_product_crawler.py --subcategories 2 --products 20 --csv --excel
```

## Bước 4: Xem dữ liệu

Dữ liệu được lưu trong thư mục `data/`:
- Sản phẩm: `data/products/`
- Hình ảnh: `data/images/`
- Báo cáo: `data/products/crawl_summary_*.txt`

## Các tham số tuỳ chọn

| Tham số | Mô tả | Mặc định |
|---------|-------|----------|
| `--categories` | Số lượng danh mục cần crawl | tất cả |
| `--subcategories` | Số lượng danh mục con cần crawl | tất cả |
| `--products` | Số lượng sản phẩm cần crawl từ mỗi danh mục con | 20 |
| `--csv` | Xuất dữ liệu ra file CSV | không |
| `--excel` | Xuất dữ liệu ra file Excel | không |

## Cấu trúc thư mục dữ liệu

```
data/
├── categories_playwright.json     # Dữ liệu danh mục
├── products/
│   ├── subcategory_timestamp.json # Dữ liệu sản phẩm JSON
│   ├── subcategory_timestamp.csv  # Dữ liệu sản phẩm CSV
│   ├── subcategory_timestamp.xlsx # Dữ liệu sản phẩm Excel
│   └── crawl_summary_*.txt        # Báo cáo tổng hợp
├── images/
│   └── subcategory/
│       └── product_id/
│           ├── 1.jpg              # Hình ảnh sản phẩm
│           ├── thumb_1.jpg        # Thumbnail
│           └── index.html         # Trang gallery
└── screenshots/
    └── subcategory_*.png          # Ảnh chụp màn hình
``` 