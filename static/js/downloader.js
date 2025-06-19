document.addEventListener("DOMContentLoaded", function () {
  let currentJobId = null;
  let statusInterval = null;

  // --- DOM Element Selection ---
  const jsonInput = document.getElementById("jsonInput");
  const downloadBtn = document.getElementById("downloadBtn");
  const downloadBtnHelp = document.getElementById("downloadBtnHelp");
  const jsonValidation = document.getElementById("jsonValidation");
  const progressContainer = document.getElementById("progressContainer");
  const downloadSection = document.getElementById("downloadSection");
  const errorSection = document.getElementById("errorSection");
  const newDownloadBtn = document.getElementById("newDownloadBtn");
  const retryBtn = document.getElementById("retryBtn");
  const cancelBtn = document.getElementById("cancelBtn");
  const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
  const clearHistoryBtn = document.getElementById("clearHistoryBtn");
  const statusMessage = document.getElementById("statusMessage");
  const statusDetails = document.getElementById("statusDetails");
  const progressBar = document.getElementById("progressBar");
  
  // Immediately hide the error section
  if (errorSection) {
    // Make sure the error section doesn't have the show-error class
    errorSection.classList.remove("show-error");
  }

  // --- Event Listeners ---

  // JSON validation and download button enabling
  if (jsonInput) {
    jsonInput.addEventListener("input", () => {
      const jsonString = jsonInput.value.trim();
      if (jsonString) {
        try {
          // Parse JSON to validate it
          const parsedJson = JSON.parse(jsonString);
          
          // Additional validation to ensure it has the required structure
          if (typeof parsedJson === 'object' && parsedJson !== null) {
            // Check if it's an array (batch download)
            if (Array.isArray(parsedJson)) {
              if (parsedJson.length === 0) {
                throw new Error("JSON array cannot be empty");
              }
              
              // Check first item in array has url
              if (!parsedJson[0].url && !parsedJson[0].info?.url) {
                throw new Error("Missing URL in JSON array items");
              }
            } 
            // Check if it's a single object with url
            else if (!parsedJson.url && !parsedJson.info?.url) {
              throw new Error("Missing URL in JSON");
            }
            
            // If we got here, JSON is valid
            jsonValidation.innerHTML =
              '<i class="bi bi-check-circle text-success"></i>';
            downloadBtn.disabled = false;
            downloadBtnHelp.style.display = "none";
          } else {
            throw new Error("JSON must be an object or array");
          }
        } catch (e) {
          jsonValidation.innerHTML =
            '<i class="bi bi-x-circle text-danger"></i>';
          downloadBtn.disabled = true;
          downloadBtnHelp.style.display = "block";
          downloadBtnHelp.textContent = `Invalid JSON: ${e.message}`;
        }
      } else {
        jsonValidation.innerHTML = "";
        downloadBtn.disabled = true;
        downloadBtnHelp.style.display = "block";
        downloadBtnHelp.textContent = "Enter valid JSON to enable download";
      }
    });
  }

  // Main download functionality
  if (downloadBtn) {
    downloadBtn.addEventListener("click", function () {
      // Hide any existing error messages
      if (errorSection) {
        errorSection.classList.remove("show-error");
      }
      
      // Validate JSON one more time before sending
      const jsonString = document.getElementById("jsonInput").value.trim();
      let parsedJson;
      
      try {
        parsedJson = JSON.parse(jsonString);
        
        // Additional validation for cookies
        if (parsedJson.cookies && typeof parsedJson.cookies === 'string' && parsedJson.cookies.length > 10000) {
          console.warn("Very long cookies string detected, this might cause issues");
          // We'll still proceed but log a warning
        }
        
        // Ensure headers is an object
        if (parsedJson.headers && typeof parsedJson.headers !== 'object') {
          parsedJson.headers = {};
          console.warn("Headers was not an object, replacing with empty object");
        }
        
        // Check for URL
        if (!parsedJson.url) {
          showError("Missing URL in JSON: The JSON must contain a 'url' field");
          return;
        }
        
      } catch (e) {
        showError("Invalid JSON format: " + e.message);
        return;
      }
      
      // Show progress immediately to give feedback
      showProgress("Preparing download request...");
      
      // Sanitize the JSON to prevent common issues
      function sanitizeJson(json) {
        // Create a deep copy to avoid modifying the original
        const sanitized = JSON.parse(JSON.stringify(json));
        
        // Ensure headers is an object
        if (sanitized.headers && typeof sanitized.headers !== 'object') {
          sanitized.headers = {};
        }
        
        // Ensure cookies is a string
        if (sanitized.cookies && typeof sanitized.cookies !== 'string') {
          try {
            sanitized.cookies = String(sanitized.cookies);
          } catch (e) {
            sanitized.cookies = "";
          }
        }
        
        return sanitized;
      }
      
      // Sanitize the JSON and stringify it again
      const sanitizedJson = sanitizeJson(parsedJson);
      const sanitizedJsonString = JSON.stringify(sanitizedJson);
      
      // Build request data with all form options
      let requestData = {
        mode: "json",
        quality: document.getElementById("quality").value,
        format: document.getElementById("format").value,
        filename: document.getElementById("filename").value,
        verbose: document.getElementById("verbose").checked,
        json_string: sanitizedJsonString,
        // Advanced Options
        videoQualityAdvanced: document.getElementById("videoQualityAdvanced")
          .value,
        audioQuality: document.getElementById("audioQuality").value,
        audioFormat: document.getElementById("audioFormat").value,
        containerAdvanced: document.getElementById("containerAdvanced").value,
        subtitleLangs: document.getElementById("subtitleLangs").value,
        subtitleFormat: document.getElementById("subtitleFormat").value,
        autoSubs: document.getElementById("autoSubs").checked,
        extractAudio: document.getElementById("extractAudio").checked,
        embedSubs: document.getElementById("embedSubs").checked,
        embedThumbnail: document.getElementById("embedThumbnail").checked,
        embedMetadata: document.getElementById("embedMetadata").checked,
      };

      // Log request for debugging (without sensitive data)
      console.log("Sending download request with options:", {
        mode: requestData.mode,
        format: requestData.format,
        quality: requestData.quality,
        // Don't log the full JSON string as it may contain sensitive data
        json_type: Array.isArray(parsedJson) ? "array" : "object",
      });

      fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          if (data.success) {
            currentJobId = data.job_id;
            
            // Update progress message based on response
            if (data.is_multi) {
              showProgress(`Starting batch download of ${data.video_count} videos...`);
            } else {
              showProgress("Starting download...");
            }
            
            startStatusPolling();
          } else {
            showError(data.error || "Unknown error occurred.");
          }
        })
        .catch((error) => {
          showError("Failed to start download: " + error.message);
        });
    });
  }

  // Reset UI for new download
  if (newDownloadBtn) {
    newDownloadBtn.addEventListener("click", () => {
      downloadSection.style.display = "none";
      errorSection.classList.remove("show-error"); // Hide error section
      progressContainer.style.display = "none"; // Hide progress container
      jsonInput.value = "";
      downloadBtn.disabled = true; // Start with button disabled
      downloadBtnHelp.style.display = "block";
      jsonValidation.innerHTML = "";
      currentJobId = null;
    });
  }

  // Retry button
  if (retryBtn) {
    retryBtn.addEventListener("click", () => {
      errorSection.style.display = "none";
      downloadBtn.click();
    });
  }

  // Cancel button
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      if (currentJobId) {
        fetch(`/api/cancel/${currentJobId}`, { method: "POST" });
      }
      if (statusInterval) clearInterval(statusInterval);
      statusInterval = null;
      progressContainer.style.display = "none";
      showError("Download canceled by user.");
    });
  }

  // --- UI State Functions ---
  function showProgress(message = "Initializing...") {
    progressContainer.style.display = "block";
    downloadSection.style.display = "none";
    // Hide error section by removing the show-error class
    errorSection.classList.remove("show-error");
    downloadBtn.disabled = true;
    statusMessage.textContent = message;
    statusDetails.textContent = "Please wait while we process your request.";
    progressBar.style.width = "0%";
    progressBar.setAttribute("aria-valuenow", "0");
  }

  function showDownloadComplete() {
    if (statusInterval) clearInterval(statusInterval);
    statusInterval = null;

    progressContainer.style.display = "none";
    downloadSection.style.display = "block";
    // Hide error section by removing the show-error class
    errorSection.classList.remove("show-error");
    downloadBtn.disabled = false;

    document.getElementById("downloadFileBtn").onclick = () => {
      window.open(`/api/download-file/${currentJobId}`, "_blank");
    };
    
    // Add to history when download completes
    if (currentJobId) {
      try {
        const jsonString = document.getElementById("jsonInput").value.trim();
        const parsedJson = JSON.parse(jsonString);
        
        // Extract title from JSON data
        let title = 'Unknown Title';
        if (Array.isArray(parsedJson)) {
          // For batch downloads, use a generic title
          title = `Batch Download (${parsedJson.length} videos)`;
        } else {
          // For single videos, try to extract title from various possible fields
          title = parsedJson.title || 
                  parsedJson.name || 
                  parsedJson.videoTitle || 
                  parsedJson.info?.title ||
                  extractTitleFromUrl(parsedJson.url) ||
                  'Unknown Title';
        }
        
        const historyItem = {
          job_id: currentJobId,
          url: parsedJson.url || 'Unknown URL',
          title: title,
          quality: document.getElementById("quality").value,
          format: document.getElementById("format").value,
          completedAt: new Date().toISOString(),
          is_multi: Array.isArray(parsedJson),
          video_count: Array.isArray(parsedJson) ? parsedJson.length : 1
        };
        
        addToHistory(historyItem);
      } catch (error) {
        console.error('Error adding to history:', error);
      }
    }
  }

  function showError(message) {
    if (statusInterval) clearInterval(statusInterval);
    statusInterval = null;

    // Only show error if we have a message
    if (!message) {
      console.warn("showError called without an error message");
      return;
    }
    
    progressContainer.style.display = "none";
    downloadSection.style.display = "none";
    
    // Format the error message for better readability
    let formattedMessage = message;
    
    // Check for specific error types and provide more helpful messages
    if (message.includes("string indices must be integers")) {
      formattedMessage = "JSON format error: There may be an issue with the cookies or headers format. Try removing the cookies field temporarily to see if that resolves the issue.";
    } else if (message.includes("Missing URL")) {
      formattedMessage = "The JSON must contain a 'url' field with the video URL.";
    } else if (message.includes("Invalid JSON")) {
      formattedMessage = message + " Please check your JSON syntax.";
    }
    
    // Update error message and show error section
    document.getElementById("errorMessage").textContent = formattedMessage;
    // Add the show-error class to make it visible
    errorSection.classList.add("show-error");
    
    console.error("Download error:", message);
    downloadBtn.disabled = false;
  }

  // --- API Polling ---
  function startStatusPolling() {
    if (statusInterval) clearInterval(statusInterval);
    
    let failedAttempts = 0;
    const MAX_FAILED_ATTEMPTS = 3;

    statusInterval = setInterval(() => {
      if (!currentJobId) return;

      fetch(`/api/status/${currentJobId}`)
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
          }
          failedAttempts = 0; // Reset failed attempts on success
          return response.json();
        })
        .then((data) => {
          // Update UI elements with new data
          if (statusMessage)
            statusMessage.textContent = data.stage || "Processing...";
            
          if (statusDetails) {
            // Format details nicely
            let details = data.details || "";
            
            // If we have "Unknown of Unknown at Unknown", replace with better text
            if (details.includes("Unknown of Unknown at Unknown")) {
              details = "Downloading... Please wait";
            }
            
            // If we have "N/A of N/A at N/A", replace with better text
            if (details.includes("N/A of N/A at N/A")) {
              details = "Downloading... Please wait";
            }
            
            statusDetails.textContent = details;
          }
          
          if (progressBar) {
            // Calculate a better progress value
            let progressValue = data.progress || 0;
            
            // If progress is 0 but status is downloading, show at least 10%
            if (progressValue === 0 && data.status === "downloading") {
              progressValue = 10;
            }
            
            // For multi-video downloads, ensure progress reflects completed videos
            if (data.is_multi && data.total_videos > 0) {
              const completedRatio = (data.completed_videos || 0) / data.total_videos;
              progressValue = Math.max(progressValue, completedRatio * 100);
            }
            
            // Ensure progress is at least 5% to show activity
            const displayProgress = Math.max(5, progressValue);
            
            // Set progress bar width with CSS transition for animation
            progressBar.style.width = `${displayProgress}%`;
            
            progressBar.setAttribute("aria-valuenow", displayProgress);
          }

          // For multi-video downloads, show more detailed information
          if (data.is_multi) {
            const completed = data.completed_videos || 0;
            const total = data.total_videos || 1;
            statusDetails.textContent = `${completed} of ${total} videos completed. ${data.details || ''}`;
          }

          // Check job status to stop polling if necessary
          if (data.status === "completed") {
            showDownloadComplete();
          } else if (data.status === "completed_with_errors") {
            // Handle partial success for multi-downloads
            showDownloadComplete();
            statusMessage.textContent = "Download Completed with Some Errors";
          } else if (data.status === "failed") {
            showError(data.error || "An unknown error occurred.");
          }
        })
        .catch((error) => {
          console.error("Polling error:", error);
          failedAttempts++;
          
          if (failedAttempts >= MAX_FAILED_ATTEMPTS) {
            clearInterval(statusInterval);
            statusInterval = null;
            showError("Connection to server lost after multiple attempts.");
          } else {
            // Don't show error for temporary connection issues
            console.warn(`Connection issue (attempt ${failedAttempts}/${MAX_FAILED_ATTEMPTS})`);
          }
        });
    }, 1500); // Poll every 1.5 seconds
  }

  // --- Job History (Client-side localStorage) ---
  
  function extractTitleFromUrl(url) {
    try {
      if (!url) return null;
      
      // Extract video ID from YouTube URLs and create a basic title
      if (url.includes('youtube.com/watch?v=') || url.includes('youtu.be/')) {
        const videoId = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)/);
        if (videoId) {
          return `YouTube Video (${videoId[1]})`;
        }
      }
      
      // For other URLs, try to extract a meaningful name from the path
      const urlObj = new URL(url);
      const pathname = urlObj.pathname;
      const filename = pathname.split('/').pop();
      
      if (filename && filename.includes('.')) {
        // Remove file extension and decode
        const nameWithoutExt = filename.replace(/\.[^/.]+$/, '');
        return decodeURIComponent(nameWithoutExt).replace(/[_-]/g, ' ');
      }
      
      return null;
    } catch (error) {
      return null;
    }
  }
  
  function addToHistory(jobData) {
    try {
      let history = JSON.parse(localStorage.getItem('downloadHistory') || '[]');
      
      // Add timestamp if not present
      if (!jobData.completedAt) {
        jobData.completedAt = new Date().toISOString();
      }
      
      // Add to beginning of array (most recent first)
      history.unshift(jobData);
      
      // Keep only last 50 items to avoid localStorage bloat
      if (history.length > 50) {
        history = history.slice(0, 50);
      }
      
      localStorage.setItem('downloadHistory', JSON.stringify(history));
      loadJobHistory(); // Refresh the display
    } catch (error) {
      console.error('Error adding to history:', error);
    }
  }
  
  function loadJobHistory() {
    const historyContainer = document.getElementById('jobHistory');
    if (!historyContainer) return;
    
    try {
      const history = JSON.parse(localStorage.getItem('downloadHistory') || '[]');
      
      if (history.length === 0) {
        historyContainer.innerHTML = '<p class="text-center mt-3 subtitle-text">No recent downloads</p>';
        return;
      }
      
      let historyHtml = '<div class="history-list">';
      
      history.forEach((item, index) => {
        const completedDate = new Date(item.completedAt).toLocaleString();
        const url = item.url || 'Unknown URL';
        const shortUrl = url.length > 40 ? url.substring(0, 40) + '...' : url;
        const quality = item.quality || 'best';
        const format = item.format || 'mp4';
        const isMulti = item.is_multi || false;
        const videoCount = item.video_count || 1;
        
        // Extract and display title
        const title = item.title || 'Unknown Title';
        const displayTitle = isMulti ? `📁 Batch (${videoCount} videos)` : `🎥 ${title}`;
        
        // Check if file is still available (within 1 hour retention period)
        const completedTime = new Date(item.completedAt);
        const currentTime = new Date();
        const hoursSinceCompletion = (currentTime - completedTime) / (1000 * 60 * 60);
        const fileStillAvailable = hoursSinceCompletion < 1; // FILE_RETENTION_HOURS = 1
        
        // Create download button or expired notice
        let downloadSection = '';
        if (fileStillAvailable) {
          downloadSection = `
            <div class="ms-2 flex-shrink-0">
              <button class="btn btn-sm btn-outline-primary" onclick="downloadFromHistory('${item.job_id}')">
                <i class="bi bi-download"></i>
              </button>
            </div>
          `;
        } else {
          downloadSection = `
            <div class="ms-2 flex-shrink-0">
              <span class="badge bg-secondary text-muted small">Expired</span>
            </div>
          `;
        }
        
        historyHtml += `
          <div class="history-item mb-2 p-2 border rounded">
            <div class="d-flex justify-content-between align-items-start">
              <div class="flex-grow-1 pe-2">
                <div class="fw-semibold history-title" title="${title}">
                  ${displayTitle}
                </div>
                <div class="text-muted small text-truncate" title="${url}">
                  ${shortUrl}
                </div>
                <div class="text-muted small">
                  ${quality} • ${format} • ${completedDate}
                </div>
              </div>
              ${downloadSection}
            </div>
          </div>
        `;
      });
      
      historyHtml += '</div>';
      historyContainer.innerHTML = historyHtml;
      
    } catch (error) {
      console.error('Error loading history:', error);
      historyContainer.innerHTML = '<p class="text-center mt-3 text-danger">Error loading history</p>';
    }
  }
  
  function clearJobHistory() {
    if (confirm('Are you sure you want to clear all download history? This cannot be undone.')) {
      try {
        localStorage.removeItem('downloadHistory');
        loadJobHistory();
        console.log('Download history cleared');
      } catch (error) {
        console.error('Error clearing history:', error);
      }
    }
  }
  
  // Make downloadFromHistory available globally
  window.downloadFromHistory = function(jobId) {
    if (jobId) {
      window.open(`/api/download-file/${jobId}`, '_blank');
    } else {
      console.error('No job ID provided for download');
    }
  };

  if (refreshHistoryBtn) {
    refreshHistoryBtn.addEventListener("click", loadJobHistory);
  }

  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", clearJobHistory);
  }

  // Initial load actions
  loadJobHistory();
  
  // Ensure error section is hidden on page load
  if (errorSection) {
    errorSection.classList.remove("show-error");
  }
});
