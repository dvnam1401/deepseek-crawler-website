# Lịch Sử Thay Đổi

Tất cả các thay đổi đáng chú ý của dự án sẽ được ghi lại trong file này.

## [1.0.0] - 2025-04-03

### Thêm mới
- Thu thập danh mục và sản phẩm từ trang Bách Hoá Xanh
- Xử lý AJAX và cuộn trang để tải thêm sản phẩm
- Hỗ trợ tải và lưu trữ nhiều hình ảnh cho mỗi sản phẩm
- Tạo thumbnail cho mỗi hình ảnh được tải xuống
- Tạo trang gallery HTML cho mỗi sản phẩm
- Xuất dữ liệu với nhiều định dạng: JSON, CSV, Excel
- Báo cáo tổng quan sau khi hoàn thành crawl
- Xử lý phát hiện và giải quyết captcha

### Cải thiện
- Xử lý tốt tiếng Việt trong CSV và Excel
- Tối ưu hóa tốc độ crawl với cơ chế chờ thông minh
- Hỗ trợ nhiều tùy chọn command-line để điều chỉnh quá trình crawl

### Sửa lỗi
- Sửa lỗi hiển thị tiếng Việt trong file CSV và báo cáo
- Xử lý lỗi timeout khi tải trang
- Xử lý lỗi khi tải hình ảnh không khả dụng

## [0.2.0] - 2025-04-02

### Thêm mới
- Chuyển đổi từ Selenium sang Playwright để cải thiện hiệu suất
- Tạo cấu trúc tổ chức dữ liệu thông minh hơn
- Thêm tính năng lưu và phân tích khi gặp captcha

### Cải thiện
- Tối ưu hóa việc phát hiện thông tin sản phẩm
- Cải thiện tốc độ thu thập dữ liệu
- Hoàn thiện cơ chế trích xuất URL sản phẩm từ danh sách

## [0.1.0] - 2025-04-01

### Thêm mới
- Phiên bản crawler đầu tiên sử dụng Selenium
- Cấu trúc dự án cơ bản
- Thu thập danh mục và sản phẩm đơn giản
- Xuất dữ liệu dạng JSON 