# Y Combinator Startup Directory Scraper

Scrape data for approximately **500 startups** listed on the [Y Combinator startup directory](https://www.ycombinator.com/companies).

## 🎯 Approach Summary

This scraper uses a two-phase approach for efficient and reliable data collection:

1. **API Discovery**: Identified that YC uses Algolia for their search functionality. By leveraging their public Algolia API, we can efficiently batch-fetch company listings without dealing with pagination/infinite scroll issues.

2. **Page Scraping**: For detailed founder information (names & LinkedIn URLs), we scrape individual company pages, parsing the embedded Next.js `__NEXT_DATA__` JSON which contains structured founder data.

3. **Concurrency & Rate Limiting**: Uses ThreadPoolExecutor for parallel requests (5 workers) with random delays between requests to be respectful to the server and avoid rate limiting.

## 📊 Data Extracted

| Field | Description |
|-------|-------------|
| Company Name | Official startup name |
| Batch | YC batch (e.g., "W21", "S22") |
| Short Description | One-liner description |
| Founder Name(s) | Comma-separated founder names |
| Founder LinkedIn URL(s) | Comma-separated LinkedIn profile URLs |

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/SamsudeenAshad/Scrape-data-for-startups.git
cd Scrape-data-for-startups

# Install dependencies
pip install -r requirements.txt
```

### Usage

**Option 1: Run the Python script**
```bash
python yc_scraper.py
```

**Option 2: Use the Jupyter Notebook**
```bash
jupyter notebook yc_scraper.ipynb
```

## 📁 Project Structure

```
├── yc_scraper.py          # Main Python script
├── yc_scraper.ipynb       # Interactive Jupyter notebook
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── output/
    ├── yc_startups_500.csv    # CSV output (generated)
    └── yc_startups_500.json   # JSON output (generated)
```

## 🔧 Technical Details

### Scraping Strategy

1. **Algolia API** (`YCAlgoliaClient`):
   - YC's frontend uses Algolia for search
   - Public API credentials extracted from their website
   - Fetches 100 companies per request efficiently

2. **Page Parser** (`YCPageScraper`):
   - Scrapes individual company pages for founder details
   - Parses Next.js `__NEXT_DATA__` script tag for structured JSON
   - Falls back to HTML parsing if JSON unavailable

3. **Performance Optimizations**:
   - ThreadPoolExecutor for concurrent requests (5 workers)
   - In-memory caching to avoid duplicate requests
   - Exponential backoff retry logic
   - Random delays (0.3-0.8s) between requests

### Code Quality

- Modular design with separate classes for each concern
- Type hints throughout for better code clarity
- Comprehensive docstrings and inline comments
- Error handling with retry logic
- Logging for debugging and monitoring

## ⚠️ Limitations & Notes

- LinkedIn URLs depend on founders having linked their profiles on YC
- Some older companies may have incomplete founder information
- Rate limiting is implemented to be respectful (expect ~10-15 min for 500 companies)
- YC's website structure may change, requiring scraper updates

## 📈 Sample Output

| Company Name | Batch | Short Description | Founder Name(s) | Founder LinkedIn URL(s) |
|-------------|-------|-------------------|-----------------|------------------------|
| Airbnb | W09 | Book accommodations around the world | Brian Chesky, Joe Gebbia, Nathan Blecharczyk | linkedin.com/in/brianchesky, ... |
| Stripe | S09 | Economic infrastructure for the internet | Patrick Collison, John Collison | linkedin.com/in/patrickcollison, ... |

## 📝 License

This project is for educational purposes. Please respect YC's terms of service when using this scraper.
