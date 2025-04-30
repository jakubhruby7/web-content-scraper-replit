import os
import logging
import re
import time
import random
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import trafilatura
import nltk
import html2text
from nltk.tokenize import sent_tokenize
from file_manager import save_text_to_file

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Try to download NLTK data, but don't fail if it doesn't work
try:
    nltk.download('punkt', quiet=True)
except:
    logger.warning("NLTK punkt download failed. Sentence tokenization may not work properly.")

def clean_text(text):
    """
    Clean and format text content for AI embeddings.
    
    Args:
        text (str): The raw text content
        
    Returns:
        str: Cleaned and formatted text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Try to use NLTK to improve sentence structure
    try:
        sentences = sent_tokenize(text)
        text = '\n'.join(sentences)
    except:
        # Fall back to basic cleaning if NLTK fails
        text = text.replace('. ', '.\n')
    
    # Final cleanup
    text = text.strip()
    return text

def extract_with_trafilatura(url):
    """
    Extract text using Trafilatura library.
    
    Args:
        url (str): The URL to scrape
        
    Returns:
        tuple: (text_content, html_content) or (None, None) if failed
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            # Extract text
            text = trafilatura.extract(downloaded)
            # Also get the HTML for conversion to markdown
            html = trafilatura.extract(downloaded, output_format="html", include_links=True, 
                                      include_images=True, include_tables=True)
            return text, html
        return None, None
    except Exception as e:
        logger.error(f"Trafilatura extraction error for {url}: {str(e)}")
        return None, None

def extract_with_beautifulsoup(url):
    """
    Fallback method to extract text using BeautifulSoup if Trafilatura fails.
    
    Args:
        url (str): The URL to scrape
        
    Returns:
        tuple: (text_content, html_content) or (None, None) if failed
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Make a copy of the soup for HTML
        soup_html = BeautifulSoup(str(soup), 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "header", "footer", "nav"]):
            script.extract()
        
        # Also remove them from the HTML version
        for script in soup_html(["script", "style"]):
            script.extract()
        
        # Extract text
        text = soup.get_text(separator=' ')
        
        # Get the main content for HTML
        main_content = soup_html.find('body')
        if not main_content:
            main_content = soup_html
            
        html_content = str(main_content)
        
        return text, html_content
    except Exception as e:
        logger.error(f"BeautifulSoup extraction error for {url}: {str(e)}")
        return None, None

def scrape_url(url):
    """
    Scrape a URL and extract content as markdown to preserve structure.
    
    Args:
        url (str): The URL to scrape
        
    Returns:
        str: Markdown content or None if failed
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    logger.info(f"Scraping URL: {url}")
    
    # Try Trafilatura first (best for article content)
    text, html_content = extract_with_trafilatura(url)
    
    # Fall back to BeautifulSoup if Trafilatura fails
    if not text:
        logger.info(f"Trafilatura failed, trying BeautifulSoup for {url}")
        text, html_content = extract_with_beautifulsoup(url)
    
    if text and html_content:
        # Configure html2text
        h2t = html2text.HTML2Text()
        h2t.ignore_links = False
        h2t.ignore_images = False
        h2t.ignore_tables = False
        h2t.body_width = 0  # Don't wrap text
        h2t.unicode_snob = True  # Use Unicode instead of ASCII
        h2t.wrap_links = False
        
        try:
            # Convert HTML to markdown
            markdown_content = h2t.handle(html_content)
            
            # If markdown conversion fails, use the plain text
            if not markdown_content or len(markdown_content.strip()) < 10:
                markdown_content = clean_text(text)
                logger.warning(f"Markdown conversion failed for {url}, using plain text")
        except Exception as e:
            logger.error(f"Error converting to markdown: {str(e)}")
            markdown_content = clean_text(text)
        
        # Add metadata for context
        domain = urlparse(url).netloc
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        metadata = f"# Scraped Content from {domain}\n\n"
        metadata += f"**Source URL:** {url}  \n"
        metadata += f"**Date:** {timestamp}  \n\n"
        metadata += "---\n\n"
        
        return metadata + markdown_content
    
    return None

def scrape_multiple_urls(urls, data_dir):
    """
    Scrape multiple URLs and save the results.
    
    Args:
        urls (list): List of URLs to scrape
        data_dir (str): Directory to save files
        
    Returns:
        list: List of dictionaries containing results
    """
    results = []
    
    for url in urls:
        try:
            # Add a small delay to avoid hitting the server too hard
            time.sleep(random.uniform(1, 3))
            
            text_content = scrape_url(url)
            if text_content:
                filename = save_text_to_file(text_content, url, data_dir)
                results.append({
                    "url": url,
                    "status": "success",
                    "filename": filename
                })
            else:
                results.append({
                    "url": url,
                    "status": "error",
                    "message": "No content could be extracted"
                })
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {str(e)}")
            results.append({
                "url": url,
                "status": "error",
                "message": str(e)
            })
    
    return results
