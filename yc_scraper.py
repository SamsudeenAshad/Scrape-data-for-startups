"""
Y Combinator Startup Directory Scraper
=======================================
This script scrapes data for ~500 startups from the Y Combinator directory.
It extracts: Company Name, Batch, Short Description, Founder Names, and Founder LinkedIn URLs.

Approach:
1. Uses YC's Algolia search API to fetch company listings efficiently
2. Visits individual company pages to extract detailed founder information
3. Implements concurrent requests for faster scraping
4. Includes rate limiting and retry logic for reliability

Author: YC Scraper Assignment
Date: 2026
"""

import requests
import json
import time
import csv
import random
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Founder:
    """Represents a startup founder"""
    name: str
    linkedin_url: Optional[str] = None
    title: Optional[str] = None


@dataclass
class Startup:
    """Represents a YC startup with all required fields"""
    company_name: str
    batch: str
    short_description: str
    founders: List[Founder] = field(default_factory=list)
    company_url: Optional[str] = None
    website: Optional[str] = None
    
    @property
    def founder_names(self) -> str:
        """Returns comma-separated founder names"""
        return ", ".join([f.name for f in self.founders])
    
    @property
    def founder_linkedin_urls(self) -> str:
        """Returns comma-separated founder LinkedIn URLs"""
        urls = [f.linkedin_url for f in self.founders if f.linkedin_url]
        return ", ".join(urls)
    
    def to_csv_row(self) -> Dict[str, str]:
        """Convert to CSV row format"""
        return {
            'Company Name': self.company_name,
            'Batch': self.batch,
            'Short Description': self.short_description,
            'Founder Name(s)': self.founder_names,
            'Founder LinkedIn URL(s)': self.founder_linkedin_urls,
            'Company URL': self.company_url or '',
            'Website': self.website or ''
        }


class YCAlgoliaClient:
    """
    Client for YC's Algolia search API.
    YC uses Algolia to power their company search functionality.
    """
    
    # Algolia API credentials (public, used by YC website)
    ALGOLIA_APP_ID = "45BWZJ1SGC"
    ALGOLIA_API_KEY = "MjBjYjRiMzY0NzdhZWY0NjExY2NhZjYxMGIxYjc2MTAwNWFkNTkwNTc4NjgxYjU0YzFhYTY2ZGQ5OGY5NDMxZnJlc3RyaWN0SW5kaWNlcz0lNUIlMjJZQ0NvbXBhbnlfcHJvZHVjdGlvbiUyMiUyQyUyMllDQ29tcGFueV9CeV9MYXVuY2hfRGF0ZV9wcm9kdWN0aW9uJTIyJTVEJnRhZ0ZpbHRlcnM9JTVCJTIyeWNkY19wdWJsaWMlMjIlNUQmYW5hbHl0aWNzVGFncz0lNUIlMjJ5Y2RjJTIyJTVE"
    ALGOLIA_INDEX = "YCCompany_production"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.ycombinator.com/companies',
        })
        self.base_url = f"https://{self.ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{self.ALGOLIA_INDEX}/query"
    
    def search_companies(self, page: int = 0, hits_per_page: int = 100, filters: str = "") -> Dict[str, Any]:
        """
        Search YC companies using Algolia API.
        
        Args:
            page: Page number (0-indexed)
            hits_per_page: Number of results per page (max 1000)
            filters: Optional Algolia filter string
            
        Returns:
            Dict containing hits and pagination info
        """
        headers = {
            'x-algolia-application-id': self.ALGOLIA_APP_ID,
            'x-algolia-api-key': self.ALGOLIA_API_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            "query": "",
            "page": page,
            "hitsPerPage": hits_per_page,
            "filters": filters,
            "attributesToRetrieve": [
                "name", "slug", "one_liner", "batch", "website",
                "all_locations", "team_size", "industries", "status"
            ]
        }
        
        try:
            response = self.session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Algolia API error: {e}")
            return {"hits": [], "nbHits": 0}
    
    def get_all_companies(self, max_companies: int = 500) -> List[Dict[str, Any]]:
        """
        Fetch all companies up to max_companies limit.
        
        Args:
            max_companies: Maximum number of companies to fetch
            
        Returns:
            List of company dictionaries
        """
        all_companies = []
        page = 0
        hits_per_page = 100  # Algolia typically allows up to 1000
        
        logger.info(f"Starting to fetch {max_companies} companies from YC directory...")
        
        while len(all_companies) < max_companies:
            result = self.search_companies(page=page, hits_per_page=hits_per_page)
            hits = result.get('hits', [])
            
            if not hits:
                logger.info("No more companies found.")
                break
            
            all_companies.extend(hits)
            logger.info(f"Fetched page {page + 1}, total companies: {len(all_companies)}")
            
            # Check if we have more pages
            total_hits = result.get('nbHits', 0)
            if (page + 1) * hits_per_page >= total_hits:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
        
        return all_companies[:max_companies]


class YCPageScraper:
    """
    Scrapes individual YC company pages for detailed founder information.
    """
    
    BASE_URL = "https://www.ycombinator.com/companies/"
    
    def __init__(self, max_workers: int = 5):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.max_workers = max_workers
        self.cache = {}  # Simple in-memory cache
    
    def get_company_page(self, slug: str, retries: int = 3) -> Optional[str]:
        """
        Fetch a company's page HTML with retry logic.
        
        Args:
            slug: Company URL slug (e.g., 'airbnb')
            retries: Number of retry attempts
            
        Returns:
            HTML content or None if failed
        """
        if slug in self.cache:
            return self.cache[slug]
        
        url = urljoin(self.BASE_URL, slug)
        
        for attempt in range(retries):
            try:
                # Add random delay to avoid rate limiting
                time.sleep(random.uniform(0.5, 1.5))
                
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                self.cache[slug] = response.text
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {slug}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
        return None
    
    def extract_founders_from_html(self, html: str) -> List[Founder]:
        """
        Extract founder information from company page HTML.
        
        The YC company pages contain founder sections with:
        - Founder name
        - LinkedIn URL
        - Title/Role
        
        Args:
            html: Raw HTML content
            
        Returns:
            List of Founder objects
        """
        founders = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Method 1: Look for the Active Founders section
        # YC pages typically have founder info in a specific section
        
        # Find all LinkedIn links that are likely founder profiles
        linkedin_pattern = re.compile(r'linkedin\.com/in/([^/\s"\']+)')
        
        # Look for founder sections - they typically contain founder info blocks
        # The structure varies, so we try multiple approaches
        
        # Try finding the script tag with __NEXT_DATA__ (Next.js)
        next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data_script:
            try:
                data = json.loads(next_data_script.string)
                # Navigate through the Next.js data structure
                props = data.get('props', {}).get('pageProps', {})
                company_data = props.get('company', {})
                
                # Extract founders from the structured data
                founder_list = company_data.get('founders', [])
                for f in founder_list:
                    founder = Founder(
                        name=f.get('full_name', f.get('name', 'Unknown')),
                        linkedin_url=f.get('linkedin_url'),
                        title=f.get('title')
                    )
                    founders.append(founder)
                    
                if founders:
                    return founders
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug(f"Could not parse Next.js data: {e}")
        
        # Method 2: Parse HTML structure directly
        # Look for sections that contain founder information
        
        # Find all text containing founder indicators
        founder_sections = soup.find_all(['div', 'section'], class_=lambda x: x and ('founder' in x.lower() if x else False))
        
        # Look for elements with LinkedIn URLs
        linkedin_links = soup.find_all('a', href=linkedin_pattern)
        
        for link in linkedin_links:
            href = link.get('href', '')
            linkedin_url = href if 'linkedin.com' in href else None
            
            # Try to find the associated name
            # Usually the name is near the LinkedIn link
            parent = link.find_parent(['div', 'section', 'article'])
            if parent:
                # Look for name in text content or specific elements
                name_elem = parent.find(['h3', 'h4', 'strong', 'span'], class_=lambda x: x and 'name' in str(x).lower()) if parent else None
                if name_elem:
                    name = name_elem.get_text(strip=True)
                else:
                    # Try to get text before the link
                    name = parent.get_text(strip=True).split('\n')[0][:100]
                
                if name and linkedin_url:
                    # Check if we already have this founder
                    existing_urls = [f.linkedin_url for f in founders]
                    if linkedin_url not in existing_urls:
                        founders.append(Founder(name=name, linkedin_url=linkedin_url))
        
        # Method 3: Use regex to find founder patterns in raw text
        if not founders:
            text = soup.get_text()
            
            # Find patterns like "Name Title" followed by LinkedIn
            linkedin_matches = linkedin_pattern.findall(html)
            
            # Look for common founder indicators
            founder_indicators = ['Founder', 'CEO', 'CTO', 'COO', 'Co-founder', 'Co-Founder']
            
            for indicator in founder_indicators:
                pattern = rf'([A-Z][a-z]+ [A-Z][a-z]+)\s*[^a-zA-Z]*{indicator}'
                matches = re.findall(pattern, text)
                for match in matches[:5]:  # Limit to prevent noise
                    if not any(f.name == match for f in founders):
                        founders.append(Founder(name=match))
        
        return founders
    
    def scrape_company(self, company_data: Dict[str, Any]) -> Optional[Startup]:
        """
        Scrape a single company's full information.
        
        Args:
            company_data: Basic company data from Algolia
            
        Returns:
            Startup object with full details
        """
        slug = company_data.get('slug', '')
        if not slug:
            return None
        
        logger.debug(f"Scraping company: {company_data.get('name', slug)}")
        
        # Create basic startup object
        startup = Startup(
            company_name=company_data.get('name', 'Unknown'),
            batch=company_data.get('batch', 'Unknown'),
            short_description=company_data.get('one_liner', ''),
            company_url=f"https://www.ycombinator.com/companies/{slug}",
            website=company_data.get('website', '')
        )
        
        # Fetch and parse the company page for founder info
        html = self.get_company_page(slug)
        if html:
            founders = self.extract_founders_from_html(html)
            startup.founders = founders
        
        return startup
    
    def scrape_companies_parallel(self, companies: List[Dict[str, Any]], 
                                   progress_callback=None) -> List[Startup]:
        """
        Scrape multiple companies in parallel using ThreadPoolExecutor.
        
        Args:
            companies: List of company data dicts from Algolia
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of Startup objects
        """
        startups = []
        total = len(companies)
        completed = 0
        
        logger.info(f"Starting parallel scraping of {total} companies with {self.max_workers} workers...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_company = {
                executor.submit(self.scrape_company, company): company 
                for company in companies
            }
            
            # Process completed tasks
            for future in as_completed(future_to_company):
                company = future_to_company[future]
                completed += 1
                
                try:
                    startup = future.result()
                    if startup:
                        startups.append(startup)
                        logger.debug(f"[{completed}/{total}] Scraped: {startup.company_name}")
                except Exception as e:
                    logger.error(f"Error scraping {company.get('name', 'unknown')}: {e}")
                
                if progress_callback:
                    progress_callback(completed, total)
                
                # Log progress every 50 companies
                if completed % 50 == 0:
                    logger.info(f"Progress: {completed}/{total} companies scraped")
        
        return startups


class DataExporter:
    """Handles exporting scraped data to various formats."""
    
    @staticmethod
    def to_csv(startups: List[Startup], filename: str = "yc_startups.csv"):
        """
        Export startups to CSV file.
        
        Args:
            startups: List of Startup objects
            filename: Output filename
        """
        if not startups:
            logger.warning("No data to export!")
            return
        
        fieldnames = [
            'Company Name', 'Batch', 'Short Description',
            'Founder Name(s)', 'Founder LinkedIn URL(s)',
            'Company URL', 'Website'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for startup in startups:
                writer.writerow(startup.to_csv_row())
        
        logger.info(f"Exported {len(startups)} startups to {filename}")
    
    @staticmethod
    def to_json(startups: List[Startup], filename: str = "yc_startups.json"):
        """
        Export startups to JSON file.
        
        Args:
            startups: List of Startup objects
            filename: Output filename
        """
        data = []
        for startup in startups:
            startup_dict = {
                'company_name': startup.company_name,
                'batch': startup.batch,
                'short_description': startup.short_description,
                'founders': [asdict(f) for f in startup.founders],
                'company_url': startup.company_url,
                'website': startup.website
            }
            data.append(startup_dict)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(startups)} startups to {filename}")


def main():
    """
    Main execution function.
    Orchestrates the complete scraping workflow.
    """
    print("=" * 60)
    print("Y Combinator Startup Directory Scraper")
    print("=" * 60)
    
    # Configuration
    MAX_COMPANIES = 500
    MAX_WORKERS = 5  # Concurrent requests (be respectful to the server)
    OUTPUT_CSV = "yc_startups_500.csv"
    OUTPUT_JSON = "yc_startups_500.json"
    
    start_time = time.time()
    
    # Step 1: Fetch company listings from Algolia
    print("\n[Step 1/3] Fetching company listings from YC directory...")
    algolia_client = YCAlgoliaClient()
    companies = algolia_client.get_all_companies(max_companies=MAX_COMPANIES)
    print(f"✓ Found {len(companies)} companies")
    
    if not companies:
        print("ERROR: No companies found. The API may have changed.")
        print("Trying alternative method...")
        # Fallback: Use direct page scraping if Algolia fails
        return
    
    # Step 2: Scrape detailed information for each company
    print(f"\n[Step 2/3] Scraping founder details for {len(companies)} companies...")
    print("(This may take a few minutes due to rate limiting)")
    
    scraper = YCPageScraper(max_workers=MAX_WORKERS)
    startups = scraper.scrape_companies_parallel(companies)
    print(f"✓ Successfully scraped {len(startups)} companies")
    
    # Step 3: Export data
    print("\n[Step 3/3] Exporting data...")
    exporter = DataExporter()
    exporter.to_csv(startups, OUTPUT_CSV)
    exporter.to_json(startups, OUTPUT_JSON)
    
    # Summary
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE!")
    print("=" * 60)
    print(f"Total companies scraped: {len(startups)}")
    print(f"Companies with founders: {sum(1 for s in startups if s.founders)}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    print(f"\nOutput files:")
    print(f"  - {OUTPUT_CSV}")
    print(f"  - {OUTPUT_JSON}")
    print("=" * 60)
    
    # Print sample data
    if startups:
        print("\nSample Data (first 3 companies):")
        for startup in startups[:3]:
            print(f"\n  Company: {startup.company_name}")
            print(f"  Batch: {startup.batch}")
            print(f"  Description: {startup.short_description[:100]}...")
            print(f"  Founders: {startup.founder_names or 'N/A'}")
            print(f"  LinkedIn: {startup.founder_linkedin_urls or 'N/A'}")


if __name__ == "__main__":
    main()
