document.addEventListener('DOMContentLoaded', () => {
    const jobForm = document.getElementById('jobForm');
    const sourceType = document.getElementById('sourceType');
    const spotifyUrlField = document.getElementById('spotifyUrlField');
    const lastfmUsernameField = document.getElementById('lastfmUsernameField');
    const lastfmSourcesField = document.getElementById('lastfmSourcesField');
    const checkOnly = document.getElementById('checkOnly');
    const lastfmCredentialsField = document.getElementById('lastfmCredentialsField');
    const jobsList = document.getElementById('jobsList');
    const refreshJobsBtn = document.getElementById('refreshJobsBtn');
    const settingsForm = document.getElementById('settingsForm');
    const jobDetailsContent = document.getElementById('jobDetailsContent');
    const jobDetailsModal = new bootstrap.Modal(document.getElementById('jobDetailsModal'));

    // Initialize form fields
    updateFormFields();

    // Event listeners
    sourceType.addEventListener('change', updateFormFields);
    checkOnly.addEventListener('change', updateFormFields);
    jobForm.addEventListener('submit', (e) => {
        e.preventDefault();
        startJob();
    });
    refreshJobsBtn.addEventListener('click', loadJobs);
    settingsForm.addEventListener('submit', (e) => {
        e.preventDefault();
        saveSettings();
    });

    // Load jobs on page load
    loadJobs();

    // Update form fields based on source type
    function updateFormFields() {
        spotifyUrlField.classList.add('hidden');
        lastfmUsernameField.classList.add('hidden');
        lastfmSourcesField.classList.add('hidden');
        lastfmCredentialsField.classList.add('hidden');

        if (sourceType.value === 'album' || sourceType.value === 'playlist' || sourceType.value === 'artist') {
            spotifyUrlField.classList.remove('hidden');
        } else if (sourceType.value === 'lastfm_username') {
            lastfmUsernameField.classList.remove('hidden');
            lastfmSourcesField.classList.remove('hidden');
        }

        if (!checkOnly.checked) {
            lastfmCredentialsField.classList.remove('hidden');
        }
    }

    // Start a new job
    function startJob() {
        const data = {
            source_type: sourceType.value,
            source_value: sourceType.value === 'lastfm_username' ? document.getElementById('lastfmUsername').value : document.getElementById('spotifyUrl').value,
            check_only: checkOnly.checked,
            lastfm_email: document.getElementById('lastfmEmail').value,
            lastfm_password: document.getElementById('lastfmPassword').value,
            lastfm_sources: Array.from(lastfmSourcesField.querySelectorAll('input[type="checkbox"]:checked')).map((checkbox) => checkbox.value),
        };

        fetch('/api/start-job', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        })
            .then((response) => response.json())
            .then((result) => {
                alert('Job started successfully!');
                loadJobs();
            })
            .catch((error) => {
                console.error('Error starting job:', error);
                alert('Error starting job');
            });
    }

    // Load active jobs
    function loadJobs() {
        jobsList.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
        fetch('/api/jobs')
            .then((response) => response.json())
            .then((jobs) => {
                if (jobs.length === 0) {
                    jobsList.innerHTML = '<p class="text-center">No active jobs</p>';
                } else {
                    jobsList.innerHTML = jobs.map((job) => `
                        <div class="card mb-3">
                            <div class="card-body">
                                <h5>Job ${job.id}</h5>
                                <p>Status: ${job.status}</p>
                                <p>Progress: ${job.progress}%</p>
                                <button class="btn btn-sm btn-primary" onclick="showJobDetails('${job.id}')">View Details</button>
                            </div>
                        </div>
                    `).join('');
                }
            })
            .catch((error) => {
                console.error('Error loading jobs:', error);
                jobsList.innerHTML = '<p class="text-danger">Error loading jobs</p>';
            });
    }

    // Show job details
    function showJobDetails(jobId) {
        fetch(`/api/job-status/${jobId}`)
            .then((response) => response.json())
            .then((job) => {
                jobDetailsContent.innerHTML = `
                    <p><strong>Status:</strong> ${job.status}</p>
                    <p><strong>Progress:</strong> ${job.progress}%</p>
                    <p><strong>Message:</strong> ${job.message}</p>
                `;
                if (job.missing_artwork && job.missing_artwork.length > 0) {
                    jobDetailsContent.innerHTML += `
                        <h5>Missing Artwork</h5>
                        <ul>
                            ${job.missing_artwork.map((album) => `<li>${album.artist} - ${album.album}</li>`).join('')}
                        </ul>
                    `;
                }
                jobDetailsModal.show();
            })
            .catch((error) => {
                console.error('Error fetching job details:', error);
                jobDetailsContent.innerHTML = '<p class="text-danger">Error loading job details</p>';
                jobDetailsModal.show();
            });
    }

    // Save settings
    function saveSettings() {
        const data = {
            spotify_client_id: document.getElementById('spotifyClientId').value,
            spotify_client_secret: document.getElementById('spotifyClientSecret').value,
            lastfm_api_key: document.getElementById('lastfmApiKey').value,
            lastfm_api_secret: document.getElementById('lastfmApiSecret').value,
        };

        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        })
            .then((response) => response.json())
            .then((result) => {
                alert('Settings saved successfully!');
            })
            .catch((error) => {
                console.error('Error saving settings:', error);
                alert('Error saving settings');
            });
    }
});
