/**
 * Video Downloader Web Interface - Main JavaScript
 */

class VideoDownloader {
    constructor() {
        this.currentJobId = null;
        this.statusInterval = null;
        this.isDownloadInProgress = false;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.refreshJobHistory();
        this.checkDependencies();
        this.initTheme();
    }

    setupEventListeners() {

        // Download functionality
        document.getElementById('downloadBtn')?.addEventListener('click', () => this.startDownload());

        // Control buttons
        document.getElementById('cancelBtn')?.addEventListener('click', () => this.cancelDownload());
        document.getElementById('retryBtn')?.addEventListener('click', () => this.retryDownload());
        document.getElementById('newDownloadBtn')?.addEventListener('click', () => this.newDownload());
        document.getElementById('refreshHistoryBtn')?.addEventListener('click', () => this.refreshJobHistory());
        document.getElementById('clearHistoryBtn')?.addEventListener('click', () => this.clearJobHistory());

        // Auto-format JSON on paste
        document.getElementById('jsonInput')?.addEventListener('paste', (e) => {
            setTimeout(() => this.formatJson(), 100);
        });

        // Real-time JSON validation
        document.getElementById('jsonInput')?.addEventListener('input', () => {
            this.debounce(() => this.validateJsonRealtime(), 500)();
        });
        
        // Initial button state
        this.updateDownloadButtonState();
        
        // Theme toggle
        document.getElementById('themeToggle')?.addEventListener('change', (e) => this.toggleTheme(e.target.checked));
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
        
        if (!validationDiv) return;
        
        if (!jsonInput?.trim()) {
            validationDiv.innerHTML = '';
            this.updateDownloadButtonState(false);
            return;
        }

        try {
            const parsed = JSON.parse(jsonInput);
            const hasUrl = parsed && parsed.url && typeof parsed.url === 'string' && parsed.url.trim();
            
            if (hasUrl) {
                validationDiv.innerHTML = '<small class="text-success"><i class="bi bi-check-circle"></i> Valid JSON</small>';
                this.updateDownloadButtonState(true);
                // Detect available qualities
                this.detectAvailableQualities(parsed);
            } else {
                validationDiv.innerHTML = '<small class="text-warning"><i class="bi bi-exclamation-triangle"></i> Missing URL</small>';
                this.updateDownloadButtonState(false);
                this.resetQualityOptions();
            }
        } catch (error) {
            validationDiv.innerHTML = '<small class="text-danger"><i class="bi bi-x-circle"></i> Invalid JSON</small>';
            this.updateDownloadButtonState(false);
            this.resetQualityOptions();
        }
    }

    updateDownloadButtonState(isValid = false) {
        const downloadBtn = document.getElementById('downloadBtn');
        const downloadBtnHelp = document.getElementById('downloadBtnHelp');
        
        if (downloadBtn) {
            downloadBtn.disabled = !isValid;
            
            if (isValid) {
                downloadBtn.classList.remove('btn-secondary');
                downloadBtn.classList.add('btn-primary');
            } else {
                downloadBtn.classList.remove('btn-primary');
                downloadBtn.classList.add('btn-secondary');
            }
        }
        
        if (downloadBtnHelp) {
            if (isValid) {
                downloadBtnHelp.textContent = 'Ready to download';
                downloadBtnHelp.classList.remove('text-muted');
                downloadBtnHelp.classList.add('text-success');
            } else {
                downloadBtnHelp.textContent = 'Please enter valid JSON configuration to enable download';
                downloadBtnHelp.classList.remove('text-success');
                downloadBtnHelp.classList.add('text-muted');
            }
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
        // Prevent duplicate requests
        if (this.isDownloadInProgress) {
            console.log('Download already in progress, ignoring request');
            return;
        }
        
        // Additional check to prevent rapid clicking
        const downloadBtn = document.getElementById('downloadBtn');
        if (downloadBtn && downloadBtn.disabled) {
            console.log('Download button is disabled, ignoring request');
            return;
        }

        const requestData = this.buildRequestData();
        if (!requestData) return;

        try {
            this.isDownloadInProgress = true;
            this.setDownloadButtonState(true, 'Starting...');
            
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            
            if (data.success) {
                this.currentJobId = data.job_id;
                
                // Save initial job to localStorage with video title if available
                let videoTitle = 'Media Download';
                try {
                    const jsonData = JSON.parse(requestData.json_string);
                    if (jsonData.title) {
                        videoTitle = jsonData.title.replace(/\s*-\s*(YouTube|Vimeo|TikTok).*$/i, '').trim();
                    }
                } catch (e) {
                    // Use default title if JSON parsing fails
                }
                
                const initialJob = this.createSanitizedJob(
                    data.job_id, 
                    'pending', 
                    'Download started...', 
                    null, // No URL extraction from JSON for privacy
                    videoTitle
                );
                this.saveJobToHistory(initialJob);
                
                this.showProgress();
                this.startStatusPolling();
                this.refreshJobHistory();
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            this.showError(`Failed to start download: ${error.message}`);
        } finally {
            // Reset flag when request completes (success or failure)
            this.isDownloadInProgress = false;
        }
    }

    buildRequestData() {
        // Get JSON input
        const jsonInput = document.getElementById('jsonInput')?.value?.trim();
        if (!jsonInput) {
            this.showError('Please enter JSON configuration');
            return null;
        }
        
        try {
            JSON.parse(jsonInput); // Validate JSON
        } catch (error) {
            this.showError('Invalid JSON format');
            return null;
        }

        // Build request data with all the new options
        const requestData = {
            mode: 'json',
            json_string: jsonInput,
            quality: document.getElementById('quality')?.value || 'best',
            format: document.getElementById('format')?.value || 'mp4',
            filename: document.getElementById('filename')?.value?.trim() || '',
            verbose: document.getElementById('verbose')?.checked || false,
            
            // Advanced options (only include if they have values)
            videoQualityAdvanced: document.getElementById('videoQualityAdvanced')?.value || '',
            audioQuality: document.getElementById('audioQuality')?.value || 'best',
            audioFormat: document.getElementById('audioFormat')?.value || 'best',
            containerAdvanced: document.getElementById('containerAdvanced')?.value || '',
            rateLimit: document.getElementById('rateLimit')?.value || '',
            retries: document.getElementById('retries')?.value || '10',
            concurrentFragments: document.getElementById('concurrentFragments')?.value || '1',
            
            // Feature toggles
            extractAudio: document.getElementById('extractAudio')?.checked || false,
            embedSubs: document.getElementById('embedSubs')?.checked || false,
            embedThumbnail: document.getElementById('embedThumbnail')?.checked || false,
            embedMetadata: document.getElementById('embedMetadata')?.checked || false,
            keepFragments: document.getElementById('keepFragments')?.checked || false,
            writeSubs: document.getElementById('writeSubs')?.checked || false,
            
            // Subtitle options
            subtitleLangs: document.getElementById('subtitleLangs')?.value?.trim() || '',
            subtitleFormat: document.getElementById('subtitleFormat')?.value || 'best',
            autoSubs: document.getElementById('autoSubs')?.checked || false
        };

        return requestData;
    }

    showProgress() {
        this.hideAllSections();
        document.getElementById('progressContainer').style.display = 'block';
        this.updateProgress({ message: 'Initializing download...', status: 'pending' });
        this.updateStep('init', 'active');
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
                
                // Update job in localStorage with current status
                if (this.currentJobId) {
                    const updatedJob = this.createSanitizedJob(
                        this.currentJobId,
                        data.status,
                        data.message || 'Processing...',
                        null, // URL not needed for updates
                        null // Keep existing title
                    );
                    this.saveJobToHistory(updatedJob);
                }
                
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
        }, 2000);
    }

    stopStatusPolling() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    }

    updateProgress(data) {
        const statusMessage = document.getElementById('statusMessage');
        const statusDetails = document.getElementById('statusDetails');
        const loadingSpinner = document.getElementById('loadingSpinner');
        
        // Update status message
        if (statusMessage) {
            statusMessage.textContent = data.message || 'Processing...';
        }
        
        // Update status details and steps based on message content
        if (statusDetails) {
            let details = 'Please wait while we process your request';
            let currentStep = 'init';
            
            const message = (data.message || '').toLowerCase();
            
            if (message.includes('extract') || message.includes('information')) {
                details = 'Analyzing video and extracting metadata...';
                currentStep = 'extract';
            } else if (message.includes('download') || message.includes('fragment')) {
                details = 'Downloading video and audio streams...';
                currentStep = 'download';
            } else if (message.includes('process') || message.includes('merge') || message.includes('convert') || message.includes('ffmpeg') || message.includes('h264')) {
                details = 'Converting to H.264 and finalizing...';
                currentStep = 'process';
            } else if (message.includes('complet')) {
                details = 'Download completed successfully!';
                currentStep = 'completed';
            } else if (message.includes('fail') || message.includes('error')) {
                details = 'An error occurred during download';
                currentStep = 'failed';
            }
            
            statusDetails.textContent = details;
            this.updateStep(currentStep, data.status);
        }
        
        // Handle spinner visibility
        if (loadingSpinner) {
            if (data.status === 'completed' || data.status === 'failed') {
                loadingSpinner.style.display = 'none';
            } else {
                loadingSpinner.style.display = 'block';
            }
        }
        
        // Progress bar removed - using spinner only
    }

    updateStep(stepName, status) {
        // Reset all steps
        const steps = ['init', 'extract', 'download', 'process'];
        steps.forEach(step => {
            const element = document.getElementById(`step-${step}`);
            if (element) {
                element.classList.remove('active', 'completed');
                const icon = element.querySelector('i');
                if (icon) {
                    icon.className = 'bi bi-circle text-muted';
                }
            }
        });
        
        // Update steps based on current progress
        const stepOrder = ['init', 'extract', 'download', 'process'];
        const currentIndex = stepOrder.indexOf(stepName);
        
        stepOrder.forEach((step, index) => {
            const element = document.getElementById(`step-${step}`);
            const icon = element?.querySelector('i');
            
            if (index < currentIndex || (index === currentIndex && status === 'completed')) {
                // Completed steps
                element?.classList.add('completed');
                if (icon) icon.className = 'bi bi-check-circle-fill text-success';
            } else if (index === currentIndex && status !== 'completed') {
                // Current active step
                element?.classList.add('active');
                if (icon) icon.className = 'bi bi-circle-fill text-primary';
            }
        });
        
        // Handle special cases
        if (status === 'failed') {
            const currentElement = document.getElementById(`step-${stepName}`);
            const icon = currentElement?.querySelector('i');
            if (currentElement) {
                currentElement.classList.remove('active');
                currentElement.classList.add('failed');
            }
            if (icon) icon.className = 'bi bi-x-circle-fill text-danger';
        }
    }

    cancelDownload() {
        this.stopStatusPolling();
        this.hideAllSections();
        this.setDownloadButtonState(false);
        this.currentJobId = null;
        this.isDownloadInProgress = false;
    }

    retryDownload() {
        this.startDownload();
    }

    newDownload() {
        this.cancelDownload();
        this.clearForm();
        this.clearValidation();
        this.isDownloadInProgress = false;
    }

    clearForm() {
        // Clear text inputs
        ['jsonInput', 'filename', 'subtitleLangs'].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.value = '';
        });
        
        // Reset selects to default values
        ['quality', 'format', 'videoQualityAdvanced', 'audioQuality', 'audioFormat', 'containerAdvanced', 
         'rateLimit', 'retries', 'concurrentFragments', 'subtitleFormat'].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.selectedIndex = 0;
        });
        
        // Uncheck all checkboxes
        ['verbose', 'extractAudio', 'embedSubs', 'embedThumbnail', 'embedMetadata', 'keepFragments', 
         'writeSubs', 'autoSubs'].forEach(id => {
            const element = document.getElementById(id);
            if (element) element.checked = false;
        });
        
        // Collapse advanced options
        const advancedCollapse = document.getElementById('advancedOptions');
        if (advancedCollapse && advancedCollapse.classList.contains('show')) {
            const bsCollapse = new bootstrap.Collapse(advancedCollapse, {toggle: false});
            bsCollapse.hide();
        }
        
        // Reset download button state
        this.updateDownloadButtonState(false);
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
            // Get job history from localStorage (client-side only)
            const jobs = this.getLocalJobHistory();
            
            const historyDiv = document.getElementById('jobHistory');
            if (!historyDiv) return;
            
            if (jobs.length === 0) {
                historyDiv.innerHTML = '<div class="text-muted text-center p-3">No recent downloads</div>';
                return;
            }
            
            historyDiv.innerHTML = '';
            // Show last 10 jobs, most recent first
            jobs.slice(-10).reverse().forEach(job => {
                const jobDiv = this.createJobHistoryItem(job);
                historyDiv.appendChild(jobDiv);
            });
        } catch (error) {
            console.error('Error refreshing job history:', error);
        }
    }

    createJobHistoryItem(job) {
        const jobDiv = document.createElement('div');
        jobDiv.className = `job-item ${job.status}`;
        
        const statusIcon = this.getStatusIcon(job.status);
        const timeAgo = this.getTimeAgo(new Date(job.created_at));
        
        // Show video title for completed downloads, otherwise show status message
        const displayMessage = job.status === 'completed' && job.title && job.title !== 'Media Download' ? 
            job.title : 
            (job.url_domain ? `${job.url_domain} - ${job.message}` : job.message);
        
        // Check if file is still available for download (only for completed jobs)
        const showDownloadBtn = job.status === 'completed' && this.isFileStillAvailable(job.created_at);
        
        jobDiv.innerHTML = `
            <div class="position-relative">
                <div class="d-flex align-items-start">
                    <i class="bi bi-${statusIcon} me-2 mt-1"></i>
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center justify-content-between mb-1">
                            <span class="fw-medium text-capitalize">${job.status}</span>
                            <span class="badge bg-secondary">${job.job_id.substring(0, 8)}</span>
                        </div>
                        <small class="text-muted d-block">${timeAgo}</small>
                        <small class="d-block text-wrap" style="line-height: 1.3;">
                            ${displayMessage}
                        </small>
                    </div>
                </div>
                ${showDownloadBtn ? `
                    <button class="btn btn-sm btn-outline-primary download-file-btn position-absolute" 
                            data-job-id="${job.job_id}" 
                            title="Download file"
                            style="bottom: 0.5rem; right: 0.5rem;">
                        <i class="bi bi-download"></i>
                    </button>
                ` : ''}
            </div>
        `;
        
        // Add click handler for download button
        if (showDownloadBtn) {
            const downloadBtn = jobDiv.querySelector('.download-file-btn');
            if (downloadBtn) {
                downloadBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.downloadJobFile(job.job_id);
                });
            }
        }
        
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

    // LocalStorage job history management
    getLocalJobHistory() {
        try {
            const history = localStorage.getItem('videoDownloaderHistory');
            return history ? JSON.parse(history) : [];
        } catch (error) {
            console.error('Error reading job history from localStorage:', error);
            return [];
        }
    }

    saveJobToHistory(job) {
        try {
            const history = this.getLocalJobHistory();
            
            // Remove any existing job with the same ID
            const filteredHistory = history.filter(existingJob => existingJob.job_id !== job.job_id);
            
            // Add the new/updated job
            filteredHistory.push(job);
            
            // Keep only the last 50 jobs to prevent localStorage from growing too large
            const trimmedHistory = filteredHistory.slice(-50);
            
            localStorage.setItem('videoDownloaderHistory', JSON.stringify(trimmedHistory));
        } catch (error) {
            console.error('Error saving job to localStorage:', error);
        }
    }

    clearJobHistory() {
        if (confirm('Are you sure you want to clear your download history? This action cannot be undone.')) {
            try {
                localStorage.removeItem('videoDownloaderHistory');
                this.refreshJobHistory();
            } catch (error) {
                console.error('Error clearing job history:', error);
            }
        }
    }

    // Create a sanitized job object for local storage (no sensitive data)
    createSanitizedJob(jobId, status, message, url = null, title = null) {
        // If updating existing job, preserve the title
        if (!title) {
            const existingJob = this.getLocalJobHistory().find(job => job.job_id === jobId);
            title = existingJob?.title || 'Media Download';
        }
        
        return {
            job_id: jobId,
            status: status,
            message: this.sanitizeMessage(message),
            title: title || 'Media Download',
            created_at: new Date().toISOString(),
            url_domain: url ? this.extractDomain(url) : null
        };
    }

    // Remove sensitive information from messages
    sanitizeMessage(message) {
        if (!message) return 'Processing...';
        
        // Remove any potential sensitive data patterns
        return message
            .replace(/cookie[s]?[:\s]*[^;\s]+/gi, 'cookies: [HIDDEN]')
            .replace(/authorization[:\s]*[^\s]+/gi, 'authorization: [HIDDEN]')
            .replace(/token[:\s]*[^\s]+/gi, 'token: [HIDDEN]')
            .replace(/session[:\s]*[^\s]+/gi, 'session: [HIDDEN]')
            .replace(/password[:\s]*[^\s]+/gi, 'password: [HIDDEN]')
            .replace(/key[:\s]*[^\s]+/gi, 'key: [HIDDEN]');
    }

    // Extract domain from URL for display purposes
    extractDomain(url) {
        try {
            const urlObj = new URL(url);
            return urlObj.hostname;
        } catch (error) {
            return 'Unknown site';
        }
    }

    // Check if file is still available based on retention policy
    isFileStillAvailable(createdAt) {
        try {
            const createdTime = new Date(createdAt);
            const now = new Date();
            const hoursSinceCreated = (now - createdTime) / (1000 * 60 * 60);
            
            // Default retention is 2 hours in production, 1 hour in development
            // We'll be conservative and assume 1 hour retention
            const retentionHours = 1;
            
            return hoursSinceCreated < retentionHours;
        } catch (error) {
            console.error('Error checking file availability:', error);
            return false;
        }
    }

    // Download file from completed job
    async downloadJobFile(jobId) {
        try {
            // First check if the file is still available
            const response = await fetch(`/api/status/${jobId}`);
            if (!response.ok) {
                throw new Error('Job not found');
            }
            
            const jobStatus = await response.json();
            if (jobStatus.status !== 'completed' || !jobStatus.has_file) {
                throw new Error('File no longer available');
            }
            
            // Download the file
            window.open(`/api/download-file/${jobId}`, '_blank');
            
        } catch (error) {
            console.error('Download failed:', error);
            
            // Show user-friendly error message
            const errorMsg = error.message === 'File no longer available' 
                ? 'This file is no longer available on the server'
                : 'Failed to download file';
                
            // You could show a toast notification here
            alert(errorMsg);
        }
    }

    // Detect available video qualities
    async detectAvailableQualities(jsonData) {
        const qualitySelect = document.getElementById('quality');
        const advancedQualitySelect = document.getElementById('videoQualityAdvanced');
        
        if (!qualitySelect) return;
        
        try {
            // Show loading state
            const originalHTML = qualitySelect.innerHTML;
            qualitySelect.innerHTML = '<option value="best">Detecting qualities...</option>';
            qualitySelect.disabled = true;
            
            // Build request data for format detection
            const requestData = {
                mode: 'json',
                json_string: JSON.stringify(jsonData),
                quality: 'best',
                format: 'mp4',
                verbose: false
            };
            
            const response = await fetch('/api/get-formats', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            if (response.ok) {
                const result = await response.json();
                
                if (result.success && result.available_qualities.length > 0) {
                    // Update quality dropdown with available qualities
                    this.updateQualityOptions(result.available_qualities);
                } else {
                    // Fallback to default options
                    qualitySelect.innerHTML = originalHTML;
                    console.warn('No specific qualities detected, using defaults');
                }
            } else {
                // Fallback to default options
                qualitySelect.innerHTML = originalHTML;
                console.warn('Failed to detect qualities, using defaults');
            }
            
        } catch (error) {
            console.error('Error detecting qualities:', error);
            // Fallback to default options
            this.resetQualityOptions();
        } finally {
            qualitySelect.disabled = false;
        }
    }

    // Update quality options based on available qualities
    updateQualityOptions(availableQualities) {
        const qualitySelect = document.getElementById('quality');
        const advancedQualitySelect = document.getElementById('videoQualityAdvanced');
        
        if (!qualitySelect) return;
        
        // Quality mapping with descriptions
        const qualityMap = {
            '2160p': 'Best Available (4K)',
            '1440p': 'Best Available (2K)', 
            '1080p': 'Best Available (1080p)',
            '720p': 'Best Available (720p)',
            '480p': 'Best Available (480p)',
            '360p': 'Best Available (360p)'
        };
        
        // Build new options
        let newHTML = '';
        
        // Add specific quality options only
        availableQualities.forEach(quality => {
            const description = quality === '2160p' ? '4K (2160p)' :
                              quality === '1440p' ? '2K (1440p)' :
                              quality === '1080p' ? '1080p (Full HD)' :
                              quality === '720p' ? '720p (HD)' :
                              quality === '480p' ? '480p (SD)' :
                              quality === '360p' ? '360p (Low)' : quality;
            
            newHTML += `<option value="${quality}">${description}</option>`;
        });
        
        qualitySelect.innerHTML = newHTML;
        
        // Update advanced quality select if it exists
        if (advancedQualitySelect) {
            let advancedHTML = '<option value="">Use Simple Quality</option>';
            availableQualities.forEach(quality => {
                const description = quality === '2160p' ? '4K (2160p)' :
                                  quality === '1440p' ? '2K (1440p)' :
                                  quality === '1080p' ? '1080p (Full HD)' :
                                  quality === '720p' ? '720p (HD)' :
                                  quality === '480p' ? '480p (SD)' :
                                  quality === '360p' ? '360p (Low)' : quality;
                
                advancedHTML += `<option value="${quality}">${description}</option>`;
            });
            advancedHTML += '<option value="1080p60">1080p 60fps</option>';
            advancedHTML += '<option value="720p60">720p 60fps</option>';
            
            advancedQualitySelect.innerHTML = advancedHTML;
        }
    }

    // Reset quality options to defaults
    resetQualityOptions() {
        const qualitySelect = document.getElementById('quality');
        const advancedQualitySelect = document.getElementById('videoQualityAdvanced');
        
        if (qualitySelect) {
            qualitySelect.innerHTML = `
                <option value="1080p">1080p (Full HD)</option>
                <option value="720p">720p (HD)</option>
                <option value="480p">480p (SD)</option>
            `;
        }
        
        if (advancedQualitySelect) {
            advancedQualitySelect.innerHTML = `
                <option value="">Use Simple Quality</option>
                <option value="2160p">4K (2160p)</option>
                <option value="1440p">2K (1440p)</option>
                <option value="1080p60">1080p 60fps</option>
                <option value="720p60">720p 60fps</option>
                <option value="360p">360p (Low)</option>
            `;
        }
    }

    // Theme management
    initTheme() {
        // Check for saved theme preference or default to light
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme);
        
        // Update toggle state
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.checked = savedTheme === 'dark';
        }
    }
    
    toggleTheme(isDark) {
        const theme = isDark ? 'dark' : 'light';
        this.setTheme(theme);
        localStorage.setItem('theme', theme);
    }
    
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        
        // Update theme icon
        const themeIcon = document.getElementById('themeIcon');
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'bi bi-sun-fill';
            } else {
                themeIcon.className = 'bi bi-moon-fill';
            }
        }
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