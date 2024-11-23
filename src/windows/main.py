from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import psutil
from datetime import datetime
import platform
import socket
import os
import win32service
import win32serviceutil
import subprocess
import webbrowser

app = FastAPI()

# Cache for static data
static_data = {}

# Initialize static data that doesn't change frequently
async def initialize_static_data():
    static_data['cpu_info'] = get_cpu_info()
    static_data['kernel_version'] = platform.release()
    static_data['os_release'] = platform.platform()
    static_data['hostname'] = socket.gethostname()
    static_data['cpu_frequency'] = get_cpu_frequency()
    static_data['logged_in_users'] = get_logged_in_users()

def get_logged_in_users():
    try:
        users = psutil.users()
        return len(users)
    except Exception:
        return 0

# Function to check service status on Windows
async def get_service_status():
    # List of critical Windows services to monitor
    services = {
        'Spooler': 'Print Spooler',
        'W32Time': 'Windows Time',
        'WinDefend': 'Windows Defender Antivirus Service',
        'wuauserv': 'Windows Update',
        'Dhcp': 'DHCP Client',
        'Dnscache': 'DNS Client',
        'LanmanServer': 'Server',
        'LanmanWorkstation': 'Workstation',
        'TermService': 'Remote Desktop Services',
        'EventLog': 'Windows Event Log',
        'PlugPlay': 'Plug and Play',
        'RemoteRegistry': 'Remote Registry',
        'RpcSs': 'Remote Procedure Call (RPC)',
        'Themes': 'Themes',
        'AudioSrv': 'Windows Audio',
        'BITS': 'Background Intelligent Transfer Service',
        'Winmgmt': 'Windows Management Instrumentation',
        'SecurityHealthService': 'Windows Security Service',
        'IKEEXT': 'IKE and AuthIP IPsec Keying Modules',
        'PolicyAgent': 'IPsec Policy Agent',
        'EventSystem': 'COM+ Event System',
        'MpsSvc': 'Windows Firewall',
        'SharedAccess': 'Internet Connection Sharing (ICS)',
        'SamSs': 'Security Accounts Manager',
        'SENS': 'System Event Notification Service',
        'SessionEnv': 'Remote Desktop Configuration',
        'ShellHWDetection': 'Shell Hardware Detection',
        'gpsvc': 'Group Policy Client',
        'NlaSvc': 'Network Location Awareness',
        'Netlogon': 'Net Logon',
        'Netman': 'Network Connections',
        'WlanSvc': 'WLAN AutoConfig',
        'Wcmsvc': 'Windows Connection Manager',
        'iphlpsvc': 'IP Helper',
        'Audiosrv': 'Windows Audio',
        'AudioEndpointBuilder': 'Windows Audio Endpoint Builder',
        'Appinfo': 'Application Information',
        'BITS': 'Background Intelligent Transfer Service',
        'Browser': 'Computer Browser',
        'CryptSvc': 'Cryptographic Services',
        'DcomLaunch': 'DCOM Server Process Launcher',
        'dot3svc': 'Wired AutoConfig',
        'EapHost': 'Extensible Authentication Protocol',
        'fdPHost': 'Function Discovery Provider Host',
        'FDResPub': 'Function Discovery Resource Publication',
        'hkmsvc': 'Health Key and Certificate Management',
        'HomeGroupListener': 'HomeGroup Listener',
        'HomeGroupProvider': 'HomeGroup Provider',
        'IKEEXT': 'IKE and AuthIP IPsec Keying Modules',
        'lmhosts': 'TCP/IP NetBIOS Helper',
        'MSDTC': 'Distributed Transaction Coordinator',
        'NcdAutoSetup': 'Network Connected Devices Auto-Setup',
        'NlaSvc': 'Network Location Awareness',
        'nsi': 'Network Store Interface Service',
        'PeerDistSvc': 'BranchCache',
        'PnrpAutoReg': 'PNRP Machine Name Publication Service',
        'PNRPSvc': 'Peer Name Resolution Protocol',
        'PolicyAgent': 'IPsec Policy Agent',
        'RpcLocator': 'Remote Procedure Call (RPC) Locator',
        'RemoteAccess': 'Routing and Remote Access',
        'RemoteRegistry': 'Remote Registry',
        'Schedule': 'Task Scheduler',
        'SessionEnv': 'Remote Desktop Configuration',
        'SSDPSRV': 'SSDP Discovery',
        'TermService': 'Remote Desktop Services',
        'TrkWks': 'Distributed Link Tracking Client',
        'W32Time': 'Windows Time',
        'WinHttpAutoProxySvc': 'WinHTTP Web Proxy Auto-Discovery Service',
        'Winmgmt': 'Windows Management Instrumentation',
        'WSearch': 'Windows Search',
        'wuauserv': 'Windows Update',
    }
    service_status = {}
    for service_name, display_name in services.items():
        try:
            status = win32serviceutil.QueryServiceStatus(service_name)[1]
            service_status[display_name] = (status == win32service.SERVICE_RUNNING)
        except Exception:
            service_status[display_name] = False
    return service_status

# Function to get network connections
def get_network_connections():
    try:
        connections = psutil.net_connections(kind='inet')
        formatted_connections = []
        for conn in connections:
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
            formatted_connections.append({
                'type': 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP',
                'laddr': laddr,
                'raddr': raddr,
                'status': conn.status
            })
        return formatted_connections
    except Exception:
        return []

# Function to get CPU info
def get_cpu_info():
    try:
        return platform.processor()
    except Exception:
        return "N/A"

# Function to get CPU frequency
def get_cpu_frequency():
    try:
        cpu_freq = psutil.cpu_freq()
        return f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A"
    except Exception:
        return "N/A"

# Function to collect stats
async def collect_stats(previous_net_io):
    try:
        # Get service statuses
        service_status = await get_service_status()

        # Get utilization data using psutil
        cpu_utilization = psutil.cpu_percent(interval=0)
        per_cpu_utilization = psutil.cpu_percent(interval=0, percpu=True)
        memory = psutil.virtual_memory()
        memory_utilization = memory.percent
        swap = psutil.swap_memory()
        swap_utilization = swap.percent
        disk = psutil.disk_usage('C:\\')
        disk_utilization = disk.percent

        # Get uptime
        uptime_seconds = int(datetime.now().timestamp() - psutil.boot_time())
        uptime_hours = uptime_seconds // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60
        uptime_seconds_remaining = uptime_seconds % 60
        uptime_output = f"{uptime_hours}h {uptime_minutes}m {uptime_seconds_remaining}s"

        # Get processes and sort by CPU utilization
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            cpu_percent = p.info.get('cpu_percent', 0.0)
            memory_percent = p.info.get('memory_percent', 0.0)
            processes.append({
                'pid': p.info['pid'],
                'name': p.info['name'],
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent
            })
        # Sort processes by CPU utilization descending
        processes_sorted = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)
        # Limit to top 10 processes to reduce data size
        processes_sorted = processes_sorted[:10]

        # Network info
        net_io = psutil.net_io_counters()
        sent_bytes = net_io.bytes_sent
        recv_bytes = net_io.bytes_recv
        if previous_net_io is not None:
            sent_rate = (sent_bytes - previous_net_io.bytes_sent) / 1024  # KB/s
            recv_rate = (recv_bytes - previous_net_io.bytes_recv) / 1024  # KB/s
        else:
            sent_rate = 0
            recv_rate = 0
        network_info = f"Upload: {sent_rate:.2f} KB/s, Download: {recv_rate:.2f} KB/s"
        network_utilization = {'upload': sent_rate, 'download': recv_rate}

        # Open and active network connections
        network_connections = get_network_connections()
        # Format network connections
        connections_str = "\n".join([
            f"Proto: {conn['type']}, Local Address: {conn['laddr']}, Remote Address: {conn['raddr']}, Status: {conn['status']}"
            for conn in network_connections if conn['status'] == 'ESTABLISHED'
        ])

        # Disk I/O stats
        disk_io = psutil.disk_io_counters()
        disk_read = f"{disk_io.read_bytes >> 20} MB"
        disk_write = f"{disk_io.write_bytes >> 20} MB"

        # Load average (not available on Windows)
        load_avg_str = "N/A"

        # Current time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Package all stats into a dictionary
        stats = {
            'cpu_utilization': cpu_utilization,
            'per_cpu_utilization': per_cpu_utilization,
            'memory_utilization': memory_utilization,
            'swap_utilization': swap_utilization,
            'disk_utilization': disk_utilization,
            'network_utilization': network_utilization,
            'service_status': service_status,
            'current_time': current_time,
            'uptime_output': uptime_output,
            'process_list': processes_sorted,  # Send as list of dicts
            'network_info': network_info,
            'network_connections': connections_str,
            'disk_read': disk_read,
            'disk_write': disk_write,
            'load_avg': load_avg_str,
            'current_net_io': net_io  # Include for next iteration
        }

        # Combine static data and dynamic stats
        stats.update(static_data)

        return stats
    except Exception as e:
        print(f"Error collecting stats: {e}")
        return {}

# WebSocket endpoint to stream stats
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await initialize_static_data()  # Ensure static data is initialized
    previous_net_io = None
    try:
        while True:
            stats = await collect_stats(previous_net_io)
            await websocket.send_json(stats)
            await asyncio.sleep(1)  # Adjust the interval as needed
            previous_net_io = stats.get('current_net_io')
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()

# Serve the HTML page
@app.get("/", response_class=HTMLResponse)
async def index():
    html_content = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>System Monitor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
    <!-- Meta tags to prevent caching -->
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <!-- Include Chart.js for interactive charts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- Include SortableJS for draggable grid items -->
    <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.13.0/Sortable.min.js"></script>
    <style>
        body { font-family: 'Inter', sans-serif; margin: 0; padding: 0; background-color: #0D1117; color: #C9D1D9; }
        .container { padding: 20px; }
        .navbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: #161B22;
            padding: 10px 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
        .navbar img { height: 40px; }
        .navbar h1 {
            color: #58A6FF;
            margin: 0;
            font-size: 24px;
        }
        h2 { color: #D69D85; cursor: pointer; }
        h3 { color: #58A6FF; }
        pre { background: #1A1E25; padding: 10px; border: 1px solid #58A6FF; box-shadow: 0 0 10px #58A6FF; margin-top: 10px; overflow: auto; max-height: 600px; }
        .section { margin-bottom: 20px; }
        .footer { margin-top: 20px; font-size: 0.9em; color: #888; text-align: center; }
        .status-green { color: #28a745; }
        .status-red { color: #dc3545; }
        .utilization-bar {
            background-color: #1A1E25;
            border: 1px solid #343a40;
            border-radius: 5px;
            overflow: hidden;
            height: 20px;
            margin-top: 5px;
            width: 100%;
            position: relative;
        }
        .utilization-fill {
            height: 100%;
            transition: width 0.5s;
        }
        .utilization-fill.green { background-color: #28a745; }
        .utilization-fill.yellow { background-color: #ffc107; }
        .utilization-fill.red { background-color: #dc3545; }
        .utilization-text {
            position: absolute;
            width: 100%;
            text-align: center;
            top: 0;
            left: 0;
            line-height: 20px;
            font-size: 12px;
            color: #fff;
        }
        canvas { background-color: #1A1E25; }
        .metric {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
        .metric-icon {
            margin-right: 10px;
        }
        .chart-container {
            width: 100%;
            max-width: 400px;
            margin: auto;
        }
        .progress-container {
            width: 100%;
            max-width: 600px;
            margin: auto;
        }
        /* Grid layout */
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        .card {
            background-color: #161B22;
            padding: 15px;
            border: 1px solid #343a40;
            border-radius: 5px;
            box-shadow: 0 0 10px #343a40;
            cursor: move; /* Indicate draggable */
        }
        .card h3 {
            margin-top: 0;
            color: #D69D85;
        }
        .card pre {
            border: none;
            box-shadow: none;
            margin-top: 10px;
        }
        .chart-small {
            width: 100%;
            max-width: 300px;
            margin: auto;
        }
        .service-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .service-status {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background-color: #1A1E25;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #343a40;
        }
        .service-status i {
            margin-right: 10px;
        }
        /* Full-width card */
        .full-width {
            grid-column: 1 / -1;
        }
        /* Double-width card */
        .double-width {
            grid-column: span 2;
        }
        /* Sortable ghost class */
        .sortable-ghost {
            opacity: 0.4;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>System Monitor</h1>
    </div>
    <div class="container">
        <div id="dashboard" class="section">
            <h2>System Dashboard</h2>
            <div class="grid-container">
                <!-- General Information Card -->
                <div class="card">
                    <h3><i class="fas fa-info-circle"></i> General Info</h3>
                    <p id="hostname"></p>
                    <p id="uptime_output"></p>
                    <p id="os_release"></p>
                    <p id="kernel_version"></p>
                    <p id="logged_in_users"></p>
                </div>
                <!-- CPU Utilization Card -->
                <div class="card">
                    <h3><i class="fas fa-microchip"></i> CPU</h3>
                    <p id="cpu_info"></p>
                    <p id="cpu_frequency"></p>
                    <div class="utilization-bar">
                        <div id="cpu_utilization_fill" class="utilization-fill" style="width: 0%;"></div>
                        <div id="cpu_utilization_text" class="utilization-text">0%</div>
                    </div>
                    <p id="load_avg"></p>
                    <div class="chart-small">
                        <canvas id="cpu_chart" width="300" height="150"></canvas>
                    </div>
                </div>
                <!-- Memory Utilization Card -->
                <div class="card">
                    <h3><i class="fas fa-memory"></i> Memory</h3>
                    <div class="utilization-bar">
                        <div id="memory_utilization_fill" class="utilization-fill" style="width: 0%;"></div>
                        <div id="memory_utilization_text" class="utilization-text">0%</div>
                    </div>
                    <h3><i class="fas fa-hdd"></i> Swap</h3>
                    <div class="utilization-bar">
                        <div id="swap_utilization_fill" class="utilization-fill" style="width: 0%;"></div>
                        <div id="swap_utilization_text" class="utilization-text">0%</div>
                    </div>
                </div>
                <!-- Disk Utilization Card -->
                <div class="card">
                    <h3><i class="fas fa-database"></i> Disk</h3>
                    <div class="utilization-bar">
                        <div id="disk_utilization_fill" class="utilization-fill" style="width: 0%;"></div>
                        <div id="disk_utilization_text" class="utilization-text">0%</div>
                    </div>
                    <p id="disk_read_write"></p>
                </div>
                <!-- Network Card -->
                <div class="card">
                    <h3><i class="fas fa-network-wired"></i> Network</h3>
                    <p id="network_info"></p>
                    <div class="utilization-bar">
                        <div id="network_utilization_fill" class="utilization-fill" style="width: 0%;"></div>
                        <div id="network_utilization_text" class="utilization-text">0 KB/s</div>
                    </div>
                    <div class="chart-small">
                        <canvas id="network_chart" width="300" height="150"></canvas>
                    </div>
                </div>
                <!-- Services Card -->
                <div class="card">
                    <h3><i class="fas fa-server"></i> Services</h3>
                    <div class="service-list" id="service_list">
                        <!-- Service statuses will be dynamically generated -->
                    </div>
                </div>
                <!-- Top Processes Card -->
                <div class="card double-width">
                    <h3><i class="fas fa-tasks"></i> Top Processes</h3>
                    <pre id="process_list"></pre>
                </div>
                <!-- Network Connections Card -->
                <div class="card full-width">
                    <h3><i class="fas fa-plug"></i> Active Connections</h3>
                    <pre id="network_connections"></pre>
                </div>
            </div>
            <div class="footer" id="last_updated">
                Last updated: --
            </div>
        </div>
    </div>
    <script>
        function showSection(sectionId) {
            var sections = document.querySelectorAll('.section');
            sections.forEach(function(section) {
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
            textElement.textContent = `${value.toFixed(2)} ${unit}`;
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
            updateUtilizationBar(
                document.getElementById('network_utilization_fill'),
                document.getElementById('network_utilization_text'),
                totalNetwork,
                'KB/s',
                maxNetworkSpeed
            );

            // Update Network Information
            document.getElementById('network_info').textContent = data.network_info;
            document.getElementById('disk_read_write').textContent = `Disk I/O - Read: ${data.disk_read}, Write: ${data.disk_write}`;

            // Update Network Connections
            document.getElementById('network_connections').textContent = data.network_connections;

            // Update Process List
            const processList = data.process_list.map(function(proc) {
                return `PID: ${proc.pid}, Name: ${proc.name}, CPU%: ${proc.cpu_percent.toFixed(1)}, MEM%: ${proc.memory_percent.toFixed(1)}`;
            }).join('\n');
            document.getElementById('process_list').textContent = processList;

            // Update Service Statuses
            const serviceListElement = document.getElementById('service_list');
            serviceListElement.innerHTML = ''; // Clear existing services
            for (const [serviceName, status] of Object.entries(data.service_status)) {
                const serviceElement = document.createElement('div');
                serviceElement.className = 'service-status';
                serviceElement.innerHTML = `
                    <div>${serviceName}</div>
                    <span>${status
                        ? '<span class="status-green"><i class="fas fa-check-circle"></i></span>'
                        : '<span class="status-red"><i class="fas fa-times-circle"></i></span>'}</span>
                `;
                serviceListElement.appendChild(serviceElement);
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
                        labels: data.per_cpu_utilization.map(function(_, index) { return 'CPU ' + index; }),
                        datasets: [{
                            label: 'Per CPU Utilization (%)',
                            data: data.per_cpu_utilization,
                            backgroundColor: data.per_cpu_utilization.map(function(value) {
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
                cpuChart.data.datasets[0].backgroundColor = data.per_cpu_utilization.map(function(value) {
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
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

def open_browser():
    """Open the default web browser to the application's page."""
    url = "http://127.0.0.1:8003"
    try:
        webbrowser.open(url, new=2)  # new=2 opens in a new tab, if possible
    except Exception as e:
        print(f"Failed to open browser: {e}")

if __name__ == "__main__":
    import uvicorn
    import threading

    # Start the web server in a separate thread
    def start_server():
        uvicorn.run(app, host="127.0.0.1", port=8003, log_level="info")

    server_thread = threading.Thread(target=start_server)
    server_thread.start()

    # Give the server a moment to start
    asyncio.sleep(1)

    # Open the web browser
    open_browser()

    # Wait for the server thread to finish
    server_thread.join()

