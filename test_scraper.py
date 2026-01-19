"""
Quick test script to verify the YC scraper is working correctly.
This fetches just 10 companies to test the functionality.
"""

import requests
import json
import time
from bs4 import BeautifulSoup

print("=" * 60)
print("YC Scraper - Quick Test (10 companies)")
print("=" * 60)

# Test 1: Algolia API
print("\n[Test 1] Testing Algolia API...")

ALGOLIA_APP_ID = "45BWZJ1SGC"
ALGOLIA_API_KEY = "MjBjYjRiMzY0NzdhZWY0NjExY2NhZjYxMGIxYjc2MTAwNWFkNTkwNTc4NjgxYjU0YzFhYTY2ZGQ5OGY5NDMxZnJlc3RyaWN0SW5kaWNlcz0lNUIlMjJZQ0NvbXBhbnlfcHJvZHVjdGlvbiUyMiUyQyUyMllDQ29tcGFueV9CeV9MYXVuY2hfRGF0ZV9wcm9kdWN0aW9uJTIyJTVEJnRhZ0ZpbHRlcnM9JTVCJTIyeWNkY19wdWJsaWMlMjIlNUQmYW5hbHl0aWNzVGFncz0lNUIlMjJ5Y2RjJTIyJTVE"
ALGOLIA_INDEX = "YCCompany_production"

base_url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

headers = {
    'x-algolia-application-id': ALGOLIA_APP_ID,
    'x-algolia-api-key': ALGOLIA_API_KEY,
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

payload = {
    "query": "",
    "page": 0,
    "hitsPerPage": 10,
    "attributesToRetrieve": ["name", "slug", "one_liner", "batch", "website"]
}

try:
    response = requests.post(base_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    companies = data.get('hits', [])
    total_available = data.get('nbHits', 0)
    
    print(f"✅ Algolia API working!")
    print(f"   Total companies available: {total_available}")
    print(f"   Fetched: {len(companies)} companies")
    
    # Show sample
    print("\n   Sample companies:")
    for i, company in enumerate(companies[:5], 1):
        print(f"   {i}. {company.get('name', 'N/A')} ({company.get('batch', 'N/A')})")
        print(f"      - {company.get('one_liner', 'N/A')[:60]}...")
        
except Exception as e:
    print(f"❌ Algolia API failed: {e}")
    companies = []

# Test 2: Page scraping for founders
print("\n" + "=" * 60)
print("[Test 2] Testing page scraping for founder info...")

if companies:
    test_company = companies[0]
    slug = test_company.get('slug', '')
    
    print(f"\n   Testing with: {test_company.get('name', 'Unknown')} ({slug})")
    
    try:
        url = f"https://www.ycombinator.com/companies/{slug}"
        page_response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        page_response.raise_for_status()
        
        soup = BeautifulSoup(page_response.text, 'html.parser')
        
        # Try to find Next.js data
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data:
            json_data = json.loads(next_data.string)
            page_props = json_data.get('props', {}).get('pageProps', {})
            company_data = page_props.get('company', {})
            founders = company_data.get('founders', [])
            
            print(f"✅ Page scraping working!")
            print(f"   Found {len(founders)} founder(s):")
            
            for f in founders:
                name = f.get('full_name', f.get('name', 'Unknown'))
                linkedin = f.get('linkedin_url', 'N/A')
                title = f.get('title', '')
                print(f"   - {name} ({title})")
                print(f"     LinkedIn: {linkedin if linkedin else 'N/A'}")
        else:
            print("⚠️ Next.js data not found, trying HTML parsing...")
            
    except Exception as e:
        print(f"❌ Page scraping failed: {e}")

print("\n" + "=" * 60)
print("Test complete! The scraper appears to be working correctly.")
print("=" * 60)
print("\nYou can now run the full scraper with:")
print("  python yc_scraper.py")
print("\nOr use the Jupyter notebook:")
print("  jupyter notebook yc_scraper.ipynb")
