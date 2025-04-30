import re
import logging
import os
from urllib.parse import urlparse
import markdown
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def estimate_token_count(text):
    """
    Estimate the number of tokens in a text string.
    This is a rough approximation based on word count.
    
    Args:
        text (str): The text to estimate tokens for
        
    Returns:
        int: Estimated token count
    """
    # A simple estimation: ~1.33 tokens per word on average
    words = re.findall(r'\b\w+\b', text)
    return int(len(words) * 1.33)

def get_section_headers(markdown_text):
    """
    Extract section headers from markdown text to use as context.
    
    Args:
        markdown_text (str): The markdown text
        
    Returns:
        list: List of (header_level, header_text, position) tuples
    """
    headers = []
    # Match markdown headers (# Header, ## Header, etc.)
    header_pattern = re.compile(r'^(#{1,6})\s+(.*?)$', re.MULTILINE)
    
    for match in header_pattern.finditer(markdown_text):
        level = len(match.group(1))
        text = match.group(2).strip()
        position = match.start()
        headers.append((level, text, position))
    
    return headers

def get_document_title(markdown_text):
    """
    Extract document title from markdown text.
    
    Args:
        markdown_text (str): The markdown text
        
    Returns:
        str: Document title or default title
    """
    # Try to get the first h1 header
    headers = get_section_headers(markdown_text)
    if headers and headers[0][0] == 1:  # If first header is h1
        return headers[0][1]
    
    # Fallback: Try to find "# Scraped Content from" header
    title_match = re.search(r'# Scraped Content from (.*?)$', markdown_text, re.MULTILINE)
    if title_match:
        return f"Content from {title_match.group(1)}"
    
    return "Document"  # Default title

def get_current_section_context(position, headers):
    """
    Get the current section context for a given position.
    
    Args:
        position (int): Current position in text
        headers (list): List of (level, text, position) header tuples
        
    Returns:
        list: Current section headers from h1 to deepest level
    """
    current_headers = []
    current_levels = {}  # Keep track of current headers at each level
    
    for level, text, header_pos in headers:
        if header_pos > position:
            break
        
        # Update the current header for this level
        current_levels[level] = text
        
        # Remove any deeper level headers (when we enter a new section)
        deeper_levels = [l for l in current_levels.keys() if l > level]
        for l in deeper_levels:
            current_levels.pop(l, None)
    
    # Build the list of current headers from h1 to deepest level
    max_level = max(current_levels.keys()) if current_levels else 0
    for level in range(1, max_level + 1):
        if level in current_levels:
            current_headers.append(current_levels[level])
    
    return current_headers

def create_chunks_from_markdown(markdown_text, url=None, target_token_count=400, overlap_percentage=15):
    """
    Create semantic chunks from markdown text for AI embeddings.
    
    Args:
        markdown_text (str): The markdown text to chunk
        url (str, optional): The source URL
        target_token_count (int): Target tokens per chunk
        overlap_percentage (int): Percentage of overlap between chunks
        
    Returns:
        list: List of chunk dictionaries with text and metadata
    """
    logger.debug(f"Creating chunks with target_token_count={target_token_count}, overlap_percentage={overlap_percentage}")
    
    # Get document title and source info
    document_title = get_document_title(markdown_text)
    domain = urlparse(url).netloc if url else "Unknown source"
    
    logger.debug(f"Document title: {document_title}, domain: {domain}")
    
    # Extract headers for context
    headers = get_section_headers(markdown_text)
    
    # Convert markdown to HTML for better structural parsing
    html = markdown.markdown(markdown_text, extensions=['tables', 'nl2br'])
    soup = BeautifulSoup(html, 'html.parser')
    
    # Get all paragraph and list elements
    elements = soup.find_all(['p', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table'])
    logger.debug(f"Found {len(elements)} elements to chunk")
    
    chunks = []
    current_chunk = ""
    current_token_count = 0
    current_elements = []  # Store complete elements for the current chunk
    
    for element in elements:
        # Extract and clean text from the element
        if element.name in ['ul', 'ol']:
            # For lists, get all list items
            items = element.find_all('li')
            element_text = "\n".join([f"• {item.get_text().strip()}" for item in items])
        else:
            element_text = element.get_text().strip()
        
        if not element_text:
            continue
        
        element_token_count = estimate_token_count(element_text)
        logger.debug(f"Element: {element.name}, tokens: {element_token_count}, text: {element_text[:50]}...")
        
        # Check if this single element exceeds the target token count
        if element_token_count > target_token_count * 1.5:
            logger.debug(f"Large element found: {element_token_count} tokens, will split carefully")
            
            # For very large elements, we'll need to split them but still respect sentence boundaries
            # This is typically for very large paragraphs
            sentences = re.split(r'(?<=[.!?])\s+', element_text)
            sentence_groups = []
            current_group = []
            current_group_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = estimate_token_count(sentence)
                
                if current_group_tokens + sentence_tokens > target_token_count and current_group:
                    sentence_groups.append(" ".join(current_group))
                    current_group = [sentence]
                    current_group_tokens = sentence_tokens
                else:
                    current_group.append(sentence)
                    current_group_tokens += sentence_tokens
            
            # Add the last group if it's not empty
            if current_group:
                sentence_groups.append(" ".join(current_group))
            
            # Process each sentence group as if it were a separate element
            for group in sentence_groups:
                group_tokens = estimate_token_count(group)
                
                # If adding this group would exceed our target, create a new chunk
                if current_token_count > 0 and current_token_count + group_tokens > target_token_count:
                    # Create a new chunk with the current elements
                    chunk_text = ""
                    for el_text in current_elements:
                        if chunk_text and not chunk_text.endswith("\n"):
                            chunk_text += "\n\n"
                        chunk_text += el_text
                    
                    # Get context for this position
                    position = markdown_text.find(chunk_text[:50]) if chunk_text else 0
                    section_context = get_current_section_context(position, headers)
                    
                    # Create context section - everything on one line
                    context = f"Context: {document_title}."
                    if section_context:
                        context += f" Section: {' > '.join(section_context)}"
                    
                    # Create content section with an empty line between context and content
                    formatted_text = f"{context}\n\nContent: {chunk_text}"
                    
                    # Add chunk to our list
                    chunks.append({
                        "text": formatted_text,
                        "metadata": {
                            "document": document_title,
                            "source": domain,
                            "section": " > ".join(section_context) if section_context else None,
                        }
                    })
                    
                    # Calculate overlap (we'll use sentence overlap instead of word overlap)
                    # For now, just reset since we're respecting paragraph/element boundaries
                    current_chunk = ""
                    current_token_count = 0
                    current_elements = []
                
                # Add the group to the current chunk
                current_elements.append(group)
                current_token_count += group_tokens
        else:
            # For normal-sized elements, check if adding it would exceed the target
            if current_token_count > 0 and current_token_count + element_token_count > target_token_count:
                # Create a new chunk with the current elements
                chunk_text = ""
                for el_text in current_elements:
                    if chunk_text and not chunk_text.endswith("\n"):
                        chunk_text += "\n\n"
                    chunk_text += el_text
                
                # Get context for this position
                position = markdown_text.find(chunk_text[:50]) if chunk_text else 0
                section_context = get_current_section_context(position, headers)
                
                # Create context section - everything on one line
                context = f"Context: {document_title}."
                if section_context:
                    context += f" Section: {' > '.join(section_context)}"
                
                # Create content section with an empty line between context and content
                formatted_text = f"{context}\n\nContent: {chunk_text}"
                
                logger.debug(f"Created chunk with {current_token_count} tokens")
                
                # Add chunk to our list
                chunks.append({
                    "text": formatted_text,
                    "metadata": {
                        "document": document_title,
                        "source": domain,
                        "section": " > ".join(section_context) if section_context else None,
                    }
                })
                
                # Reset for new chunk (no overlap for now, to maintain element boundaries)
                current_chunk = ""
                current_token_count = 0
                current_elements = []
            
            # Add the element to the current chunk
            current_elements.append(element_text)
            current_token_count += element_token_count
    
    # Don't forget the last chunk
    if current_elements:
        chunk_text = ""
        for el_text in current_elements:
            if chunk_text and not chunk_text.endswith("\n"):
                chunk_text += "\n\n"
            chunk_text += el_text
        
        # Get context for this position
        position = markdown_text.find(chunk_text[:50]) if chunk_text else 0
        section_context = get_current_section_context(position, headers)
        
        # Create context section - everything on one line
        context = f"Context: {document_title}."
        if section_context:
            context += f" Section: {' > '.join(section_context)}"
        
        # Create content section with an empty line between context and content
        formatted_text = f"{context}\n\nContent: {chunk_text}"
        
        logger.debug(f"Created final chunk with {current_token_count} tokens")
        
        # Add chunk to our list
        chunks.append({
            "text": formatted_text,
            "metadata": {
                "document": document_title,
                "source": domain,
                "section": " > ".join(section_context) if section_context else None,
            }
        })
    
    return chunks

def export_chunks_to_files(chunks, base_filename, output_dir):
    """
    Export chunks to individual files.
    
    Args:
        chunks (list): List of chunk dictionaries
        base_filename (str): Base filename to use
        output_dir (str): Directory to save files in
        
    Returns:
        list: List of created filenames
    """
    os.makedirs(output_dir, exist_ok=True)
    created_files = []
    
    for i, chunk in enumerate(chunks):
        filename = f"{base_filename}_chunk_{i+1:03d}.txt"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(chunk["text"])
        
        created_files.append(filename)
    
    return created_files