// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add loading state to scrape buttons
    const scrapeBtns = document.querySelectorAll('#scrapeBtn, #scrapeBulkBtn');
    scrapeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Save original button text
            const originalText = this.innerHTML;
            
            // Disable button and show loading spinner
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Scraping...';
            
            // Add a timer to re-enable the button if the form doesn't submit for some reason
            setTimeout(() => {
                if (this.disabled) {
                    this.disabled = false;
                    this.innerHTML = originalText;
                }
            }, 10000); // 10 seconds timeout
            
            // Submit the form
            this.closest('form').submit();
        });
    });

    // Setup for URL input validation highlighting
    const urlInput = document.getElementById('url');
    if (urlInput) {
        urlInput.addEventListener('input', function() {
            const url = this.value.trim();
            const valid = /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/.test(url);
            
            if (url === '') {
                this.classList.remove('is-valid', 'is-invalid');
            } else if (valid) {
                this.classList.add('is-valid');
                this.classList.remove('is-invalid');
            } else {
                this.classList.add('is-invalid');
                this.classList.remove('is-valid');
            }
        });
    }

    // Setup for bulk URLs validation
    const urlsTextarea = document.getElementById('urls');
    if (urlsTextarea) {
        urlsTextarea.addEventListener('input', function() {
            const urls = this.value.trim().split('\n').filter(url => url.trim() !== '');
            
            if (urls.length === 0) {
                this.classList.remove('is-valid', 'is-invalid');
            } else if (urls.length > 0) {
                this.classList.add('is-valid');
                this.classList.remove('is-invalid');
            }
        });
    }
});

/**
 * Set up the delete confirmation modal
 * @param {string} filename - The filename to delete
 */
function confirmDelete(filename) {
    const deleteForm = document.getElementById('deleteForm');
    deleteForm.action = `/delete/${filename}`;
    
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    deleteModal.show();
}

/**
 * Format file size in human-readable format
 * @param {number} bytes - The size in bytes
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted size string
 */
function formatFileSize(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Update file list through AJAX
 */
function refreshFileList() {
    fetch('/files')
        .then(response => response.json())
        .then(files => {
            // Implementation for dynamic file list update
            // Not needed for initial version as page refresh happens on form submit
        })
        .catch(error => console.error('Error fetching files:', error));
}
