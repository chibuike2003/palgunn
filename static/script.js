// Example for discover_projects.html
document.addEventListener('DOMContentLoaded', () => {
    const searchButton = document.querySelector('.search-bar button');
    const searchInput = document.querySelector('.search-bar input');

    if (searchButton && searchInput) {
        searchButton.addEventListener('click', () => {
            const query = searchInput.value;
            if (query.trim() !== '') {
                // In a real application, you'd send this query to a backend API
                // For now, let's just log it or redirect
                console.log('Searching for:', query);
                alert(`Searching for projects related to: ${query}`);
                // window.location.href = `/search-results.html?q=${encodeURIComponent(query)}`;
            } else {
                alert('Please enter a search term!');
            }
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchButton.click();
            }
        });
    }

    // Example for invite_collaboration.html copy link functionality
    const copyLinkBtn = document.getElementById('copyShareLink');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', () => {
            const shareLinkInput = document.getElementById('shareLinkInput');
            if (shareLinkInput) {
                shareLinkInput.select();
                document.execCommand('copy');
                alert('Share link copied to clipboard!');
            }
        });
    }

    // Example for merge_grow.html (conceptual)
    const submitMergeBtn = document.getElementById('submitMergeRequest');
    if (submitMergeBtn) {
        submitMergeBtn.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent form submission for now
            const description = document.getElementById('mergeDescription').value;
            const targetProject = document.getElementById('targetProject').value;

            if (description.trim() === '' || targetProject === '') {
                alert('Please fill in all details for the merge request.');
                return;
            }

            console.log('Merge Request Submitted:');
            console.log('Description:', description);
            console.log('Target Project:', targetProject);

            alert('Merge request submitted successfully! The project owner will review your changes.');
            // In a real app, you'd send this to a backend API to create a pull request.
        });
    }
});