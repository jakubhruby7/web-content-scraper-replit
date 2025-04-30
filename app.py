import os
import logging
import datetime
import markdown
from markupsafe import Markup
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from scraper import scrape_url, scrape_multiple_urls
from file_manager import (
    save_text_to_file, get_all_files, get_file_content, delete_file,
    save_chunks, get_all_chunks, get_chunk_content, get_chunks_for_file,
    CHUNKS_DIR
)
from chunker import create_chunks_from_markdown

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key-for-development")

# Make datetime available in templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Create data directory if it doesn't exist
DATA_DIR = "scraped_data"
os.makedirs(DATA_DIR, exist_ok=True)

@app.route("/")
def index():
    """Home page route"""
    files = get_all_files(DATA_DIR)
    return render_template("index.html", files=files)

@app.route("/scrape", methods=["POST"])
def scrape():
    """Endpoint to handle scraping requests"""
    url = request.form.get("url", "").strip()
    
    if not url:
        flash("Please enter a valid URL", "danger")
        return redirect(url_for("index"))
    
    try:
        text_content = scrape_url(url)
        if text_content:
            filename = save_text_to_file(text_content, url, DATA_DIR)
            flash(f"Successfully scraped and saved to {filename}", "success")
        else:
            flash("No content could be extracted from the URL", "warning")
    except Exception as e:
        logger.error(f"Error scraping URL {url}: {str(e)}")
        flash(f"Error scraping URL: {str(e)}", "danger")
    
    return redirect(url_for("index"))

@app.route("/scrape-bulk", methods=["POST"])
def scrape_bulk():
    """Endpoint to handle bulk scraping requests"""
    urls = request.form.get("urls", "").strip().split("\n")
    urls = [url.strip() for url in urls if url.strip()]
    
    if not urls:
        flash("Please enter at least one valid URL", "danger")
        return redirect(url_for("index"))
    
    results = scrape_multiple_urls(urls, DATA_DIR)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    
    if success_count > 0:
        flash(f"Successfully scraped {success_count} URLs", "success")
    if error_count > 0:
        flash(f"Failed to scrape {error_count} URLs", "warning")
    
    return redirect(url_for("index"))

@app.route("/files")
def files():
    """Get all scraped files"""
    files = get_all_files(DATA_DIR)
    return jsonify(files)

@app.route("/file/<filename>")
def view_file(filename):
    """View a specific file"""
    content = get_file_content(filename, DATA_DIR)
    
    # Extract source URL from markdown or plain text format
    if "**Source URL:**" in content:
        original_url = content.split("**Source URL:**", 1)[1].split("\n", 1)[0].strip()
    elif "\nSource URL: " in content:
        original_url = content.split("\nSource URL: ", 1)[1].split("\n", 1)[0]
    else:
        original_url = "Unknown"
    
    # Convert markdown to HTML if needed
    html_content = Markup(markdown.markdown(content, extensions=['tables', 'nl2br']))
    
    return render_template("view_file.html", filename=filename, 
                          content=content, 
                          html_content=html_content,
                          original_url=original_url)

@app.route("/download/<filename>")
def download_file(filename):
    """Download a specific file"""
    return send_from_directory(DATA_DIR, filename, as_attachment=True)

@app.route("/delete/<filename>", methods=["POST"])
def delete_file_route(filename):
    """Delete a specific file"""
    try:
        delete_file(filename, DATA_DIR)
        flash(f"File {filename} deleted successfully", "success")
    except Exception as e:
        flash(f"Error deleting file: {str(e)}", "danger")
    return redirect(url_for("index"))

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template("index.html", error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template("index.html", error="Server error. Please try again later."), 500

# Chunk management routes

@app.route("/create-chunks/<filename>", methods=["GET", "POST"])
def create_chunks_route(filename):
    """Create chunks from a file for AI embeddings"""
    logger.debug(f"Create chunks route for {filename}, method: {request.method}")
    
    if request.method == "GET":
        # Show the form to configure chunking options
        return render_template(
            "create_chunks.html", 
            filename=filename,
            default_token_count=400,
            default_overlap=15
        )
    
    # Handle POST request
    try:
        token_count = int(request.form.get("token_count", 400))
        overlap = int(request.form.get("overlap", 15))
        logger.debug(f"Creating chunks with token_count={token_count}, overlap={overlap}")
        
        # Get the file content
        content = get_file_content(filename, DATA_DIR)
        url = None
        
        # Try to extract the URL from the content
        if "**Source URL:**" in content:
            url = content.split("**Source URL:**", 1)[1].split("\n", 1)[0].strip()
        elif "\nSource URL: " in content:
            url = content.split("\nSource URL: ", 1)[1].split("\n", 1)[0]
        
        logger.debug(f"Extracted URL: {url}")
        
        # Create chunks from the content
        chunks = create_chunks_from_markdown(content, url, token_count, overlap)
        logger.debug(f"Created {len(chunks)} chunks")
        
        # Save the chunks
        result = save_chunks(chunks, filename)
        logger.debug(f"Save chunks result: {result}")
        
        if result["status"] == "success":
            flash(f"Successfully created {result['num_chunks']} chunks from {filename}", "success")
        else:
            flash(f"Error creating chunks: {result.get('message', 'Unknown error')}", "danger")
        
        # Log the chunk files that were created
        if "chunk_files" in result:
            for chunk_file in result["chunk_files"]:
                logger.debug(f"Created chunk file: {chunk_file}")
        
        # Get the base filename (without extension) for the chunks view
        base_filename = filename
        if base_filename.endswith('.txt'):
            base_filename = base_filename[:-4]
            
        logger.debug(f"Redirecting to view_chunks with filename={filename}, base_filename={base_filename}")
        return redirect(url_for("view_chunks", filename=filename))
        
    except Exception as e:
        logger.error(f"Error creating chunks for {filename}: {str(e)}")
        flash(f"Error creating chunks: {str(e)}", "danger")
        return redirect(url_for("view_file", filename=filename))

@app.route("/chunks")
def list_chunks():
    """List all chunk sets"""
    chunk_sets = get_all_chunks()
    return render_template("list_chunks.html", chunk_sets=chunk_sets)

@app.route("/chunks/<filename>")
def view_chunks(filename):
    """View chunks for a file"""
    logger.debug(f"Viewing chunks for file: {filename}")
    
    # Remove .txt extension if present
    base_filename = filename
    if base_filename.endswith('.txt'):
        base_filename = base_filename[:-4]
    
    logger.debug(f"Base filename: {base_filename}")
    
    # Get chunks for the file
    chunks_data = get_chunks_for_file(base_filename)
    logger.debug(f"Chunks data status: {chunks_data.get('status')}")
    
    if chunks_data["status"] == "error":
        error_msg = chunks_data.get("message", "Unknown error")
        logger.error(f"Error viewing chunks: {error_msg}")
        flash(f"Error viewing chunks: {error_msg}", "warning")
        return redirect(url_for("view_file", filename=filename))
    
    logger.debug(f"Found {chunks_data.get('num_chunks', 0)} chunks")
    
    return render_template(
        "view_chunks.html", 
        filename=filename,
        base_filename=base_filename,
        chunks_data=chunks_data
    )

@app.route("/chunk/<chunk_filename>")
def view_chunk(chunk_filename):
    """View a specific chunk"""
    content = get_chunk_content(chunk_filename)
    
    # Convert markdown to HTML
    html_content = Markup(markdown.markdown(content, extensions=['tables', 'nl2br']))
    
    return render_template(
        "view_chunk.html", 
        chunk_filename=chunk_filename,
        content=content,
        html_content=html_content
    )

@app.route("/download-chunk/<chunk_filename>")
def download_chunk(chunk_filename):
    """Download a specific chunk"""
    return send_from_directory(CHUNKS_DIR, chunk_filename, as_attachment=True)
