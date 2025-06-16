/**
 * Video Downloader Web Interface - Main JavaScript
 */

class VideoDownloader {
    constructor() {
        this.currentJobId = null;
        this.statusInterval = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.refreshJobHistory();
        this.checkDependencies();
    }

    setupEventListeners() {
        // Mode switching
        document.querySelectorAll('input[name="inputMode"]').forEach(radio => {
            radio.addEventListener('change', (e) => this.switchMode(e.target.value));
        });

        // JSON validation
        document.getElementById('validateJsonBtn')?.addEventListener('click', () => this.validateJson());

        // Download functionality
        document.getElementById('downloadBtn')?.addEventListener('click', () => this.startDownload());

        // Control buttons
        document.getElementById('cancelBtn')?.addEventListener('click', () => this.cancelDownload());
        document.getElementById('retryBtn')?.addEventListener('click', () => this.retryDownload());
        document.getElementById('newDownloadBtn')?.addEventListener('click', () => this.newDownload());
        document.getElementById('refreshHistoryBtn')?.addEventListener('click', () => this.refreshJobHistory());

        // Auto-format JSON on paste
        document.getElementById('jsonInput')?.addEventListener('paste', (e) => {
            setTimeout(() => this.formatJson(), 100);
        });

        // Real-time JSON validation
        document.getElementById('jsonInput')?.addEventListener('input', () => {
            this.debounce(() => this.validateJsonRealtime(), 500)();
        });
    }

    switchMode(mode) {
        document.querySelectorAll('.mode-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(mode + 'Mode')?.classList.add('active');
        this.clearValidation();
    }

    async validateJson() {
        const jsonInput = document.getElementById('jsonInput')?.value;
        const validationDiv = document.getElementById('jsonValidation');
        
        if (!validationDiv) return;

        if (!jsonInput?.trim()) {
            validationDiv.innerHTML = '<div class="alert alert-warning"><i class="bi bi-exclamation-triangle"></i> Please enter JSON to validate</div>';
            return;
        }

        try {
            const response = await fetch('/api/validate-json', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ json_string: jsonInput })
            });

            const data = await response.json();
            
            if (data.valid) {
                validationDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="bi bi-check-circle"></i> Valid JSON
                        <small class="d-block mt-1">URL: ${data.parsed.url}</small>
                    </div>
                `;
            } else {
                validationDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-x-circle"></i> ${data.error}
                    </div>
                `;
            }
        } catch (error) {
            validationDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Error validating JSON: ${error.message}
                </div>
            `;
        }
    }

    validateJsonRealtime() {
        const jsonInput = document.getElementById('jsonInput')?.value;
        const validationDiv = document.getElementById('jsonValidation');
        
        if (!validationDiv || !jsonInput?.trim()) {
            validationDiv.innerHTML = '';
            return;
        }

        try {
            JSON.parse(jsonInput);
            validationDiv.innerHTML = '<small class="text-success"><i class="bi bi-check-circle"></i> Valid JSON syntax</small>';
        } catch (error) {
            validationDiv.innerHTML = '<small class="text-danger"><i class="bi bi-x-circle"></i> Invalid JSON syntax</small>';
        }
    }

    formatJson() {
        const jsonInput = document.getElementById('jsonInput');
        if (!jsonInput) return;

        try {
            const parsed = JSON.parse(jsonInput.value);
            jsonInput.value = JSON.stringify(parsed, null, 2);
        } catch (error) {
            // Invalid JSON, don't format
        }
    }

    async startDownload() {
        const mode = document.querySelector('input[name="inputMode"]:checked')?.value;
        if (!mode) return;

        const requestData = this.buildRequestData(mode);
        if (!requestData) return;

        try {
            this.setDownloadButtonState(true, 'Starting...');
            
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            
            if (data.success) {
                this.currentJobId = data.job_id;
                this.showProgress();
                this.startStatusPolling();
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            this.showError(`Failed to start download: ${error.message}`);
        }
    }

    buildRequestData(mode) {
        const requestData = {
            mode: mode,
            quality: document.getElementById('quality')?.value || 'best',
            format: document.getElementById('format')?.value || 'mp4',
            filename: document.getElementById('filename')?.value?.trim() || '',
            verbose: document.getElementById('verbose')?.checked || false
        };

        if (mode === 'simple') {
            const url = document.getElementById('videoUrl')?.value?.trim();
            if (!url) {
                this.showError('Please enter a video URL');
                return null;
            }
            requestData.url = url;
        } else if (mode === 'json') {
            const jsonInput = document.getElementById('jsonInput')?.value?.trim();
            if (!jsonInput) {
                this.showError('Please enter JSON configuration');
                return null;
            }
            
            try {
                JSON.parse(jsonInput); // Validate JSON
                requestData.json_string = jsonInput;
            } catch (error) {
                this.showError('Invalid JSON format');
                return null;
            }
        }

        return requestData;
    }

    showProgress() {
        this.hideAllSections();
        document.getElementById('progressContainer').style.display = 'block';
        this.updateProgress({ progress: 0, message: 'Initializing...', status: 'pending' });
    }

    showDownloadComplete() {
        this.hideAllSections();
        document.getElementById('downloadSection').style.display = 'block';
        this.setDownloadButtonState(false);
        
        // Set up download file button
        const downloadBtn = document.getElementById('downloadFileBtn');
        if (downloadBtn) {
            downloadBtn.onclick = () => {
                window.open(`/api/download-file/${this.currentJobId}`, '_blank');
            };
        }
    }

    showError(message) {
        this.hideAllSections();
        const errorSection = document.getElementById('errorSection');
        const errorMessage = document.getElementById('errorMessage');
        
        if (errorSection && errorMessage) {
            errorSection.style.display = 'block';
            errorMessage.textContent = message;
        }
        
        this.setDownloadButtonState(false);
        this.stopStatusPolling();
    }

    hideAllSections() {
        ['progressContainer', 'downloadSection', 'errorSection'].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.style.display = 'none';
        });
    }

    startStatusPolling() {
        this.stopStatusPolling();
        
        this.statusInterval = setInterval(async () => {
            if (!this.currentJobId) return;
            
            try {
                const response = await fetch(`/api/status/${this.currentJobId}`);
                const data = await response.json();
                
                this.updateProgress(data);
                
                if (data.status === 'completed') {
                    this.stopStatusPolling();
                    this.showDownloadComplete();
                    this.refreshJobHistory();
                } else if (data.status === 'failed') {
                    this.stopStatusPolling();
                    this.showError(data.error || 'Download failed');
                    this.refreshJobHistory();
                }
            } catch (error) {
                console.error('Error polling status:', error);
            }
        }, 1000);
    }

    stopStatusPolling() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    }

    updateProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const statusMessage = document.getElementById('statusMessage');
        
        if (progressBar) {
            progressBar.style.width = `${data.progress}%`;
            progressBar.textContent = `${data.progress}%`;
            
            // Update progress bar color based on status
            progressBar.className = 'progress-bar';
            if (data.status === 'completed') {
                progressBar.classList.add('bg-success');
            } else if (data.status === 'failed') {
                progressBar.classList.add('bg-danger');
            } else {
                progressBar.classList.add('bg-primary');
            }
        }
        
        if (statusMessage) {
            statusMessage.textContent = data.message || 'Processing...';
        }
    }

    cancelDownload() {
        this.stopStatusPolling();
        this.hideAllSections();
        this.setDownloadButtonState(false);
        this.currentJobId = null;
    }

    retryDownload() {
        this.startDownload();
    }

    newDownload() {
        this.cancelDownload();
        this.clearForm();
        this.clearValidation();
    }

    clearForm() {
        ['videoUrl', 'jsonInput', 'filename'].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.value = '';
        });
        
        const verboseCheckbox = document.getElementById('verbose');
        if (verboseCheckbox) verboseCheckbox.checked = false;
    }

    clearValidation() {
        const validationDiv = document.getElementById('jsonValidation');
        if (validationDiv) validationDiv.innerHTML = '';
    }

    setDownloadButtonState(disabled, text = null) {
        const downloadBtn = document.getElementById('downloadBtn');
        if (!downloadBtn) return;
        
        downloadBtn.disabled = disabled;
        
        if (text) {
            const originalText = downloadBtn.dataset.originalText || downloadBtn.innerHTML;
            if (!downloadBtn.dataset.originalText) {
                downloadBtn.dataset.originalText = originalText;
            }
            downloadBtn.innerHTML = disabled ? 
                `<span class="loading"></span> ${text}` : 
                downloadBtn.dataset.originalText;
        } else if (downloadBtn.dataset.originalText) {
            downloadBtn.innerHTML = downloadBtn.dataset.originalText;
        }
    }

    async refreshJobHistory() {
        try {
            const response = await fetch('/api/jobs');
            const jobs = await response.json();
            
            const historyDiv = document.getElementById('jobHistory');
            if (!historyDiv) return;
            
            if (jobs.length === 0) {
                historyDiv.innerHTML = '<div class="text-muted text-center p-3">No recent downloads</div>';
                return;
            }
            
            historyDiv.innerHTML = '';
            jobs.slice(-10).reverse().forEach(job => {
                const jobDiv = this.createJobHistoryItem(job);
                historyDiv.appendChild(jobDiv);
            });
        } catch (error) {
            console.error('Error fetching job history:', error);
        }
    }

    createJobHistoryItem(job) {
        const jobDiv = document.createElement('div');
        jobDiv.className = `job-item ${job.status}`;
        
        const statusIcon = this.getStatusIcon(job.status);
        const timeAgo = this.getTimeAgo(new Date(job.created_at));
        
        jobDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1">
                    <div class="d-flex align-items-center mb-1">
                        <i class="bi bi-${statusIcon} me-2"></i>
                        <span class="fw-medium text-capitalize">${job.status}</span>
                    </div>
                    <small class="text-muted d-block">${timeAgo}</small>
                    <small class="text-truncate d-block" style="max-width: 200px;" title="${job.message}">
                        ${job.message}
                    </small>
                </div>
                <span class="badge bg-secondary ms-2">${job.job_id.substring(0, 8)}</span>
            </div>
        `;
        
        return jobDiv;
    }

    getStatusIcon(status) {
        const icons = {
            'completed': 'check-circle-fill text-success',
            'failed': 'x-circle-fill text-danger',
            'downloading': 'hourglass-split text-primary',
            'pending': 'clock text-warning'
        };
        return icons[status] || 'circle text-secondary';
    }

    getTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }

    async checkDependencies() {
        try {
            const response = await fetch('/api/check-deps');
            const deps = await response.json();
            
            // Update dependency status in UI if needed
            this.updateDependencyStatus(deps);
        } catch (error) {
            console.error('Error checking dependencies:', error);
        }
    }

    updateDependencyStatus(deps) {
        // This could be used to dynamically update dependency status
        // For now, the status is rendered server-side
    }

    // Utility function for debouncing
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new VideoDownloader();
});

// Export for potential external use
window.VideoDownloader = VideoDownloader;