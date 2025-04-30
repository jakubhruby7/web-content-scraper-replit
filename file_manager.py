import os
import re
import logging
import time
import json
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create directories if they don't exist
CHUNKS_DIR = "scraped_chunks"
os.makedirs(CHUNKS_DIR, exist_ok=True)

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
        
        # Also delete associated chunks if they exist
        base_name = filename.rsplit('.', 1)[0]  # Remove extension
        chunk_pattern = f"{base_name}_chunk_*.txt"
        
        # Check for chunks in the chunks directory
        for chunk_file in os.listdir(CHUNKS_DIR):
            if chunk_file.startswith(base_name) and "_chunk_" in chunk_file:
                chunk_path = os.path.join(CHUNKS_DIR, chunk_file)
                try:
                    os.remove(chunk_path)
                    logger.info(f"Deleted associated chunk: {chunk_path}")
                except Exception as chunk_error:
                    logger.error(f"Error deleting chunk {chunk_path}: {str(chunk_error)}")
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {str(e)}")
        raise

def save_chunks(chunks, base_filename, metadata=None):
    """
    Save chunks to the chunks directory with metadata.
    
    Args:
        chunks (list): List of chunk dictionaries with text and metadata
        base_filename (str): Base filename (without extension)
        metadata (dict, optional): Additional metadata for the chunks
        
    Returns:
        dict: Information about the saved chunks
    """
    if not chunks:
        return {"status": "error", "message": "No chunks to save"}
    
    # Create chunks directory if it doesn't exist
    os.makedirs(CHUNKS_DIR, exist_ok=True)
    
    # Remove extension if present
    if "." in base_filename:
        base_filename = base_filename.rsplit('.', 1)[0]
    
    # Store metadata in a JSON file
    metadata_filename = f"{base_filename}_metadata.json"
    metadata_path = os.path.join(CHUNKS_DIR, metadata_filename)
    
    chunk_files = []
    total_tokens = 0
    
    # Save each chunk
    for i, chunk in enumerate(chunks):
        chunk_filename = f"{base_filename}_chunk_{i+1:03d}.txt"
        chunk_path = os.path.join(CHUNKS_DIR, chunk_filename)
        
        try:
            with open(chunk_path, 'w', encoding='utf-8') as f:
                f.write(chunk["text"])
            
            chunk_files.append(chunk_filename)
            estimated_tokens = len(chunk["text"].split()) * 1.33  # Simple token estimation
            total_tokens += estimated_tokens
            
            logger.info(f"Saved chunk: {chunk_path}")
        except Exception as e:
            logger.error(f"Error saving chunk {chunk_path}: {str(e)}")
    
    # Save metadata
    chunk_metadata = {
        "source_file": base_filename,
        "created": time.strftime('%Y-%m-%d %H:%M:%S'),
        "num_chunks": len(chunks),
        "estimated_total_tokens": int(total_tokens),
        "chunk_files": chunk_files,
        "custom_metadata": metadata or {}
    }
    
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(chunk_metadata, f, indent=2)
        logger.info(f"Saved chunk metadata: {metadata_path}")
    except Exception as e:
        logger.error(f"Error saving chunk metadata {metadata_path}: {str(e)}")
    
    return {
        "status": "success",
        "base_filename": base_filename,
        "num_chunks": len(chunks),
        "chunk_files": chunk_files,
        "estimated_total_tokens": int(total_tokens)
    }

def get_all_chunks():
    """
    Get all chunk sets with their metadata.
    
    Returns:
        list: List of chunk set information
    """
    if not os.path.exists(CHUNKS_DIR):
        return []
    
    chunk_sets = []
    metadata_files = [f for f in os.listdir(CHUNKS_DIR) if f.endswith('_metadata.json')]
    
    for metadata_file in metadata_files:
        try:
            with open(os.path.join(CHUNKS_DIR, metadata_file), 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Count actual chunk files that exist
            chunk_count = 0
            for chunk_file in metadata.get('chunk_files', []):
                if os.path.exists(os.path.join(CHUNKS_DIR, chunk_file)):
                    chunk_count += 1
            
            source_file = metadata.get('source_file', 'unknown')
            if not source_file.endswith('.txt'):
                source_file += '.txt'
            
            chunk_sets.append({
                'base_filename': metadata.get('source_file', 'unknown'),
                'source_file': source_file,
                'created': metadata.get('created', 'unknown'),
                'num_chunks': chunk_count,
                'estimated_tokens': metadata.get('estimated_total_tokens', 0),
                'metadata_file': metadata_file
            })
        except Exception as e:
            logger.error(f"Error reading chunk metadata {metadata_file}: {str(e)}")
    
    # Sort by creation time (newest first)
    chunk_sets.sort(key=lambda x: x['created'], reverse=True)
    return chunk_sets

def get_chunk_content(chunk_filename):
    """
    Get the content of a specific chunk file.
    
    Args:
        chunk_filename (str): The chunk filename
        
    Returns:
        str: The content of the chunk
    """
    chunk_path = os.path.join(CHUNKS_DIR, chunk_filename)
    if not os.path.exists(chunk_path):
        return f"Chunk file {chunk_filename} not found."
    
    try:
        with open(chunk_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading chunk {chunk_path}: {str(e)}")
        return f"Error reading chunk: {str(e)}"

def get_chunks_for_file(base_filename):
    """
    Get all chunks for a specific file.
    
    Args:
        base_filename (str): The base filename (without extension)
        
    Returns:
        dict: Information about the chunks
    """
    # Remove extension if present
    if "." in base_filename:
        base_filename = base_filename.rsplit('.', 1)[0]
    
    metadata_filename = f"{base_filename}_metadata.json"
    metadata_path = os.path.join(CHUNKS_DIR, metadata_filename)
    
    if not os.path.exists(metadata_path):
        return {"status": "error", "message": f"No chunks found for {base_filename}"}
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Get content of each chunk
        chunks = []
        for chunk_file in metadata.get('chunk_files', []):
            chunk_path = os.path.join(CHUNKS_DIR, chunk_file)
            if os.path.exists(chunk_path):
                with open(chunk_path, 'r', encoding='utf-8') as f:
                    chunks.append({
                        "filename": chunk_file,
                        "content": f.read()
                    })
        
        return {
            "status": "success",
            "base_filename": base_filename,
            "num_chunks": len(chunks),
            "created": metadata.get('created', 'unknown'),
            "estimated_tokens": metadata.get('estimated_total_tokens', 0),
            "chunks": chunks
        }
    except Exception as e:
        logger.error(f"Error getting chunks for {base_filename}: {str(e)}")
        return {"status": "error", "message": str(e)}
