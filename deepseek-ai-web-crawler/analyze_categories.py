#!/usr/bin/env python3
import os
import json
import argparse
import requests
from urllib.parse import urljoin
from typing import Dict, List, Any

from config_playwright import OUTPUT_DIR

def load_categories(file_path: str) -> List[Dict[str, Any]]:
    """Load categories from JSON file"""
    try:
        print(f"Đang đọc file {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Lỗi khi đọc file {file_path}: {e}")
        return []

def print_category_tree(categories: List[Dict[str, Any]]) -> None:
    """Hiển thị danh mục dưới dạng cây"""
    if not categories:
        print("Không có danh mục nào để hiển thị")
        return
    
    print(f"\nĐã tìm thấy {len(categories)} danh mục chính:")
    print("=" * 50)
    
    for i, category in enumerate(categories, 1):
        name = category['category_name']
        url = category['category_url']
        subcategories = category.get('subcategories', [])
        
        print(f"{i}. {name} - {url}")
        
        if subcategories:
            print(f"   Có {len(subcategories)} danh mục con:")
            for j, sub in enumerate(subcategories, 1):
                sub_name = sub['subcategory_name']
                sub_url = sub['subcategory_url']
                print(f"   {i}.{j} {sub_name} - {sub_url}")
        else:
            print("   Không có danh mục con")
        
        print("-" * 50)

def verify_urls(categories: List[Dict[str, Any]], max_urls_to_check: int = 5) -> List[Dict[str, Any]]:
    """Verify that subcategory URLs are accessible"""
    verified_count = 0
    invalid_urls = []
    
    print(f"Verifying up to {max_urls_to_check} URLs...")
    
    # Thêm User-Agent để tránh lỗi 403 Forbidden
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    for category in categories:
        for sub in category.get('subcategories', []):
            sub_url = sub.get('subcategory_url', '')
            if sub_url and verified_count < max_urls_to_check:
                try:
                    # Thêm headers vào request
                    response = requests.head(sub_url, timeout=5, headers=headers)
                    # Kiểm tra nếu server trả về 403, thử lại với GET
                    if response.status_code == 403:
                        response = requests.get(sub_url, timeout=5, headers=headers)
                    
                    status = response.status_code
                    valid = 200 <= status < 300
                    sub['url_valid'] = valid
                    verified_count += 1
                    
                    print(f"Checking: {sub_url} - {'✓' if valid else '✗'} ({status})")
                    
                    if not valid:
                        invalid_urls.append({
                            'category': category.get('category_name', ''),
                            'subcategory': sub.get('subcategory_name', ''),
                            'url': sub_url,
                            'status': status
                        })
                except Exception as e:
                    sub['url_valid'] = False
                    print(f"Error checking {sub_url}: {e}")
                    invalid_urls.append({
                        'category': category.get('category_name', ''),
                        'subcategory': sub.get('subcategory_name', ''),
                        'url': sub_url,
                        'error': str(e)
                    })
                    verified_count += 1
    
    if invalid_urls:
        print("\nInvalid URLs:")
        for url_info in invalid_urls:
            print(f"- {url_info['category']} > {url_info['subcategory']}: {url_info['url']}")
            if 'status' in url_info:
                print(f"  Status: {url_info['status']}")
            if 'error' in url_info:
                print(f"  Error: {url_info['error']}")
    else:
        print("\nAll checked URLs are valid!")
    
    return categories

def analyze_categories(file_path: str, check_urls: bool = False, max_urls_to_check: int = 5) -> None:
    """Phân tích danh mục và hiển thị thống kê"""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return
    
    try:
        categories = load_categories(file_path)
        
        # Count subcategories
        total_subcategories = sum(len(cat.get('subcategories', [])) for cat in categories)
        
        # Find category with most/least subcategories
        categories_with_counts = [(cat['category_name'], len(cat.get('subcategories', []))) 
                                 for cat in categories if cat.get('subcategories')]
        
        if categories_with_counts:
            max_category, max_count = max(categories_with_counts, key=lambda x: x[1])
            min_category, min_count = min(categories_with_counts, key=lambda x: x[1])
        else:
            max_category, max_count = "None", 0
            min_category, min_count = "None", 0
        
        # Print analysis
        print(f"Category Analysis for {file_path}:")
        print(f"Total main categories: {len(categories)}")
        print(f"Total subcategories: {total_subcategories}")
        print(f"Category with most subcategories: {max_category} ({max_count})")
        print(f"Category with least subcategories: {min_category} ({min_count})")
        print()
        
        print_category_tree(categories)
        
        if check_urls:
            verify_urls(categories, max_urls_to_check)
            
    except Exception as e:
        print(f"Error analyzing categories: {e}")

def export_markdown(categories: List[Dict[str, Any]], output_file: str) -> None:
    """Export categories to Markdown format"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Bach Hoa Xanh Categories\n\n")
        
        for category in categories:
            name = category.get('category_name', 'Unknown')
            url = category.get('category_url', '')
            subcategories = category.get('subcategories', [])
            
            f.write(f"## {name}\n")
            f.write(f"Main URL: {url}\n\n")
            
            if subcategories:
                f.write("### Subcategories\n\n")
                for sub in subcategories:
                    sub_name = sub.get('subcategory_name', 'Unknown')
                    sub_url = sub.get('subcategory_url', '')
                    f.write(f"- [{sub_name}]({sub_url})\n")
            
            f.write("\n")
    
    print(f"Exported categories to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Phân tích danh mục đã crawl")
    parser.add_argument("--input", "-i", default="data/categories_playwright.json",
                       help="Input JSON file path")
    parser.add_argument("--export", "-e", default="",
                       help="Export to markdown file")
    parser.add_argument("--check-urls", "-c", action="store_true",
                       help="Check if URLs are valid")
    parser.add_argument("--max-urls", "-m", type=int, default=5,
                       help="Maximum number of URLs to check")
    args = parser.parse_args()
    
    analyze_categories(args.input, args.check_urls, args.max_urls)
    
    if args.export:
        categories = load_categories(args.input)
        export_markdown(categories, args.export)

if __name__ == "__main__":
    main() 