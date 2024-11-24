# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
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
import win32evtlog
import threading
import logging

app = FastAPI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("exchange_monitoring.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Cache for static data
static_data = {}

# Set up the templates directory
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

# Initialize static data that doesn't change frequently
async def initialize_static_data():
    static_data['cpu_info'] = get_cpu_info()
    static_data['kernel_version'] = platform.release()
    static_data['os_release'] = platform.platform()
    static_data['hostname'] = socket.gethostname()
    static_data['cpu_frequency'] = get_cpu_frequency()
    static_data['logged_in_users'] = get_logged_in_users()
    static_data['is_exchange_server'] = is_exchange_server()

def is_exchange_server():
    """
    Determines if the current server is an Exchange Server by checking
    the status of the Microsoft Exchange Transport Service.
    """
    exchange_service = 'MSExchangeTransport'
    try:
        status = win32serviceutil.QueryServiceStatus(exchange_service)[1]
        is_running = status == win32service.SERVICE_RUNNING
        logger.info(f"Exchange Service '{exchange_service}' running: {is_running}")
        return is_running
    except Exception as e:
        logger.error(f"Error checking Exchange service '{exchange_service}': {e}")
        return False  # Service not found or other error

def get_logged_in_users():
    try:
        users = psutil.users()
        user_count = len(users)
        logger.info(f"Logged-in users count: {user_count}")
        return user_count
    except Exception as e:
        logger.error(f"Error retrieving logged-in users: {e}")
        return 0

# Function to check service status on Windows
async def get_service_status():
    """
    Checks the status of critical Windows services.
    Returns a dictionary with service display names and their running status.
    """
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
        'lmhosts': 'TCP/IP NetBIOS Helper',
        'MSDTC': 'Distributed Transaction Coordinator',
        'NcdAutoSetup': 'Network Connected Devices Auto-Setup',
        'nsi': 'Network Store Interface Service',
        'PeerDistSvc': 'BranchCache',
        'PnrpAutoReg': 'PNRP Machine Name Publication Service',
        'PNRPSvc': 'Peer Name Resolution Protocol',
        'RpcLocator': 'Remote Procedure Call (RPC) Locator',
        'RemoteAccess': 'Routing and Remote Access',
        'Schedule': 'Task Scheduler',
        'SSDPSRV': 'SSDP Discovery',
        'TrkWks': 'Distributed Link Tracking Client',
        'WinHttpAutoProxySvc': 'WinHTTP Web Proxy Auto-Discovery Service',
        'WSearch': 'Windows Search',
    }
    service_status = {}
    for service_name, display_name in services.items():
        try:
            status = win32serviceutil.QueryServiceStatus(service_name)[1]
            service_status[display_name] = (status == win32service.SERVICE_RUNNING)
            logger.debug(f"Service '{display_name}' running: {service_status[display_name]}")
        except Exception as e:
            service_status[display_name] = False
            logger.warning(f"Error querying service '{display_name}': {e}")
    return service_status

def get_exchange_installation_path():
    """
    Determines the installation directory of Microsoft Exchange by querying the MSExchangeTransport service.
    Returns the installation path if found, else None.
    """
    try:
        service_name = 'MSExchangeTransport'
        config = win32serviceutil.QueryServiceConfig(service_name)
        
        # The binary path may contain quotes and command-line arguments
        binary_path = config[3]
        if '"' in binary_path:
            exe_path = binary_path.split('"')[1]
        else:
            exe_path = binary_path.split(' ')[0]
        
        # Assuming the binary is located in the 'Bin' directory under the installation path
        # e.g., 'C:\Program Files\Microsoft\Exchange Server\V15\Bin\MSExchangeTransport.exe'
        bin_dir = os.path.dirname(exe_path)
        install_dir = os.path.dirname(bin_dir)
        
        if os.path.exists(install_dir):
            logger.info(f"Exchange installation directory found: {install_dir}")
            return install_dir
        else:
            logger.error(f"Exchange installation directory does not exist: {install_dir}")
            return None
    except Exception as e:
        logger.error(f"Error finding Exchange installation path: {e}")
        return None

def get_exchange_send_receive_logs(num_lines=10):
    """
    Retrieves the latest send and receive logs from Exchange Transport Logs by dynamically determining the log paths.
    """
    logs = {}
    install_dir = get_exchange_installation_path()
    
    if not install_dir:
        logger.error("Exchange installation path not found. Cannot retrieve send/receive logs.")
        logs['send_log'] = []
        logs['receive_log'] = []
        return logs
    
    send_log_path = os.path.join(install_dir, 'TransportRoles', 'Logs', 'ProtocolLog', 'SmtpSend')
    receive_log_path = os.path.join(install_dir, 'TransportRoles', 'Logs', 'ProtocolLog', 'SmtpReceive')

    # Get the latest log file in the directory
    def get_latest_log(log_dir):
        try:
            if not os.path.exists(log_dir):
                logger.error(f"Log directory does not exist: {log_dir}")
                return None
            files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))]
            if not files:
                logger.warning(f"No log files found in directory: {log_dir}")
                return None
            latest_file = max(files, key=os.path.getmtime)
            logger.debug(f"Latest log file in '{log_dir}': {latest_file}")
            return latest_file
        except Exception as e:
            logger.error(f"Error accessing log directory {log_dir}: {e}")
            return None

    send_log_file = get_latest_log(send_log_path)
    receive_log_file = get_latest_log(receive_log_path)

    def tail(file_path, num_lines):
        try:
            with open(file_path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                end = f.tell()
                buffer = bytearray()
                lines = []
                pointer = end - 1
                while pointer >= 0 and len(lines) < num_lines:
                    f.seek(pointer)
                    new_byte = f.read(1)
                    if new_byte == b'\n':
                        line = buffer.decode('utf-8', errors='replace')[::-1]
                        lines.insert(0, line)
                        buffer = bytearray()
                    else:
                        buffer.extend(new_byte)
                    pointer -= 1
                if buffer:
                    lines.insert(0, buffer.decode('utf-8', errors='replace')[::-1])
                return lines[-num_lines:]
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []

    if send_log_file:
        logs['send_log'] = tail(send_log_file, num_lines)
    else:
        logs['send_log'] = []

    if receive_log_file:
        logs['receive_log'] = tail(receive_log_file, num_lines)
    else:
        logs['receive_log'] = []

    return logs

def get_event_logs(log_type='Application', event_levels=['Critical', 'Error', 'Warning'], num_events=10):
    """
    Retrieves recent event logs based on specified criteria.
    """
    formatted_events = []
    try:
        log_handle = win32evtlog.OpenEventLog(None, log_type)
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        events = []
        while len(events) < num_events:
            records = win32evtlog.ReadEventLog(log_handle, flags, 0)
            if not records:
                break
            for event in records:
                if len(events) >= num_events:
                    break
                event_level = ''
                if event.EventType == win32evtlog.EVENTLOG_ERROR_TYPE:
                    event_level = 'Error'
                elif event.EventType == win32evtlog.EVENTLOG_WARNING_TYPE:
                    event_level = 'Warning'
                elif event.EventType == win32evtlog.EVENTLOG_INFORMATION_TYPE:
                    event_level = 'Information'
                elif event.EventType == win32evtlog.EVENTLOG_AUDIT_FAILURE:
                    event_level = 'Audit Failure'
                elif event.EventType == win32evtlog.EVENTLOG_AUDIT_SUCCESS:
                    event_level = 'Audit Success'
                if event_level in event_levels:
                    events.append(event)
        # Format the events
        for event in events:
            record = {
                'SourceName': event.SourceName,
                'EventID': event.EventID & 0xFFFF,  # Masking to get the actual EventID
                'EventType': event.EventType,
                'TimeGenerated': event.TimeGenerated.Format(),
                'EventCategory': event.EventCategory,
                'StringInserts': event.StringInserts
            }
            formatted_events.append(record)
        logger.info(f"Retrieved {len(formatted_events)} event logs from '{log_type}'")
    except Exception as e:
        logger.error(f"Error reading event logs: {e}")
    finally:
        try:
            win32evtlog.CloseEventLog(log_handle)
        except:
            pass
    return formatted_events

def get_security_logins(num_events=10):
    """
    Retrieves recent security login events.
    """
    formatted_events = []
    try:
        log_handle = win32evtlog.OpenEventLog(None, 'Security')
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        events = []
        while len(events) < num_events:
            records = win32evtlog.ReadEventLog(log_handle, flags, 0)
            if not records:
                break
            for event in records:
                if len(events) >= num_events:
                    break
                if event.EventID & 0xFFFF == 4624:  # Logon event
                    events.append(event)
        # Format the events
        for event in events:
            record = {
                'SourceName': event.SourceName,
                'EventID': event.EventID & 0xFFFF,  # Masking to get the actual EventID
                'TimeGenerated': event.TimeGenerated.Format(),
                'StringInserts': event.StringInserts
            }
            formatted_events.append(record)
        logger.info(f"Retrieved {len(formatted_events)} security login events")
    except Exception as e:
        logger.error(f"Error reading security logs: {e}")
    finally:
        try:
            win32evtlog.CloseEventLog(log_handle)
        except:
            pass
    return formatted_events

def get_exchange_service_status():
    """
    Retrieves the status of Exchange-specific services.
    """
    exchange_services = {
        'MSExchangeADTopology': 'Microsoft Exchange Active Directory Topology',
        'MSExchangeTransport': 'Microsoft Exchange Transport',
        'MSExchangeIS': 'Microsoft Exchange Information Store',
        'MSExchangeMailboxAssistants': 'Microsoft Exchange Mailbox Assistants',
        'MSExchangeMailboxReplication': 'Microsoft Exchange Mailbox Replication',
        'MSExchangeIMAP4': 'Microsoft Exchange IMAP4',
        'MSExchangePOP3': 'Microsoft Exchange POP3',
        'MSExchangeServiceHost': 'Microsoft Exchange Service Host',
        'MSExchangeUM': 'Microsoft Exchange Unified Messaging',
        'MSExchangeThrottling': 'Microsoft Exchange Throttling',
        'MSExchangeAB': 'Microsoft Exchange Address Book',
        'MSExchangeRPC': 'Microsoft Exchange RPC Client Access',
        'MSExchangeDelivery': 'Microsoft Exchange Mailbox Transport Delivery',
        'MSExchangeSubmission': 'Microsoft Exchange Mailbox Transport Submission',
        'MSExchangeHM': 'Microsoft Exchange Health Manager',
        'MSExchangeFrontendTransport': 'Microsoft Exchange Frontend Transport',
        'MSExchangeEdgeSync': 'Microsoft Exchange EdgeSync',
    }
    service_status = {}
    for service_name, display_name in exchange_services.items():
        try:
            status = win32serviceutil.QueryServiceStatus(service_name)[1]
            service_status[display_name] = (status == win32service.SERVICE_RUNNING)
            logger.debug(f"Exchange Service '{display_name}' running: {service_status[display_name]}")
        except Exception as e:
            service_status[display_name] = False
            logger.warning(f"Error querying Exchange service '{display_name}': {e}")
    return service_status

# Function to get network connections
def get_network_connections():
    """
    Retrieves current network connections.
    """
    formatted_connections = []
    try:
        connections = psutil.net_connections(kind='inet')
        for conn in connections:
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
            formatted_connections.append({
                'type': 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP',
                'laddr': laddr,
                'raddr': raddr,
                'status': conn.status
            })
        logger.info(f"Retrieved {len(formatted_connections)} network connections")
    except Exception as e:
        logger.error(f"Error retrieving network connections: {e}")
    return formatted_connections

# Function to get CPU info
def get_cpu_info():
    try:
        cpu_info = platform.processor()
        logger.debug(f"CPU Info: {cpu_info}")
        return cpu_info
    except Exception as e:
        logger.error(f"Error retrieving CPU info: {e}")
        return "N/A"

# Function to get CPU frequency
def get_cpu_frequency():
    try:
        cpu_freq = psutil.cpu_freq()
        freq = f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A"
        logger.debug(f"CPU Frequency: {freq}")
        return freq
    except Exception as e:
        logger.error(f"Error retrieving CPU frequency: {e}")
        return "N/A"

# Function to collect stats
async def collect_stats(previous_net_io):
    stats = {}
    try:
        # Get service statuses
        service_status = await get_service_status()
        stats['service_status'] = service_status
    except Exception as e:
        logger.error(f"Failed to get service statuses: {e}")
        stats['service_status'] = {}

    # Determine if it's an Exchange server
    is_exchange = static_data.get('is_exchange_server', False)
    stats['is_exchange_server'] = is_exchange

    if is_exchange:
        try:
            # Get Exchange-specific service statuses
            exchange_services_status = get_exchange_service_status()
            stats['exchange_services_status'] = exchange_services_status
        except Exception as e:
            logger.error(f"Failed to get Exchange service statuses: {e}")
            stats['exchange_services_status'] = {}

    try:
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

        # Collect Exchange-specific data if applicable
        if is_exchange:
            try:
                exchange_logs = get_exchange_send_receive_logs(num_lines=10)
                event_logs = get_event_logs(log_type='Application', event_levels=['Critical', 'Error', 'Warning'], num_events=10)
                security_logins = get_security_logins(num_events=10)
                stats['exchange_logs'] = exchange_logs
                stats['event_logs'] = event_logs
                stats['security_logins'] = security_logins
            except Exception as e:
                logger.error(f"Failed to collect Exchange-specific data: {e}")
                stats['exchange_logs'] = []
                stats['event_logs'] = []
                stats['security_logins'] = []

        # Package all stats into a dictionary
        stats.update({
            'cpu_utilization': cpu_utilization,
            'per_cpu_utilization': per_cpu_utilization,
            'memory_utilization': memory_utilization,
            'swap_utilization': swap_utilization,
            'disk_utilization': disk_utilization,
            'network_utilization': network_utilization,
            'current_time': current_time,
            'uptime_output': uptime_output,
            'process_list': processes_sorted,  # Send as list of dicts
            'network_info': network_info,
            'network_connections': connections_str,
            'disk_read': disk_read,
            'disk_write': disk_write,
            'load_avg': load_avg_str,
            'current_net_io': net_io,  # Include for next iteration
        })

    except Exception as e:
        logger.error(f"Error collecting utilization and system stats: {e}")
        # Set default or empty values
        stats.update({
            'cpu_utilization': 0,
            'per_cpu_utilization': [],
            'memory_utilization': 0,
            'swap_utilization': 0,
            'disk_utilization': 0,
            'network_utilization': {'upload': 0, 'download': 0},
            'current_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'uptime_output': "0h 0m 0s",
            'process_list': [],
            'network_info': "Upload: 0.00 KB/s, Download: 0.00 KB/s",
            'network_connections': "",
            'disk_read': "0 MB",
            'disk_write': "0 MB",
            'load_avg': "N/A",
            'current_net_io': None,
        })
        if is_exchange:
            stats.update({
                'exchange_logs': [],
                'event_logs': [],
                'security_logins': [],
            })

    return stats

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
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()

# Serve the HTML page
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        await initialize_static_data()  # Ensure static data is initialized
        page_title = "System Monitor"
        if static_data.get('is_exchange_server'):
            page_title = "Exchange Monitoring System"
        return templates.TemplateResponse("index.html", {
            "request": request,
            "page_title": page_title,
            "is_exchange_server": static_data.get('is_exchange_server')
        })
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        return HTMLResponse("<h1>Internal Server Error</h1>", status_code=500)

def open_browser():
    """Open the default web browser to the application's page."""
    url = "http://127.0.0.1:8003"
    try:
        webbrowser.open(url, new=2)  # new=2 opens in a new tab, if possible
        logger.info(f"Opened web browser to {url}")
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")

if __name__ == "__main__":
    import uvicorn

    # Start the web server in a separate thread
    def start_server():
        uvicorn.run(app, host="127.0.0.1", port=8003, log_level="info")

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Give the server a moment to start
    asyncio.run(asyncio.sleep(1))

    # Open the web browser
    open_browser()

    # Keep the main thread alive to keep the server running
    try:
        while True:
            asyncio.run(asyncio.sleep(3600))  # Sleep for 1 hour intervals
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
