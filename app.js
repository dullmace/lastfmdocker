document.addEventListener('DOMContentLoaded', () => {
    const jobForm = document.getElementById('jobForm');
    const jobsList = document.getElementById('jobsList');
    const refreshJobsBtn = document.getElementById('refreshJobsBtn');
    const settingsForm = document.getElementById('settingsForm');

    // Load jobs on page load
    loadJobs();

    // Event listener for job form submission
    jobForm.addEventListener('submit', (e) => {
        e.preventDefault();
        startJob();
    });

    // Event listener for refreshing jobs
    refreshJobsBtn.addEventListener('click', loadJobs);

    // Event listener for saving settings
    settingsForm.addEventListener('submit', (e) => {
        e.preventDefault();
        saveSettings();
    });

    // Fetch and display active jobs
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

    // Start a new job
    function startJob() {
        const formData = new FormData(jobForm);
        const data = Object.fromEntries(formData.entries());
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

    // Save settings
    function saveSettings() {
        const formData = new FormData(settingsForm);
        const data = Object.fromEntries(formData.entries());
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
