function showSection(sectionId) {
    var sections = document.querySelectorAll('.section');
    sections.forEach(section => {
        section.classList.add('hidden');
    });
    document.getElementById(sectionId).classList.remove('hidden');
}

// Initially show the Dashboard section
document.addEventListener("DOMContentLoaded", function() {
    showSection('dashboard');
    startWebSocket();

    // Initialize SortableJS on the grid container
    new Sortable(document.querySelector('.grid-container'), {
        animation: 150,
        handle: '.card',
        ghostClass: 'sortable-ghost'
    });
});

function getUtilizationClass(value) {
    if (value < 50) {
        return 'green';
    } else if (value < 75) {
        return 'yellow';
    } else {
        return 'red';
    }
}

function updateUtilizationBar(fillElement, textElement, value, unit='%', max=100) {
    const percent = (value / max) * 100;
    fillElement.style.width = Math.min(percent, 100) + '%';
    const utilizationClass = getUtilizationClass(percent);
    fillElement.className = 'utilization-fill ' + utilizationClass;
    if (typeof value === 'number') {
        textElement.textContent = `${value.toFixed(2)} ${unit}`;
    } else {
        textElement.textContent = value;
    }
    if (utilizationClass === 'yellow') {
        textElement.style.color = '#000'; // Black text
    } else {
        textElement.style.color = '#fff'; // White text
    }
}

let cpuChart;
let networkChart;
let networkUploadHistory = [];
let networkDownloadHistory = [];
let networkLabels = [];

// Sorting state
let processSortColumn = 'cpu'; // Default sort by CPU
let processSortOrder = 'desc';
let connectionSortColumn = 'status'; // Default sort by status
let connectionSortOrder = 'asc';

// Store data for sorting
let currentProcessList = [];
let currentConnectionsList = [];

function sortProcesses(column) {
    if (processSortColumn === column) {
        processSortOrder = processSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        processSortColumn = column;
        processSortOrder = column === 'name' ? 'asc' : 'desc';
    }
    renderProcessList();
}

function sortConnections(column) {
    if (connectionSortColumn === column) {
        connectionSortOrder = connectionSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        connectionSortColumn = column;
        connectionSortOrder = 'asc';
    }
    renderConnectionsList();
}

function getSortedProcesses() {
    return [...currentProcessList].sort((a, b) => {
        let aVal, bVal;
        switch (processSortColumn) {
            case 'pid':
                aVal = a.pid;
                bVal = b.pid;
                break;
            case 'name':
                aVal = a.name.toLowerCase();
                bVal = b.name.toLowerCase();
                break;
            case 'cpu':
                aVal = a.cpu_percent;
                bVal = b.cpu_percent;
                break;
            case 'mem':
                aVal = a.memory_percent;
                bVal = b.memory_percent;
                break;
        }
        
        if (processSortColumn === 'name') {
            return processSortOrder === 'asc' ? 
                aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        } else {
            return processSortOrder === 'asc' ? aVal - bVal : bVal - aVal;
        }
    });
}

function getSortedConnections() {
    return [...currentConnectionsList].sort((a, b) => {
        let aVal, bVal;
        switch (connectionSortColumn) {
            case 'proto':
                aVal = a.type;
                bVal = b.type;
                break;
            case 'local':
                aVal = a.laddr || '';
                bVal = b.laddr || '';
                break;
            case 'remote':
                aVal = a.raddr || '';
                bVal = b.raddr || '';
                break;
            case 'status':
                aVal = a.status;
                bVal = b.status;
                break;
        }
        
        return connectionSortOrder === 'asc' ? 
            aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });
}

function renderProcessList() {
    const processContainer = document.getElementById('process_list');
    const sortedProcesses = getSortedProcesses();
    
    // Create header with sort indicators
    const header = `
        <div class="process-header">
            <div class="process-pid" onclick="sortProcesses('pid')">
                PID${processSortColumn === 'pid' ? `<span class="sort-indicator">${processSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
            <div class="process-name" onclick="sortProcesses('name')">
                COMMAND${processSortColumn === 'name' ? `<span class="sort-indicator">${processSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
            <div class="process-cpu" onclick="sortProcesses('cpu')">
                CPU%${processSortColumn === 'cpu' ? `<span class="sort-indicator">${processSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
            <div class="process-mem" onclick="sortProcesses('mem')">
                MEM%${processSortColumn === 'mem' ? `<span class="sort-indicator">${processSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
        </div>
    `;
    
    // Create rows
    const rows = sortedProcesses.map(proc => {
        // Determine CPU color class
        let cpuClass = 'cpu-low';
        if (proc.cpu_percent >= 80) cpuClass = 'cpu-critical';
        else if (proc.cpu_percent >= 50) cpuClass = 'cpu-high';
        else if (proc.cpu_percent >= 20) cpuClass = 'cpu-medium';
        
        // Determine Memory color class
        let memClass = 'mem-low';
        if (proc.memory_percent >= 50) memClass = 'mem-high';
        else if (proc.memory_percent >= 20) memClass = 'mem-medium';
        
        return `
            <div class="process-row">
                <div class="process-pid">${proc.pid}</div>
                <div class="process-name">${proc.name}</div>
                <div class="process-cpu ${cpuClass}">${proc.cpu_percent.toFixed(1)}</div>
                <div class="process-mem ${memClass}">${proc.memory_percent.toFixed(1)}</div>
            </div>
        `;
    }).join('');
    
    processContainer.innerHTML = header + rows;
    
    // Add process count info
    const processCount = sortedProcesses.length;
    if (processCount > 0) {
        const countInfo = document.createElement('div');
        countInfo.style.cssText = 'position: absolute; bottom: 5px; right: 15px; font-size: 11px; color: #8B949E;';
        countInfo.textContent = `${processCount} processes`;
        processContainer.appendChild(countInfo);
    }
}

function renderConnectionsList() {
    const connectionsContainer = document.getElementById('network_connections');
    const sortedConnections = getSortedConnections();
    
    // Create header with sort indicators
    const connHeader = `
        <div class="connection-header">
            <div class="connection-proto" onclick="sortConnections('proto')">
                PROTO${connectionSortColumn === 'proto' ? `<span class="sort-indicator">${connectionSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
            <div class="connection-local" onclick="sortConnections('local')">
                LOCAL ADDRESS${connectionSortColumn === 'local' ? `<span class="sort-indicator">${connectionSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
            <div class="connection-remote" onclick="sortConnections('remote')">
                REMOTE ADDRESS${connectionSortColumn === 'remote' ? `<span class="sort-indicator">${connectionSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
            <div class="connection-status" onclick="sortConnections('status')">
                STATE${connectionSortColumn === 'status' ? `<span class="sort-indicator">${connectionSortOrder === 'asc' ? '▲' : '▼'}</span>` : ''}
            </div>
        </div>
    `;
    
    // Create rows
    const connRows = sortedConnections.map(conn => {
        // Determine status color class
        let statusClass = '';
        const status = conn.status.toLowerCase();
        if (status === 'established') statusClass = 'status-established';
        else if (status === 'listen') statusClass = 'status-listen';
        else if (status === 'time_wait') statusClass = 'status-time-wait';
        else if (status === 'close_wait') statusClass = 'status-close-wait';
        else if (status === 'syn_sent') statusClass = 'status-syn-sent';
        else if (status === 'syn_recv') statusClass = 'status-syn-recv';
        
        return `
            <div class="connection-row">
                <div class="connection-proto">${conn.type.replace('SOCK_', '')}</div>
                <div class="connection-local">${conn.laddr || '-'}</div>
                <div class="connection-remote">${conn.raddr || '-'}</div>
                <div class="connection-status ${statusClass}">${conn.status}</div>
            </div>
        `;
    }).join('');
    
    connectionsContainer.innerHTML = connHeader + connRows;
}

function updateStats(data) {
    // Update General Information
    document.getElementById('hostname').textContent = `Hostname: ${data.hostname}`;
    document.getElementById('uptime_output').textContent = `Uptime: ${data.uptime_output}`;
    document.getElementById('os_release').textContent = `OS: ${data.os_release}`;
    document.getElementById('kernel_version').textContent = `Kernel: ${data.kernel_version}`;
    document.getElementById('logged_in_users').textContent = `Logged-in Users: ${data.logged_in_users}`;

    // Update CPU Information
    document.getElementById('cpu_info').textContent = `Model: ${data.cpu_info}`;
    document.getElementById('cpu_frequency').textContent = `Frequency: ${data.cpu_frequency}`;
    document.getElementById('load_avg').textContent = `Load Avg: ${data.load_avg}`;

    // Update CPU Utilization Bar
    updateUtilizationBar(
        document.getElementById('cpu_utilization_fill'),
        document.getElementById('cpu_utilization_text'),
        data.cpu_utilization
    );

    // Update Memory Info
    document.getElementById('memory_info').innerHTML = `
        <span style="color: #58A6FF;">Total:</span> ${data.memory_total_gb.toFixed(2)} GB | 
        <span style="color: #28a745;">Available:</span> ${data.memory_available_gb.toFixed(2)} GB | 
        <span style="color: #dc3545;">Used:</span> ${data.memory_used_gb.toFixed(2)} GB
    `;

    // Update Memory Utilization Bar
    updateUtilizationBar(
        document.getElementById('memory_utilization_fill'),
        document.getElementById('memory_utilization_text'),
        data.memory_utilization
    );

    // Update Swap Utilization Bar
    updateUtilizationBar(
        document.getElementById('swap_utilization_fill'),
        document.getElementById('swap_utilization_text'),
        data.swap_utilization
    );

    // Update Disk Utilization Bar
    updateUtilizationBar(
        document.getElementById('disk_utilization_fill'),
        document.getElementById('disk_utilization_text'),
        data.disk_utilization
    );

    // Update Network Utilization Bar
    const totalNetwork = data.network_utilization.upload + data.network_utilization.download;
    const maxNetworkSpeed = 10000; // Adjust based on your network capacity
    const networkPercent = (totalNetwork / maxNetworkSpeed) * 100;
    document.getElementById('network_utilization_fill').style.width = Math.min(networkPercent, 100) + '%';
    const utilizationClass = getUtilizationClass(networkPercent);
    document.getElementById('network_utilization_fill').className = 'utilization-fill ' + utilizationClass;
    // Display the formatted network info from backend
    document.getElementById('network_utilization_text').textContent = data.network_info.replace('Upload: ', '').replace(', Download: ', ' / ');

    // Update Network Information
    document.getElementById('network_info').textContent = data.network_info;
    document.getElementById('disk_read_write').textContent = `Disk I/O - Read: ${data.disk_read}, Write: ${data.disk_write}`;

    // Store connection data and render
    if (data.network_connections_list && data.network_connections_list.length > 0) {
        currentConnectionsList = data.network_connections_list.filter(conn => conn.status !== 'NONE');
        renderConnectionsList();
    } else {
        // Fallback to text display
        document.getElementById('network_connections').innerHTML = '<pre>' + data.network_connections + '</pre>';
    }

    // Store process data and render
    currentProcessList = data.process_list;
    renderProcessList();

    // Update Service Statuses
    for (const [serviceName, status] of Object.entries(data.service_status)) {
        const elementId = 'service_' + serviceName;
        const serviceElement = document.getElementById(elementId);
        if (serviceElement) {
            serviceElement.innerHTML = status
                ? '<span class="status-green"><i class="fas fa-check-circle"></i></span>'
                : '<span class="status-red"><i class="fas fa-times-circle"></i></span>';
        }
    }

    // Update Last Updated Time
    document.getElementById('last_updated').textContent = `Last updated: ${data.current_time}`;

    // Update Charts
    updateCharts(data);
}

function updateCharts(data) {
    // Update CPU Chart
    if (!cpuChart) {
        const ctx = document.getElementById('cpu_chart').getContext('2d');
        cpuChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.per_cpu_utilization.map((_, index) => 'CPU ' + index),
                datasets: [{
                    label: 'Per CPU Utilization (%)',
                    data: data.per_cpu_utilization,
                    backgroundColor: data.per_cpu_utilization.map(value => {
                        return value < 50 ? '#28a745' : value < 75 ? '#ffc107' : '#dc3545';
                    }),
                    borderColor: '#58A6FF',
                    borderWidth: 1,
                }]
            },
            options: {
                scales: {
                    y: { beginAtZero: true, max: 100 }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    } else {
        cpuChart.data.datasets[0].data = data.per_cpu_utilization;
        cpuChart.data.datasets[0].backgroundColor = data.per_cpu_utilization.map(value => {
            return value < 50 ? '#28a745' : value < 75 ? '#ffc107' : '#dc3545';
        });
        cpuChart.update();
    }

    // Update Network Chart
    const currentTime = new Date().toLocaleTimeString();
    networkLabels.push(currentTime);
    networkUploadHistory.push(data.network_utilization.upload);
    networkDownloadHistory.push(data.network_utilization.download);

    if (networkLabels.length > 20) {
        networkLabels.shift();
        networkUploadHistory.shift();
        networkDownloadHistory.shift();
    }

    if (!networkChart) {
        const ctx = document.getElementById('network_chart').getContext('2d');
        networkChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: networkLabels,
                datasets: [
                    {
                        label: 'Upload (KB/s)',
                        data: networkUploadHistory,
                        backgroundColor: 'rgba(40, 167, 69, 0.2)',
                        borderColor: '#28a745',
                        fill: true,
                    },
                    {
                        label: 'Download (KB/s)',
                        data: networkDownloadHistory,
                        backgroundColor: 'rgba(88, 166, 255, 0.2)',
                        borderColor: '#58A6FF',
                        fill: true,
                    }
                ]
            },
            options: {
                scales: {
                    y: { beginAtZero: true },
                    x: { display: true }
                },
                plugins: {
                    legend: { display: true }
                }
            }
        });
    } else {
        networkChart.data.labels = networkLabels;
        networkChart.data.datasets[0].data = networkUploadHistory;
        networkChart.data.datasets[1].data = networkDownloadHistory;
        networkChart.update();
    }
}

let ws;

function startWebSocket() {
    const ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const ws_path = ws_scheme + "://" + window.location.host + "/ws";
    ws = new WebSocket(ws_path);

    ws.onopen = function() {
        console.log('WebSocket connection established');
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateStats(data);
    };

    ws.onclose = function() {
        console.log('WebSocket connection closed');
        // Try to reconnect after a delay
        setTimeout(startWebSocket, 5000);
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        ws.close();
    };
}