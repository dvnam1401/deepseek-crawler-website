#!/usr/bin/env python3
import json
import time
import argparse
import concurrent.futures
import requests
from typing import Dict, List, Any, Tuple

def load_categories(file_path: str) -> List[Dict[str, Any]]:
    """Load categories from JSON file"""
    try:
        print(f"Đang đọc file {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Lỗi khi đọc file {file_path}: {e}")
        return []

def check_url(url_data: Tuple[str, str, str]) -> Dict[str, Any]:
    """Check if a URL is working"""
    url, category, subcategory = url_data
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }
    
    result = {
        'url': url,
        'category': category,
        'subcategory': subcategory,
        'valid': False,
        'status': None,
        'error': None
    }
    
    try:
        response = requests.head(url, timeout=5, headers=headers)
        # Nếu trả về 403, thử lại với GET
        if response.status_code == 403:
            response = requests.get(url, timeout=5, headers=headers)
        
        status = response.status_code
        valid = 200 <= status < 300
        
        result['valid'] = valid
        result['status'] = status
    except Exception as e:
        result['error'] = str(e)
    
    return result

def check_all_urls(file_path: str, max_workers: int = 4) -> None:
    """Check all URLs in the categories file"""
    categories = load_categories(file_path)
    if not categories:
        print("Không có danh mục để kiểm tra")
        return
    
    # Collect all URLs to check
    urls_to_check = []
    for category in categories:
        category_name = category.get('category_name', 'Unknown')
        for sub in category.get('subcategories', []):
            subcategory_name = sub.get('subcategory_name', 'Unknown')
            subcategory_url = sub.get('subcategory_url', '')
            if subcategory_url:
                urls_to_check.append((subcategory_url, category_name, subcategory_name))
    
    if not urls_to_check:
        print("Không có URL để kiểm tra")
        return
    
    print(f"Chuẩn bị kiểm tra {len(urls_to_check)} URL...")
    
    # Use ThreadPoolExecutor to check URLs in parallel
    valid_count = 0
    invalid_count = 0
    invalid_urls = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(check_url, url_data): url_data for url_data in urls_to_check}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_url), 1):
            url_data = future_to_url[future]
            url = url_data[0]
            
            try:
                result = future.result()
                if result['valid']:
                    valid_count += 1
                    print(f"[{i}/{len(urls_to_check)}] ✓ {url} - {result['status']}")
                else:
                    invalid_count += 1
                    print(f"[{i}/{len(urls_to_check)}] ✗ {url} - {result['status'] or result['error']}")
                    invalid_urls.append(result)
            except Exception as e:
                print(f"[{i}/{len(urls_to_check)}] ! Lỗi khi kiểm tra {url}: {e}")
                invalid_count += 1
                invalid_urls.append({
                    'url': url,
                    'category': url_data[1],
                    'subcategory': url_data[2],
                    'valid': False,
                    'error': str(e)
                })
            
            # Tránh quá tải server
            time.sleep(0.1)
    
    # Print summary
    print("\nKết quả kiểm tra:")
    print(f"Tổng URL: {len(urls_to_check)}")
    print(f"URL hợp lệ: {valid_count}")
    print(f"URL không hợp lệ: {invalid_count}")
    
    if invalid_urls:
        print("\nDanh sách URL không hợp lệ:")
        for url_info in invalid_urls:
            print(f"- {url_info['category']} > {url_info['subcategory']}: {url_info['url']}")
            if url_info.get('status'):
                print(f"  Status: {url_info['status']}")
            if url_info.get('error'):
                print(f"  Error: {url_info['error']}")
    
    # Save results to file
    output_file = "url_check_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total': len(urls_to_check),
            'valid': valid_count,
            'invalid': invalid_count,
            'invalid_urls': invalid_urls
        }, f, ensure_ascii=False, indent=4)
    
    print(f"\nKết quả đã được lưu vào {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Kiểm tra tất cả URL trong file categories")
    parser.add_argument("--input", "-i", default="data/categories_playwright.json",
                       help="Input JSON file path")
    parser.add_argument("--workers", "-w", type=int, default=4,
                       help="Số lượng thread đồng thời (mặc định: 4)")
    args = parser.parse_args()
    
    check_all_urls(args.input, args.workers)

if __name__ == "__main__":
    main() 