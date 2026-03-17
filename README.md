# Supermarket Price Scraper

Web application to scrape and analyze supermarket prices. Built with Python and Streamlit.

## Features

- **Price Scraper**: Automated scraping of product prices from supermarkets
- **Product Browser**: Search and filter products by name, brand, category
- **Price History**: Track price changes over time
- **Dashboard**: Statistical analysis of prices
- **Inflation Analysis**: Track price variations and inflation metrics
- **Execution Logs**: Monitor scraper performance

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the Streamlit app
streamlit run app.py
```

The application will open at `http://localhost:8501`

## Project Structure

```
.
├── app.py                 # Main Streamlit application
├── scraper/               # Scraping modules
│   ├── categorias.py      # Category fetching
│   ├── productos.py       # Product scraping
│   ├── main.py            # Main scraper execution
│   ├── logs.py            # Execution logging
│   └── analisis_inflacion.py  # Inflation analysis
├── assets/                # Static assets
├── output/                # Scraped data output
├── requirements.txt      # Python dependencies
└── .gitignore            # Git ignore rules
```

## Tech Stack

- **Streamlit**: Web UI framework
- **BeautifulSoup4**: HTML parsing
- **Pandas**: Data manipulation
- **Altair**: Data visualization
- **Requests**: HTTP requests

## License

MIT
