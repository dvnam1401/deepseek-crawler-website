from setuptools import setup, find_packages

setup(
    name="deepseek-crawler",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "beautifulsoup4>=4.12.3",
        "python-dotenv>=1.0.1",
        "python-slugify>=8.0.1",
        "requests==2.32.3",
        "selenium>=4.15.2",
        "undetected-chromedriver>=3.5.4",
        "pandas>=2.0.0,<2.1.0",
        "pydantic==2.9.2",
        "crawl4ai>=0.3.0",
        "asyncio>=3.4.3",
        "aiohttp>=3.9.1",
        "tqdm>=4.66.1",
    ],
    entry_points={
        "console_scripts": [
            "deepseek-crawler=deepseek_crawler.main:run_cli",
        ],
    },
    author="Deepseek Team",
    author_email="info@deepseek.com",
    description="Web crawler system for e-commerce websites",
    keywords="web crawler, scraper, e-commerce",
    python_requires=">=3.8",
) 