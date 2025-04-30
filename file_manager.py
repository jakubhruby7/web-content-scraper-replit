import os
import re
import logging
import time
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def sanitize_filename(url):
    """
    Create a safe filename from a URL.
    
    Args:
        url (str): The URL to convert to a filename
        
    Returns:
        str: A sanitized filename
    """
    # Extract domain
    domain = urlparse(url).netloc
    
    # Remove www. if present
    domain = re.sub(r'^www\.', '', domain)
    
    # Get path and remove trailing slash
    path = urlparse(url).path.rstrip('/')
    
    # Take only the last part of the path if it exists
    if path:
        path_part = path.split('/')[-1]
        # Sanitize the path part
        path_part = re.sub(r'[^\w\-\.]', '_', path_part)
        filename = f"{domain}_{path_part}"
    else:
        filename = domain
    
    # Add timestamp for uniqueness
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{filename}_{timestamp}.txt"
    
    # Ensure the filename is not too long
    if len(filename) > 100:
        filename = filename[-100:]
    
    return filename

def save_text_to_file(text, url, data_dir):
    """
    Save text content to a file.
    
    Args:
        text (str): The text content to save
        url (str): The source URL
        data_dir (str): The directory to save the file
        
    Returns:
        str: The filename of the saved file
    """
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    filename = sanitize_filename(url)
    file_path = os.path.join(data_dir, filename)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        logger.info(f"Saved file: {file_path}")
        return filename
    except Exception as e:
        logger.error(f"Error saving file {file_path}: {str(e)}")
        raise

def get_all_files(data_dir):
    """
    Get a list of all scraped files with their metadata.
    
    Args:
        data_dir (str): The directory containing the files
        
    Returns:
        list: List of dictionaries with file information
    """
    if not os.path.exists(data_dir):
        return []
    
    files = []
    for filename in os.listdir(data_dir):
        if filename.endswith('.txt'):
            file_path = os.path.join(data_dir, filename)
            try:
                # Get file stats
                stats = os.stat(file_path)
                size_kb = stats.st_size / 1024
                mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats.st_mtime))
                
                # Try to extract original URL from the file
                original_url = "Unknown"
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_lines = ''.join([f.readline() for _ in range(5)])
                    url_match = re.search(r'Source URL: (.*?)$', first_lines, re.MULTILINE)
                    if url_match:
                        original_url = url_match.group(1)
                
                files.append({
                    'filename': filename,
                    'size_kb': round(size_kb, 2),
                    'modified': mod_time,
                    'url': original_url
                })
            except Exception as e:
                logger.error(f"Error reading file info for {file_path}: {str(e)}")
    
    # Sort files by modification time (newest first)
    files.sort(key=lambda x: x['modified'], reverse=True)
    return files

def get_file_content(filename, data_dir):
    """
    Get the content of a specific file.
    
    Args:
        filename (str): The name of the file
        data_dir (str): The directory containing the file
        
    Returns:
        str: The content of the file
    """
    file_path = os.path.join(data_dir, filename)
    if not os.path.exists(file_path):
        return f"File {filename} not found."
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return f"Error reading file: {str(e)}"

def delete_file(filename, data_dir):
    """
    Delete a specific file.
    
    Args:
        filename (str): The name of the file
        data_dir (str): The directory containing the file
    """
    file_path = os.path.join(data_dir, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {filename} not found.")
    
    try:
        os.remove(file_path)
        logger.info(f"Deleted file: {file_path}")
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {str(e)}")
        raise
