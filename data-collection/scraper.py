import os
import time
import json
import hashlib
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import redis
from rq import Queue, Worker
from supabase import create_client, Client
from fake_useragent import UserAgent
from loguru import logger
import yaml
from prometheus_client import Counter, Histogram, start_http_server

# Metrics
PAGES_SCRAPED = Counter('pages_scraped_total', 'Total pages scraped', ['source', 'status'])
SCRAPING_DURATION = Histogram('scraping_duration_seconds', 'Time spent scraping pages')

@dataclass
class ScrapingConfig:
    name: str
    base_url: str
    selectors: Dict[str, str]
    max_pages: int
    delay: float
    use_selenium: bool = False
    enabled: bool = True

class WebScraper:
    def __init__(self):
        self.setup_logging()
        self.setup_supabase()
        self.setup_redis()
        self.setup_selenium()
        self.ua = UserAgent()
        
        # Start metrics server
        start_http_server(8001)
        
    def setup_logging(self):
        logger.add("/app/logs/scraper.log", rotation="100 MB", retention="30 days")
        
    def setup_supabase(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.supabase: Client = create_client(url, key)
        
    def setup_redis(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        password = os.getenv('REDIS_PASSWORD')
        
        self.redis_client = redis.from_url(
            redis_url,
            password=password,
            decode_responses=True
        )
        self.queue = Queue(connection=self.redis_client)
        
    def setup_selenium(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def load_config(self) -> List[ScrapingConfig]:
        """Load scraping configuration from file"""
        config_path = '/app/config/sources.yaml'
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found: {config_path}")
            return []
            
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            
        configs = []
        for source in config_data.get('sources', []):
            if source.get('enabled', True):
                configs.append(ScrapingConfig(**source))
                
        return configs
        
    def get_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        return hashlib.sha256(content.encode()).hexdigest()
        
    def scrape_with_requests(self, url: str, selectors: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Scrape content using requests and BeautifulSoup"""
        try:
            headers = {'User-Agent': self.ua.random}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_element = soup.select_one(selectors.get('title', 'title'))
            title = title_element.get_text().strip() if title_element else ''
            
            # Extract content
            content_elements = soup.select(selectors.get('content', 'p'))
            content = ' '.join([elem.get_text().strip() for elem in content_elements])
            
            return {
                'title': title,
                'content': content,
                'url': url
            }
            
        except Exception as e:
            logger.error(f"Error scraping {url} with requests: {e}")
            return None
            
    def scrape_with_selenium(self, url: str, selectors: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Scrape content using Selenium for dynamic pages"""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extract title
            try:
                title_element = self.driver.find_element(By.CSS_SELECTOR, selectors.get('title', 'title'))
                title = title_element.text.strip()
            except:
                title = ''
                
            # Extract content
            try:
                content_elements = self.driver.find_elements(By.CSS_SELECTOR, selectors.get('content', 'p'))
                content = ' '.join([elem.text.strip() for elem in content_elements])
            except:
                content = ''
                
            return {
                'title': title,
                'content': content,
                'url': url
            }
            
        except Exception as e:
            logger.error(f"Error scraping {url} with selenium: {e}")
            return None
            
    def discover_urls(self, config: ScrapingConfig) -> List[str]:
        """Discover URLs to scrape from the base URL"""
        urls = []
        
        try:
            headers = {'User-Agent': self.ua.random}
            response = requests.get(config.base_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all links
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link['href']
                full_url = urljoin(config.base_url, href)
                
                # Filter URLs based on domain
                if urlparse(full_url).netloc == urlparse(config.base_url).netloc:
                    urls.append(full_url)
                    
            # Remove duplicates and limit
            urls = list(set(urls))[:config.max_pages]
            
        except Exception as e:
            logger.error(f"Error discovering URLs for {config.name}: {e}")
            
        return urls
        
    def save_content(self, source: str, data: Dict[str, str]) -> bool:
        """Save scraped content to Supabase"""
        try:
            content_hash = self.get_content_hash(data['content'])
            
            # Check if content already exists
            existing = self.supabase.table('scraped_content').select('id').eq('content_hash', content_hash).execute()
            if existing.data:
                logger.info(f"Content already exists: {data['url']}")
                return False
                
            # Save new content
            result = self.supabase.table('scraped_content').insert({
                'source': source,
                'url': data['url'],
                'title': data['title'],
                'content': data['content'],
                'content_hash': content_hash,
                'scraped_at': datetime.utcnow().isoformat()
            }).execute()
            
            if result.data:
                logger.info(f"Saved content from {data['url']}")
                return True
            else:
                logger.error(f"Failed to save content: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving content: {e}")
            return False
            
    @SCRAPING_DURATION.time()
    def scrape_source(self, config: ScrapingConfig):
        """Scrape content from a specific source"""
        logger.info(f"Starting to scrape {config.name}")
        
        # Discover URLs
        urls = self.discover_urls(config)
        logger.info(f"Found {len(urls)} URLs for {config.name}")
        
        scraped_count = 0
        
        for url in urls:
            try:
                # Choose scraping method
                if config.use_selenium:
                    data = self.scrape_with_selenium(url, config.selectors)
                else:
                    data = self.scrape_with_requests(url, config.selectors)
                    
                if data and data['content'].strip():
                    if self.save_content(config.name, data):
                        scraped_count += 1
                        PAGES_SCRAPED.labels(source=config.name, status='success').inc()
                    else:
                        PAGES_SCRAPED.labels(source=config.name, status='duplicate').inc()
                else:
                    PAGES_SCRAPED.labels(source=config.name, status='empty').inc()
                    
                # Respect delay
                time.sleep(config.delay)
                
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                PAGES_SCRAPED.labels(source=config.name, status='error').inc()
                
        logger.info(f"Completed scraping {config.name}. Scraped {scraped_count} new pages")
        
        # Queue data processing job if we have new content
        if scraped_count > 0:
            self.queue.enqueue('data_processing.processor.process_source_data', config.name)
        
    def run(self):
        """Main scraping loop"""
        logger.info("Starting web scraper")
        
        configs = self.load_config()
        if not configs:
            logger.warning("No scraping configurations found")
            return
            
        for config in configs:
            try:
                self.scrape_source(config)
            except Exception as e:
                logger.error(f"Error scraping source {config.name}: {e}")
                
        logger.info("Web scraping completed")
        
    def run_worker(self):
        """Run as RQ worker"""
        logger.info("Starting scraper worker")
        worker = Worker([self.queue], connection=self.redis_client)
        worker.work()
        
    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

if __name__ == "__main__":
    scraper = WebScraper()
    
    # Check if running as worker or standalone
    if os.getenv('RUN_AS_WORKER', 'false').lower() == 'true':
        scraper.run_worker()
    else:
        scraper.run()
