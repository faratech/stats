/**
 * Enhanced DNF Package Timeline Visualizer
 * Main JavaScript functionality
 *
 * This script provides interactive visualizations for DNF package management
 * history with support for dark/light themes, responsive design, and robust search.
 *
 * @version 1.0.2
 */

// Configuration
const config = {
    apiEndpoint: '?api=data',
    timeRangeEndpoint: '?api=timerange',
    searchEndpoint: '?api=search',
    maxTimelinePackages: 50,
    searchDebounceMs: 300,
    fetchRetryCount: 3,
    fetchRetryDelayMs: 1000
};

// Global variables
let packageData = [];
let filteredPackageData = [];
let timeRangeData = null;
let activityChart = null;
let timeline = null;
let packageTable = null;
let isDarkMode = false;
let detailTimeline = null;
let operationBreakdownChart = null;
let eventTable = null;
let searchTimeout = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing DNF Package Timeline Visualizer...');

    // Set generation date
    document.getElementById('generation-date').textContent = new Date().toLocaleString();

    // Check for saved theme preference
    const savedTheme = localStorage.getItem('packageVisTheme');
    if (savedTheme === 'dark' || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches && !savedTheme)) {
        document.documentElement.setAttribute('data-theme', 'dark');
        isDarkMode = true;
        updateThemeButtons();
    }

    // Set up event listeners
    document.getElementById('days-filter').addEventListener('change', handleDaysFilterChange);
    document.getElementById('search-filter').addEventListener('input', debounce(filterPackages, config.searchDebounceMs));
    document.getElementById('back-to-list').addEventListener('click', showPackageList);
    document.getElementById('toggle-theme').addEventListener('click', toggleTheme);
    document.getElementById('header-theme-toggle').addEventListener('click', toggleTheme);
    document.getElementById('apply-custom-range').addEventListener('click', applyCustomDateRange);

    // Add zoom control listeners
    setupGlobalZoomListeners();

    // Listen for system theme changes
    if (window.matchMedia) {
        const colorSchemeQuery = window.matchMedia('(prefers-color-scheme: dark)');
        colorSchemeQuery.addEventListener('change', (e) => {
            if (!localStorage.getItem('packageVisTheme')) {
                isDarkMode = e.matches;
                document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
                updateThemeButtons();
                updateVisualizationsForTheme();
            }
        });
    }

    // Load time range data
    loadTimeRange();
});

/**
 * Debounce function to limit the rate of function calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function}
 */
function debounce(func, wait) {
    return function(...args) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => func.apply(this, args), wait);
    };
}

/**
 * Set up zoom control listeners for all timeline control buttons
 */
function setupGlobalZoomListeners() {
    const timelineZoomIn = document.getElementById('timeline-zoom-in');
    const timelineZoomOut = document.getElementById('timeline-zoom-out');
    const timelineResetZoom = document.getElementById('timeline-reset-zoom');

    if (timelineZoomIn) {
        timelineZoomIn.addEventListener('click', () => zoomTimeline(timeline, 0.7));
    }
    if (timelineZoomOut) {
        timelineZoomOut.addEventListener('click', () => zoomTimeline(timeline, 1.3));
    }
    if (timelineResetZoom) {
        timelineResetZoom.addEventListener('click', () => {
            if (timeline) timeline.fit({ animation: true });
        });
    }
}

/**
 * Generic timeline zoom function
 * @param {object} timelineObj - The timeline object to zoom
 * @param {number} factor - Zoom factor (< 1 zooms in, > 1 zooms out)
 */
function zoomTimeline(timelineObj, factor) {
    if (!timelineObj) return;
    try {
        const currentRange = timelineObj.getWindow();
        const duration = currentRange.end - currentRange.start;
        const newDuration = duration * factor;
        const center = (currentRange.end.getTime() + currentRange.start.getTime()) / 2;
        const newStart = new Date(center - newDuration / 2);
        const newEnd = new Date(center + newDuration / 2);
        timelineObj.setWindow(newStart, newEnd, { animation: true });
    } catch (error) {
        console.error("Error zooming timeline:", error);
    }
}

/**
 * Retryable fetch function
 * @param {string} url - URL to fetch
 * @param {number} retries - Number of retries left
 * @returns {Promise}
 */
async function fetchWithRetry(url, retries = config.fetchRetryCount) {
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Server responded with status: ${response.status}`);
        return await response.json();
    } catch (error) {
        if (retries > 0) {
            console.warn(`Fetch failed, retrying (${retries} left): ${error}`);
            await new Promise(resolve => setTimeout(resolve, config.fetchRetryDelayMs));
            return fetchWithRetry(url, retries - 1);
        }
        throw error;
    }
}

/**
 * Load time range data from the server
 */
function loadTimeRange() {
    showLoading();
    fetchWithRetry(config.timeRangeEndpoint)
        .then(data => {
            if (data.error) throw new Error(data.error);
            timeRangeData = data;
            updateTimeRangeInfo();
            const startDate = new Date(timeRangeData.earliest * 1000);
            const endDate = new Date(timeRangeData.latest * 1000);
            document.getElementById('start-date').valueAsDate = startDate;
            document.getElementById('end-date').valueAsDate = endDate;
            loadData();
        })
        .catch(error => {
            console.error('Error loading time range data:', error);
            hideLoading();
            showError(`Failed to load time range data: ${error.message}. Please check server connectivity.`);
        });
}

/**
 * Update time range info display
 */
function updateTimeRangeInfo() {
    if (!timeRangeData) return;
    const element = document.getElementById('timerange-info');
    element.innerHTML = `<i class="fas fa-clock"></i> Data range: ${timeRangeData.earliest_date} to ${timeRangeData.latest_date}`;
}

/**
 * Handle days filter change
 */
function handleDaysFilterChange(e) {
    const value = e.target.value;
    const customDateRange = document.getElementById('custom-date-range');
    if (value === 'custom') {
        customDateRange.style.display = 'flex';
        setTimeout(() => customDateRange.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 100);
    } else {
        customDateRange.style.display = 'none';
        loadData();
    }
}

/**
 * Apply custom date range
 */
function applyCustomDateRange() {
    const startDate = document.getElementById('start-date').valueAsDate;
    const endDate = document.getElementById('end-date').valueAsDate;
    if (!startDate || !endDate) {
        showError('Please select both start and end dates.');
        return;
    }
    if (startDate > endDate) {
        showError('Start date must be before end date.');
        return;
    }
    const startTs = Math.floor(startDate.getTime() / 1000);
    const endTs = Math.floor(endDate.getTime() / 1000);
    loadData(startTs, endTs);
}

/**
 * Toggle dark/light theme
 */
function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
    localStorage.setItem('packageVisTheme', isDarkMode ? 'dark' : 'light');
    updateThemeButtons();
    updateVisualizationsForTheme();
}

/**
 * Update theme buttons text and icons
 */
function updateThemeButtons() {
    const footerButton = document.getElementById('toggle-theme');
    const headerButton = document.getElementById('header-theme-toggle');
    footerButton.innerHTML = isDarkMode
        ? '<i class="fas fa-sun"></i> Switch to Light Mode'
        : '<i class="fas fa-moon"></i> Switch to Dark Mode';
    headerButton.innerHTML = isDarkMode ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
}

/**
 * Update all visualizations for theme change
 */
function updateVisualizationsForTheme() {
    if (activityChart) createActivityChart();
    if (timeline) initializeTimeline();
    if (operationBreakdownChart) {
        const detailName = document.getElementById('detail-package-name').textContent;
        if (detailName) {
            const pkg = filteredPackageData.find(p => p.package === detailName) || packageData.find(p => p.package === detailName);
            if (pkg) createOperationBreakdownChart(pkg);
        }
    }
}

/**
 * Show loading indicator
 */
function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

/**
 * Hide loading indicator
 */
function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

/**
 * Show error notification
 * @param {string} message - Error message to display
 */
function showError(message) {
    let errorElement = document.getElementById('error-notification');
    if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.id = 'error-notification';
        errorElement.className = 'error-notification';
        document.body.appendChild(errorElement);
        const style = document.createElement('style');
        style.textContent = `
            .error-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                background-color: #e74c3c;
                color: white;
                padding: 15px 20px;
                border-radius: 5px;
                box-shadow: 0 3px 10px rgba(0,0,0,0.2);
                z-index: 10000;
                max-width: 400px;
                animation: fadeIn 0.3s ease;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-20px); }
                to { opacity: 1; transform: translateY(0); }
            }
        `;
        document.head.appendChild(style);
    }
    errorElement.textContent = message;
    errorElement.style.display = 'block';
    setTimeout(() => errorElement.style.display = 'none', 5000);
}

/**
 * Load data from the server
 */
function loadData(customStartTs = null, customEndTs = null) {
    showLoading();
    let url = config.apiEndpoint;
    if (customStartTs !== null && customEndTs !== null) {
        url += `&start=${customStartTs}&end=${customEndTs}`;
    } else {
        const daysFilter = document.getElementById('days-filter').value;
        if (daysFilter !== 'all' && daysFilter !== 'custom') {
            url += `&days=${daysFilter}`;
        }
    }
    fetchWithRetry(url)
        .then(data => {
            if (data.error) throw new Error(data.error);
            packageData = data;
            filteredPackageData = data;
            document.getElementById('search-filter').value = ''; // Reset search
            updateUI();
        })
        .catch(error => {
            console.error('Error loading data:', error);
            showError(`Failed to load package data: ${error.message}`);
        })
        .finally(() => hideLoading());
}

/**
 * Update all UI components
 */
function updateUI() {
    if (!filteredPackageData.length) {
        showError('No package data found for the selected time range.');
        document.getElementById('total-packages').textContent = '0';
        document.getElementById('recent-updates').textContent = '0';
        document.getElementById('most-active').textContent = '-';
        document.getElementById('operation-summary').innerHTML = '';
        if (activityChart) activityChart.destroy();
        if (timeline) timeline.destroy();
        if (packageTable) packageTable.destroy();
        return;
    }
    updateDashboard();
    initializeTimeline();
    initializeTable();
    calculateOperationSummary();
    document.getElementById('search-results-count').textContent = `Found ${filteredPackageData.length} packages`;
}

/**
 * Calculate and display operation summary
 */
function calculateOperationSummary() {
    if (!filteredPackageData.length) return;
    const operations = {
        'Install': 0,
        'Update': 0,
        'Remove': 0,
        'Downgrade': 0,
        'Reinstall': 0
    };
    filteredPackageData.forEach(pkg => {
        pkg.events.forEach(event => {
            if (operations[event.operation] !== undefined) operations[event.operation]++;
        });
    });
    const summaryContainer = document.getElementById('operation-summary');
    summaryContainer.innerHTML = '';
    for (const [operation, count] of Object.entries(operations)) {
        if (count > 0) {
            const item = document.createElement('div');
            item.className = `operation-item operation-item-${operation.toLowerCase()}`;
            let icon = '';
            switch(operation) {
                case 'Install': icon = '<i class="fas fa-plus-circle"></i>'; break;
                case 'Update': icon = '<i class="fas fa-arrow-circle-up"></i>'; break;
                case 'Remove': icon = '<i class="fas fa-trash-alt"></i>'; break;
                case 'Downgrade': icon = '<i class="fas fa-arrow-circle-down"></i>'; break;
                case 'Reinstall': icon = '<i class="fas fa-sync-alt"></i>'; break;
            }
            item.innerHTML = `${icon} ${operation}: ${count.toLocaleString()}`;
            item.title = `Total ${operation.toLowerCase()} operations: ${count.toLocaleString()}`;
            summaryContainer.appendChild(item);
        }
    }
}

/**
 * Update dashboard statistics and charts
 */
function updateDashboard() {
    if (!filteredPackageData.length) return;
    document.getElementById('total-packages').textContent = filteredPackageData.length.toLocaleString();
    const sevenDaysAgo = Date.now() / 1000 - (7 * 24 * 60 * 60);
    const recentUpdates = filteredPackageData.filter(pkg => pkg.last_event.timestamp > sevenDaysAgo).length;
    document.getElementById('recent-updates').textContent = recentUpdates.toLocaleString();
    let mostActivePackage = filteredPackageData.reduce((prev, current) =>
        (prev.total_events > current.total_events) ? prev : current, {total_events: 0});
    const mostActiveElement = document.getElementById('most-active');
    if (mostActivePackage.package) {
        mostActiveElement.textContent = mostActivePackage.package;
        mostActiveElement.title = `${mostActivePackage.total_events.toLocaleString()} events`;
    } else {
        mostActiveElement.textContent = '-';
        mostActiveElement.title = '';
    }
    createActivityChart();
}

/**
 * Create activity chart showing package operations over time
 */
function createActivityChart() {
    if (!filteredPackageData.length) return;
    if (activityChart) activityChart.destroy();
    let earliest = Number.MAX_SAFE_INTEGER;
    let latest = 0;
    filteredPackageData.forEach(pkg => {
        pkg.events.forEach(event => {
            earliest = Math.min(earliest, event.timestamp);
            latest = Math.max(latest, event.timestamp);
        });
    });
    const timeSpanSeconds = latest - earliest;
    const timeSpanDays = Math.ceil(timeSpanSeconds / (24 * 60 * 60));
    let interval = 1;
    let format = 'MM/DD';
    if (timeSpanDays > 365 * 2) {
        interval = 30;
        format = 'YYYY-MM';
    } else if (timeSpanDays > 365) {
        interval = 15;
        format = 'YYYY-MM-DD';
    } else if (timeSpanDays > 180) {
        interval = 7;
        format = 'MM/DD';
    } else if (timeSpanDays > 60) {
        interval = 3;
        format = 'MM/DD';
    }
    const dateBuckets = {};
    const earliestDate = new Date(earliest * 1000);
    earliestDate.setHours(0, 0, 0, 0);
    for (let i = 0; i <= Math.ceil(timeSpanDays / interval); i++) {
        const date = new Date(earliestDate);
        date.setDate(earliestDate.getDate() + (i * interval));
        let bucketKey = interval >= 30
            ? `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`
            : date.toISOString().split('T')[0];
        dateBuckets[bucketKey] = {
            install: 0,
            update: 0,
            remove: 0,
            downgrade: 0,
            reinstall: 0,
            unknown: 0
        };
    }
    filteredPackageData.forEach(pkg => {
        pkg.events.forEach(event => {
            const eventDate = new Date(event.timestamp * 1000);
            let bucketKey = interval >= 30
                ? `${eventDate.getFullYear()}-${(eventDate.getMonth() + 1).toString().padStart(2, '0')}`
                : eventDate.toISOString().split('T')[0];
            if (!dateBuckets[bucketKey]) {
                const allBuckets = Object.keys(dateBuckets).sort();
                let nearestBucket = allBuckets[0];
                for (const bucket of allBuckets) {
                    if (bucket <= bucketKey) nearestBucket = bucket;
                    else break;
                }
                bucketKey = nearestBucket;
                if (!dateBuckets[bucketKey]) return;
            }
            const operationType = event.operation.toLowerCase();
            if (dateBuckets[bucketKey][operationType] !== undefined) {
                dateBuckets[bucketKey][operationType]++;
            } else {
                dateBuckets[bucketKey].unknown++;
            }
        });
    });
    const labels = Object.keys(dateBuckets).sort();
    const datasets = [
        {
            label: 'Install',
            data: labels.map(date => dateBuckets[date].install),
            backgroundColor: isDarkMode ? 'rgba(46, 204, 113, 0.7)' : 'rgba(46, 204, 113, 0.8)',
            borderColor: isDarkMode ? 'rgba(46, 204, 113, 1)' : 'rgba(39, 174, 96, 1)',
            borderWidth: 1
        },
        {
            label: 'Update',
            data: labels.map(date => dateBuckets[date].update),
            backgroundColor: isDarkMode ? 'rgba(52, 152, 219, 0.7)' : 'rgba(52, 152, 219, 0.8)',
            borderColor: isDarkMode ? 'rgba(52, 152, 219, 1)' : 'rgba(41, 128, 185, 1)',
            borderWidth: 1
        },
        {
            label: 'Remove',
            data: labels.map(date => dateBuckets[date].remove),
            backgroundColor: isDarkMode ? 'rgba(231, 76, 60, 0.7)' : 'rgba(231, 76, 60, 0.8)',
            borderColor: isDarkMode ? 'rgba(231, 76, 60, 1)' : 'rgba(192, 57, 43, 1)',
            borderWidth: 1
        },
        {
            label: 'Downgrade',
            data: labels.map(date => dateBuckets[date].downgrade),
            backgroundColor: isDarkMode ? 'rgba(241, 196, 15, 0.7)' : 'rgba(241, 196, 15, 0.8)',
            borderColor: isDarkMode ? 'rgba(241, 196, 15, 1)' : 'rgba(243, 156, 18, 1)',
            borderWidth: 1
        },
        {
            label: 'Reinstall',
            data: labels.map(date => dateBuckets[date].reinstall),
            backgroundColor: isDarkMode ? 'rgba(155, 89, 182, 0.7)' : 'rgba(155, 89, 182, 0.8)',
            borderColor: isDarkMode ? 'rgba(155, 89, 182, 1)' : 'rgba(142, 68, 173, 1)',
            borderWidth: 1
        }
    ];
    if (labels.some(date => dateBuckets[date].unknown > 0)) {
        datasets.push({
            label: 'Unknown',
            data: labels.map(date => dateBuckets[date].unknown),
            backgroundColor: isDarkMode ? 'rgba(189, 195, 199, 0.7)' : 'rgba(189, 195, 199, 0.8)',
            borderColor: isDarkMode ? 'rgba(189, 195, 199, 1)' : 'rgba(127, 140, 141, 1)',
            borderWidth: 1
        });
    }
    const labelDisplayFormat = interval >= 30
        ? (date) => {
            const [year, month] = date.split('-');
            return `${month}/${year.substring(2)}`;
        }
        : (date) => {
            const d = new Date(date);
            return `${d.getMonth()+1}/${d.getDate()}`;
        };
    const ctx = document.getElementById('activity-chart').getContext('2d');
    const gridColor = isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
    const textColor = isDarkMode ? '#ccc' : '#666';
    activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.map(labelDisplayFormat),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true,
                    title: { display: true, text: 'Date', color: textColor },
                    ticks: { color: textColor },
                    grid: { color: gridColor }
                },
                y: {
                    stacked: true,
                    title: { display: true, text: 'Number of Events', color: textColor },
                    ticks: { color: textColor },
                    grid: { color: gridColor }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: textColor, padding: 20, usePointStyle: true, pointStyle: 'circle' }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        title: function(tooltipItems) {
                            return labels[tooltipItems[0].dataIndex];
                        }
                    }
                }
            }
        }
    });
}

/**
 * Initialize main timeline visualization
 */
function initializeTimeline() {
    if (!filteredPackageData.length) return;
    if (timeline) timeline.destroy();
    const items = [];
    const groups = [];
    const topPackages = filteredPackageData.slice(0, config.maxTimelinePackages);
    topPackages.forEach((pkg, index) => {
        groups.push({ id: index, content: pkg.package });
        pkg.events.forEach(event => {
            items.push({
                group: index,
                content: event.operation,
                title: `${pkg.package}: ${event.operation} on ${event.human_date}`,
                start: new Date(event.timestamp * 1000),
                className: `event-${event.operation.toLowerCase()}`
            });
        });
    });
    const timelineContainer = document.getElementById('timeline');
    const options = {
        zoomable: true,
        stack: false,
        groupOrder: 'content',
        verticalScroll: true,
        maxHeight: '500px',
        minHeight: '500px',
        orientation: 'top',
        tooltip: { followMouse: true, overflowMethod: 'cap' }
    };
    try {
        timeline = new vis.Timeline(timelineContainer, items, groups, options);
        addTimelineStyles();
    } catch (error) {
        console.error("Error creating timeline:", error);
        showError("Failed to create timeline visualization.");
    }
}

/**
 * Add custom styles for timeline events
 */
function addTimelineStyles() {
    let style = document.getElementById('timeline-styles');
    if (!style) {
        style = document.createElement('style');
        style.id = 'timeline-styles';
        document.head.appendChild(style);
    }
    style.textContent = `
        .event-install { background-color: var(--event-install) !important; border-color: var(--event-install-border) !important; color: #fff !important; font-weight: bold; }
        .event-update { background-color: var(--event-update) !important; border-color: var(--event-update-border) !important; color: #fff !important; font-weight: bold; }
        .event-remove { background-color: var(--event-remove) !important; border-color: var(--event-remove-border) !important; color: #fff !important; font-weight: bold; }
        .event-downgrade { background-color: var(--event-downgrade) !important; border-color: var(--event-downgrade-border) !important; color: #000 !important; font-weight: bold; }
        .event-reinstall { background-color: var(--event-reinstall) !important; border-color: var(--event-reinstall-border) !important; color: #fff !important; font-weight: bold; }
        .event-unknown { background-color: var(--event-unknown) !important; border-color: var(--event-unknown-border) !important; color: #333 !important; font-weight: bold; }
    `;
}

/**
 * Initialize package data table
 */
function initializeTable() {
    if (!filteredPackageData.length) return;
    if (packageTable) packageTable.destroy();
    const tableBody = document.getElementById('package-table-body');
    tableBody.innerHTML = '';
    filteredPackageData.forEach(pkg => {
        const row = document.createElement('tr');
        const nameCell = document.createElement('td');
        nameCell.textContent = pkg.package;
        row.appendChild(nameCell);
        const lastUpdatedCell = document.createElement('td');
        lastUpdatedCell.textContent = pkg.last_event.human_date;
        lastUpdatedCell.title = pkg.last_event.operation;
        row.appendChild(lastUpdatedCell);
        const firstInstalledCell = document.createElement('td');
        firstInstalledCell.textContent = pkg.first_event.human_date;
        row.appendChild(firstInstalledCell);
        const totalEventsCell = document.createElement('td');
        totalEventsCell.textContent = pkg.total_events.toLocaleString();
        row.appendChild(totalEventsCell);
        const actionsCell = document.createElement('td');
        const viewButton = document.createElement('button');
        viewButton.className = 'view-details-btn';
        viewButton.innerHTML = '<i class="fas fa-chart-line"></i> View Details';
        viewButton.addEventListener('click', () => showPackageDetails(pkg));
        actionsCell.appendChild(viewButton);
        row.appendChild(actionsCell);
        tableBody.appendChild(row);
    });
    try {
        packageTable = $('#package-table').DataTable({
            paging: true,
            searching: true,
            ordering: true,
            info: true,
            pageLength: 25,
            responsive: true,
            order: [[3, 'desc']],
            language: {
                search: "Search packages:",
                lengthMenu: "Show _MENU_ packages per page",
                info: "Showing _START_ to _END_ of _TOTAL_ packages",
                infoEmpty: "No packages found",
                infoFiltered: "(filtered from _MAX_ total packages)",
                paginate: {
                    first: '<i class="fas fa-angle-double-left"></i>',
                    last: '<i class="fas fa-angle-double-right"></i>',
                    next: '<i class="fas fa-angle-right"></i>',
                    previous: '<i class="fas fa-angle-left"></i>'
                }
            }
        });
    } catch (error) {
        console.error("Error initializing DataTable:", error);
        showError("Failed to initialize package table.");
    }
}

/**
 * Show package details view
 */
function showPackageDetails(pkg) {
    document.querySelector('.timeline-section').style.display = 'none';
    document.querySelector('.data-table-section').style.display = 'none';
    const detailSection = document.getElementById('package-detail-section');
    detailSection.style.display = 'block';
    document.getElementById('detail-package-name').textContent = pkg.package;
    const eventTableBody = document.getElementById('event-table-body');
    eventTableBody.innerHTML = '';
    pkg.events.forEach(event => {
        const row = document.createElement('tr');
        const dateCell = document.createElement('td');
        dateCell.textContent = event.human_date;
        row.appendChild(dateCell);
        const operationCell = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = `operation-badge operation-${event.operation.toLowerCase()}`;
        badge.textContent = event.operation;
        operationCell.appendChild(badge);
        row.appendChild(operationCell);
        eventTableBody.appendChild(row);
    });
    try {
        if ($.fn.DataTable drunkenDataTable('#event-table')) {
            $('#event-table').DataTable().destroy();
        }
        eventTable = $('#event-table').DataTable({
            paging: true,
            searching: false,
            ordering: true,
            info: true,
            pageLength: 15,
            order: [[0, 'desc']],
            responsive: true,
            language: {
                info: "Showing _START_ to _END_ of _TOTAL_ events",
                infoEmpty: "No events found",
                paginate: {
                    first: '<i class="fas fa-angle-double-left"></i>',
                    last: '<i class="fas fa-angle-double-right"></i>',
                    next: '<i class="fas fa-angle-right"></i>',
                    previous: '<i class="fas fa-angle-left"></i>'
                }
            }
        });
        createDetailTimeline(pkg);
        createOperationBreakdownChart(pkg);
        setupDetailZoomControls();
    } catch (error) {
        console.error("Error initializing detail view:", error);
        showError("Failed to show package details.");
    }
}

/**
 * Set up zoom controls for detail timeline
 */
function setupDetailZoomControls() {
    const detailZoomIn = document.getElementById('detail-zoom-in');
    const detailZoomOut = document.getElementById('detail-zoom-out');
    const detailResetZoom = document.getElementById('detail-reset-zoom');
    if (detailZoomIn && detailTimeline) {
        detailZoomIn.addEventListener('click', () => zoomTimeline(detailTimeline, 0.7));
    }
    if (detailZoomOut && detailTimeline) {
        detailZoomOut.addEventListener('click', () => zoomTimeline(detailTimeline, 1.3));
    }
    if (detailResetZoom && detailTimeline) {
        detailResetZoom.addEventListener('click', () => detailTimeline.fit({ animation: true }));
    }
}

/**
 * Create detailed timeline for a specific package
 */
function createDetailTimeline(pkg) {
    const container = document.getElementById('detail-timeline');
    const items = pkg.events.map(event => ({
        content: event.operation,
        title: `${event.operation} on ${event.human_date}`,
        start: new Date(event.timestamp * 1000),
        className: `event-${event.operation.toLowerCase()}`
    }));
    const options = {
        zoomable: true,
        stack: false,
        height: '250px',
        minHeight: '250px',
        tooltip: { followMouse: true, overflowMethod: 'cap' }
    };
    try {
        if (detailTimeline) detailTimeline.destroy();
        detailTimeline = new vis.Timeline(container, items, options);
    } catch (error) {
        console.error("Error creating detail timeline:", error);
        showError("Failed to create package timeline.");
    }
}

/**
 * Create operation breakdown chart for a specific package
 */
function createOperationBreakdownChart(pkg) {
    const chartContainer = document.getElementById('operation-chart-container');
    chartContainer.innerHTML = '<canvas id="operation-breakdown-chart"></canvas>';
    const operationCounts = {
        'Install': 0,
        'Update': 0,
        'Remove': 0,
        'Downgrade': 0,
        'Reinstall': 0,
        'Unknown': 0
    };
    pkg.events.forEach(event => {
        if (operationCounts[event.operation] !== undefined) {
            operationCounts[event.operation]++;
        } else {
            operationCounts['Unknown']++;
        }
    });
    const labels = Object.keys(operationCounts).filter(op => operationCounts[op] > 0);
    const data = labels.map(op => operationCounts[op]);
    const backgroundColors = {
        'Install': isDarkMode ? 'rgba(46, 204, 113, 0.7)' : 'rgba(46, 204, 113, 0.8)',
        'Update': isDarkMode ? 'rgba(52, 152, 219, 0.7)' : 'rgba(52, 152, 219, 0.8)',
        'Remove': isDarkMode ? 'rgba(231, 76, 60, 0.7)' : 'rgba(231, 76, 60, 0.8)',
        'Downgrade': isDarkMode ? 'rgba(241, 196, 15, 0.7)' : 'rgba(241, 196, 15, 0.8)',
        'Reinstall': isDarkMode ? 'rgba(155, 89, 182, 0.7)' : 'rgba(155, 89, 182, 0.8)',
        'Unknown': isDarkMode ? 'rgba(189, 195, 199, 0.7)' : 'rgba(189, 195, 199, 0.8)'
    };
    const colors = labels.map(op => backgroundColors[op]);
    const ctx = document.getElementById('operation-breakdown-chart').getContext('2d');
    const textColor = isDarkMode ? '#ccc' : '#666';
    try {
        if (operationBreakdownChart) operationBreakdownChart.destroy();
        operationBreakdownChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 1,
                    borderColor: isDarkMode ? '#2a2a3c' : '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: textColor,
                            padding: 20,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((value / total) * 100);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: 'Operation Breakdown',
                        color: textColor,
                        font: { size: 16, weight: 'bold' },
                        padding: { top: 10, bottom: 20 }
                    }
                }
            }
        });
    } catch (error) {
        console.error("Error creating operation breakdown chart:", error);
        showError("Failed to create operation chart.");
    }
}

/**
 * Show package list view
 */
function showPackageList() {
    document.querySelector('.timeline-section').style.display = 'block';
    document.querySelector('.data-table-section').style.display = 'block';
    document.getElementById('package-detail-section').style.display = 'none';
    if (detailTimeline) {
        detailTimeline.destroy();
        detailTimeline = null;
    }
    if (operationBreakdownChart) {
        operationBreakdownChart.destroy();
        operationBreakdownChart = null;
    }
    if (eventTable) {
        eventTable.destroy();
        eventTable = null;
    }
}

/**
 * Filter packages based on search input
 */
function filterPackages() {
    const searchText = document.getElementById('search-filter').value.trim().toLowerCase();
    showLoading();
    if (searchText.length >= 3) {
        fetchWithRetry(`${config.searchEndpoint}&query=${encodeURIComponent(searchText)}`)
            .then(data => {
                if (data.error) throw new Error(data.error);
                filteredPackageData = packageData.filter(pkg => data.packages.includes(pkg.package));
                updateUI();
            })
            .catch(error => {
                console.error('Error searching packages:', error);
                showError(`Failed to search packages: ${error.message}`);
                filteredPackageData = packageData;
                updateUI();
            })
            .finally(() => hideLoading());
    } else {
        filteredPackageData = packageData.filter(pkg => pkg.package.toLowerCase().includes(searchText));
        updateUI();
        hideLoading();
    }
}

// Run initial setup when DOM is fully loaded
window.addEventListener('load', function() {
    document.addEventListener('keydown', function(e) {
        if (e.key === 'D' && e.shiftKey) {
            toggleTheme();
            e.preventDefault();
        }
        if (e.key === 'Escape' && document.getElementById('package-detail-section').style.display !== 'none') {
            showPackageList();
            e.preventDefault();
        }
    });
    window.addEventListener('resize', function() {
        if (timeline) timeline.redraw();
        if (detailTimeline) detailTimeline.redraw();
    });
    window.addEventListener('beforeprint', () => document.body.classList.add('printing'));
    window.addEventListener('afterprint', () => document.body.classList.remove('printing'));
});
