# Bachhoaxanh.com Web Crawler

Đây là bộ công cụ crawl dữ liệu danh mục và sản phẩm từ trang web bachhoaxanh.com. 

## Cài đặt

Đầu tiên, tạo môi trường ảo Python:

```bash
# Tạo môi trường ảo
python -m venv venv_crawler

# Kích hoạt môi trường ảo (Windows)
venv_crawler\Scripts\activate

# Kích hoạt môi trường ảo (Linux/Mac)
source venv_crawler/bin/activate
```

Cài đặt các gói thư viện cần thiết:

```bash
pip install playwright beautifulsoup4 requests
python -m playwright install
```

## Sử dụng

### 1. Crawl danh mục và danh mục con

```bash
python playwright_category_crawler.py
```

Mặc định, kết quả sẽ được lưu vào `data/categories_playwright.json`.

Bạn có thể tùy chỉnh tên file đầu ra:

```bash
python playwright_category_crawler.py --output custom_filename.json
```

### 2. Phân tích dữ liệu danh mục

```bash
python analyze_categories.py
```

Tùy chọn:
- `--input` hoặc `-i`: Đường dẫn file JSON đầu vào (mặc định: `data/categories_playwright.json`)
- `--export` hoặc `-e`: Xuất kết quả dưới dạng Markdown (nếu cung cấp đường dẫn file)
- `--check-urls` hoặc `-c`: Kiểm tra xem các URL có hoạt động không
- `--max-urls` hoặc `-m`: Số lượng URL kiểm tra tối đa (mặc định: 5)

Ví dụ:
```bash
python analyze_categories.py --export categories.md --check-urls --max-urls 10
```

### 3. Kiểm tra tất cả URL

```bash
python check_all_urls.py 
```

Tùy chọn:
- `--input` hoặc `-i`: Đường dẫn file JSON đầu vào (mặc định: `data/categories_playwright.json`)
- `--workers` hoặc `-w`: Số lượng worker đồng thời (mặc định: 4)

Ví dụ:
```bash
python check_all_urls.py --workers 2
```

## Cấu trúc dự án

- `playwright_category_crawler.py`: Script chính để crawl danh mục từ bachhoaxanh.com
- `config_playwright.py`: Cấu hình cho crawler (URL, selector, browser, etc.)
- `analyze_categories.py`: Phân tích dữ liệu đã crawl được
- `check_all_urls.py`: Kiểm tra xem tất cả URL có hoạt động không
- `data/`: Thư mục chứa dữ liệu
  - `categories_playwright.json`: Kết quả crawl danh mục
  - `screenshots/`: Thư mục chứa ảnh chụp màn hình và HTML để debug

## Tính năng

- Crawl tất cả danh mục chính và danh mục con
- Tạo URL slug chuẩn từ tên danh mục
- Phân tích dữ liệu và hiển thị thống kê
- Kiểm tra tính khả dụng của tất cả URL
- Xuất dữ liệu dưới dạng Markdown

## Lưu ý

- Khi chạy crawler, hãy cẩn thận với tần suất yêu cầu để tránh bị chặn bởi website
- Đã thêm User-Agent trong request để tránh lỗi 403 Forbidden
- Crawler sử dụng Playwright nên phải cài đặt browser driver 