const uploadForm = document.getElementById('uploadForm');
const videoFileInput = document.getElementById('videoFile');
const maxDurationInput = document.getElementById('maxDuration');
const qualityInput = document.getElementById('quality');
const compressionInput = document.getElementById('compression');
const loadingState = document.getElementById('loadingState');
const resultsSection = document.getElementById('resultsSection');
const errorSection = document.getElementById('errorSection');
const errorMessage = document.getElementById('errorMessage');
const clipsList = document.getElementById('clipsList');
const downloadZipBtn = document.getElementById('downloadZipBtn');
const resetBtn = document.getElementById('resetBtn');
const dismissErrorBtn = document.getElementById('dismissErrorBtn');
const fileLabel = document.querySelector('.file-label');
const fileInputWrapper = document.querySelector('.file-input-wrapper');

let currentJobId = null;

/**
 * Handles file input trigger when file label is clicked or focused.
 * Supports both mouse click and keyboard (Enter/Space) activation.
 */
fileLabel.addEventListener('click', () => {
  videoFileInput.click();
});

// Enable keyboard navigation for the file label button
fileLabel.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    videoFileInput.click();
  }
});

videoFileInput.addEventListener('change', (e) => {
  const fileName = e.target.files[0]?.name || 'Choose a video...';
  fileLabel.textContent = fileName;
  fileInputWrapper.classList.toggle('active', e.target.files.length > 0);
});

uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  if (!videoFileInput.files.length) {
    showError('Please select a video file');
    return;
  }

  const formData = new FormData();
  formData.append('video', videoFileInput.files[0]);
  formData.append('maxDuration', maxDurationInput.value);
  formData.append('quality', qualityInput.value);
  formData.append('compression', compressionInput.value);

  uploadForm.style.display = 'none';
  loadingState.style.display = 'block';
  resultsSection.style.display = 'none';
  errorSection.style.display = 'none';

  try {
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || 'Upload failed');
    }

    const data = await response.json();
    currentJobId = data.jobId;

    displayResults(data);
  } catch (error) {
    showError(error.message);
    uploadForm.style.display = 'block';
    loadingState.style.display = 'none';
  }
});

/**
 * Displays video processing results with dynamically created clip items.
 * Each clip item includes accessibility attributes for screen readers.
 *
 * @param {Object} data - Result data from the API
 * @param {string[]} data.clips - Array of clip filenames
 * @param {number} data.totalDuration - Total video duration in seconds
 * @param {number} data.chunkCount - Number of clips created
 */
function displayResults(data) {
  const { clips, totalDuration, chunkCount } = data;

  document.getElementById('totalDuration').textContent = Math.round(totalDuration);
  document.getElementById('chunkCount').textContent = chunkCount;

  clipsList.innerHTML = '';
  clips.forEach((clip, index) => {
    const clipItem = document.createElement('div');
    clipItem.className = 'clip-item';
    clipItem.setAttribute('role', 'region');
    clipItem.setAttribute('aria-label', `Video clip ${index + 1} of ${clips.length}: ${clip}`);

    const clipName = document.createElement('span');
    clipName.className = 'clip-name';
    clipName.textContent = clip;

    const downloadLink = document.createElement('a');
    downloadLink.className = 'clip-download';
    downloadLink.href = `/api/download/${currentJobId}/${clip}`;
    downloadLink.textContent = 'Download';
    downloadLink.setAttribute('aria-label', `Download clip: ${clip}`);

    clipItem.appendChild(clipName);
    clipItem.appendChild(downloadLink);
    clipsList.appendChild(clipItem);
  });

  downloadZipBtn.onclick = () => {
    window.location.href = `/api/zip/${currentJobId}`;
  };

  loadingState.style.display = 'none';
  resultsSection.style.display = 'block';
}

function showError(message) {
  errorMessage.textContent = message;
  errorSection.style.display = 'block';
}

resetBtn.addEventListener('click', () => {
  uploadForm.reset();
  fileLabel.textContent = 'Choose a video...';
  fileInputWrapper.classList.remove('active');
  uploadForm.style.display = 'block';
  resultsSection.style.display = 'none';
  errorSection.style.display = 'none';
  loadingState.style.display = 'none';
});

dismissErrorBtn.addEventListener('click', () => {
  errorSection.style.display = 'none';
});
