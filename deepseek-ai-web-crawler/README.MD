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

# Hướng Dẫn Triển Khai Web Crawler

Hướng dẫn này mô tả chi tiết các bước triển khai và chạy Web Crawler để thu thập dữ liệu sản phẩm từ trang web Bách Hoá Xanh.

## Mục Lục

1. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
2. [Cài đặt môi trường](#cài-đặt-môi-trường)
3. [Cấu hình crawler](#cấu-hình-crawler)
4. [Thu thập danh mục](#thu-thập-danh-mục)
5. [Thu thập sản phẩm](#thu-thập-sản-phẩm)
6. [Xuất dữ liệu](#xuất-dữ-liệu)
7. [Xử lý hình ảnh](#xử-lý-hình-ảnh)
8. [Báo cáo và thống kê](#báo-cáo-và-thống-kê)
9. [Xử lý lỗi phổ biến](#xử-lý-lỗi-phổ-biến)

## Yêu Cầu Hệ Thống

- Python 3.8 trở lên
- Windows, macOS hoặc Linux
- Kết nối internet ổn định
- Ít nhất 4GB RAM
- Đủ dung lượng ổ đĩa để lưu trữ dữ liệu và hình ảnh (khuyến nghị ít nhất 5GB)

## Cài Đặt Môi Trường

### Bước 1: Cài đặt Python

Tải và cài đặt Python phiên bản 3.8 trở lên từ [trang chủ Python](https://www.python.org/downloads/).

### Bước 2: Tải mã nguồn

Clone hoặc tải mã nguồn từ kho lưu trữ:

```bash
git clone <repository-url>
cd <project-folder>
```

### Bước 3: Tạo môi trường ảo

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Bước 4: Cài đặt các thư viện

```bash
pip install -r requirements.txt
```

### Bước 5: Cài đặt trình duyệt Playwright

```bash
playwright install
```

## Cấu Hình Crawler

### Cấu hình cơ bản

Tệp `config_playwright.py` chứa các cấu hình cơ bản. Kiểm tra và điều chỉnh thông số theo nhu cầu:

```python
# Thư mục đầu ra
OUTPUT_DIR = "data"

# Cấu hình domain và URL gốc
BASE_URL = "https://www.bachhoaxanh.com"

# Số lần thử lại khi gặp lỗi
MAX_RETRIES = 3

# Thời gian chờ tối đa (giây)
REQUEST_TIMEOUT = 30

# Thời gian chờ giữa các request (giây)
MIN_DELAY = 1
MAX_DELAY = 3

# Số lượng hình ảnh tối đa cho mỗi sản phẩm
MAX_IMAGES_PER_PRODUCT = 10
```

## Thu Thập Danh Mục

### Bước 1: Chạy crawler danh mục

Crawler sẽ thu thập thông tin về các danh mục và danh mục con trên trang web:

```bash
python category_crawler.py
```

Kết quả sẽ được lưu trong tệp `data/categories_playwright.json`.

### Bước 2: Kiểm tra dữ liệu danh mục

Kiểm tra file `data/categories_playwright.json` để đảm bảo dữ liệu danh mục đã được thu thập đúng.

## Thu Thập Sản Phẩm

### Cách sử dụng

Cú pháp cơ bản để chạy crawler sản phẩm:

```bash
python playwright_product_crawler.py [options]
```

### Tham số tuỳ chọn

- `--categories`: Số lượng danh mục cần crawl (mặc định: tất cả)
- `--subcategories`: Số lượng danh mục con cần crawl (mặc định: tất cả)
- `--products`: Số lượng sản phẩm cần crawl từ mỗi danh mục con (mặc định: 20)
- `--csv`: Xuất dữ liệu ra file CSV
- `--excel`: Xuất dữ liệu ra file Excel

### Ví dụ

#### Thu thập tất cả sản phẩm từ tất cả danh mục

```bash
python playwright_product_crawler.py
```

#### Thu thập 10 sản phẩm từ 5 danh mục con

```bash
python playwright_product_crawler.py --subcategories 5 --products 10
```

#### Thu thập 20 sản phẩm từ 2 danh mục con và xuất ra CSV, Excel

```bash
python playwright_product_crawler.py --subcategories 2 --products 20 --csv --excel
```

## Xuất Dữ Liệu

Dữ liệu sản phẩm được lưu trữ theo các định dạng sau:

### JSON (Mặc định)

Dữ liệu JSON được lưu trong tệp `data/products/<subcategory>_<timestamp>.json`.

### CSV

Để xuất dữ liệu dưới dạng CSV:

```bash
python playwright_product_crawler.py --csv
```

File CSV sẽ được lưu tại `data/products/<subcategory>_<timestamp>.csv`.

### Excel

Để xuất dữ liệu dưới dạng Excel:

```bash
python playwright_product_crawler.py --excel
```

File Excel sẽ được lưu tại `data/products/<subcategory>_<timestamp>.xlsx`.

## Xử Lý Hình Ảnh

Crawler tự động tải xuống hình ảnh sản phẩm và tạo thumbnail cho mỗi hình ảnh:

- Hình ảnh gốc: `data/images/<subcategory>/<product_id>/<image_number>.jpg`
- Thumbnail: `data/images/<subcategory>/<product_id>/thumb_<image_number>.jpg`
- Trang gallery HTML: `data/images/<subcategory>/<product_id>/index.html`

### Giới hạn số lượng hình ảnh

Số lượng hình ảnh tối đa cho mỗi sản phẩm được cấu hình trong `config_playwright.py`:

```python
MAX_IMAGES_PER_PRODUCT = 10
```

## Báo Cáo và Thống Kê

Sau khi hoàn thành, crawler sẽ tạo báo cáo tổng quan:

- File báo cáo: `data/products/crawl_summary_<timestamp>.txt`

Báo cáo chứa thông tin về:
- Tổng số sản phẩm đã crawl
- Tổng số danh mục
- Tổng số hình ảnh đã tải
- Thống kê theo danh mục
- Danh sách file đã tạo
- Danh sách sản phẩm có nhiều hình ảnh nhất

## Xử Lý Lỗi Phổ Biến

### Lỗi mã hóa UTF-8 với tiếng Việt

Crawler đã được tối ưu để xử lý tiếng Việt. Nếu gặp vấn đề về hiển thị tiếng Việt:
- Đảm bảo terminal hoặc trình soạn thảo văn bản hỗ trợ UTF-8
- Kiểm tra file CSV trong Excel bằng cách nhập khẩu với mã hóa UTF-8

### Lỗi captcha

Nếu crawler gặp captcha:
- Crawler sẽ tạm dừng và lưu ảnh chụp màn hình captcha trong thư mục `data/screenshots/`
- Chờ 30 giây để giải quyết captcha thủ công (nếu cần)

### Lỗi phụ thuộc thư viện

Nếu gặp lỗi về thư viện:
- Kiểm tra đã cài đầy đủ thư viện: `pip install -r requirements.txt`
- Kiểm tra phiên bản Python (yêu cầu Python 3.8+)
- Đảm bảo Playwright đã được cài đặt: `playwright install`

### Lỗi timeout

Nếu trang web mất quá nhiều thời gian để phản hồi:
- Tăng giá trị `REQUEST_TIMEOUT` trong file `config_playwright.py`
- Kiểm tra kết nối internet
- Thử giảm số lượng request đồng thời bằng cách giảm tham số `--subcategories`

## Liên Hệ Hỗ Trợ

Nếu gặp vấn đề không giải quyết được hoặc cần hỗ trợ thêm, vui lòng liên hệ:
- Email: [your-email@example.com]
- GitHub Issues: [repository-issues-url] 