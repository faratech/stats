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

app = FastAPI()

# Cache for static data
static_data = {}

templates = Jinja2Templates(directory="templates")

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
        return status == win32service.SERVICE_RUNNING
    except Exception:
        return False  # Service not found or other error

def get_logged_in_users():
    try:
        users = psutil.users()
        return len(users)
    except Exception:
        return 0

# Function to check service status on Windows
async def get_service_status():
    """
    Checks the status of critical Windows services.
    Returns a dictionary with service display names and their running status.
    """
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
        except Exception:
            service_status[display_name] = False
    return service_status

def get_exchange_send_receive_logs(num_lines=10):
    """
    Retrieves the latest send and receive logs from Exchange Transport Logs.
    """
    logs = {}
    send_log_path = r'C:\Program Files\Microsoft\Exchange Server\V15\TransportRoles\Logs\ProtocolLog\SmtpSend'
    receive_log_path = r'C:\Program Files\Microsoft\Exchange Server\V15\TransportRoles\Logs\ProtocolLog\SmtpReceive'

    # Get the latest log file in the directory
    def get_latest_log(log_dir):
        try:
            files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))]
            if not files:
                return None
            latest_file = max(files, key=os.path.getmtime)
            return latest_file
        except Exception as e:
            print(f"Error accessing log directory {log_dir}: {e}")
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
                        lines.insert(0, buffer.decode('utf-8', errors='replace')[::-1])
                        buffer = bytearray()
                    else:
                        buffer.extend(new_byte)
                    pointer -= 1
                if buffer:
                    lines.insert(0, buffer.decode('utf-8', errors='replace')[::-1])
                return lines[-num_lines:]
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
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
    log_handle = win32evtlog.OpenEventLog(None, log_type)
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    events = []
    try:
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
    except Exception as e:
        print(f"Error reading event logs: {e}")
    finally:
        win32evtlog.CloseEventLog(log_handle)
    # Format the events
    formatted_events = []
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
    return formatted_events

def get_security_logins(num_events=10):
    """
    Retrieves recent security login events.
    """
    log_handle = win32evtlog.OpenEventLog(None, 'Security')
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    events = []
    try:
        while len(events) < num_events:
            records = win32evtlog.ReadEventLog(log_handle, flags, 0)
            if not records:
                break
            for event in records:
                if len(events) >= num_events:
                    break
                if event.EventID & 0xFFFF == 4624:  # Logon event
                    events.append(event)
    except Exception as e:
        print(f"Error reading security logs: {e}")
    finally:
        win32evtlog.CloseEventLog(log_handle)
    # Format the events
    formatted_events = []
    for event in events:
        record = {
            'SourceName': event.SourceName,
            'EventID': event.EventID & 0xFFFF,  # Masking to get the actual EventID
            'TimeGenerated': event.TimeGenerated.Format(),
            'StringInserts': event.StringInserts
        }
        formatted_events.append(record)
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
        except Exception:
            service_status[display_name] = False
    return service_status

# Function to get network connections
def get_network_connections():
    """
    Retrieves current network connections.
    """
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

        if static_data.get('is_exchange_server'):
            # Collect Exchange-specific data
            exchange_services_status = get_exchange_service_status()
            exchange_logs = get_exchange_send_receive_logs(num_lines=10)
            event_logs = get_event_logs(log_type='Application', event_levels=['Critical', 'Error', 'Warning'], num_events=10)
            security_logins = get_security_logins(num_events=10)
            # Add to stats
            stats['exchange_services_status'] = exchange_services_status
            stats['exchange_logs'] = exchange_logs
            stats['event_logs'] = event_logs
            stats['security_logins'] = security_logins

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
async def index(request: Request):
    await initialize_static_data()  # Ensure static data is initialized
    page_title = "System Monitor"
    if static_data.get('is_exchange_server'):
        page_title = "Exchange Monitoring System"
    return templates.TemplateResponse("index.html", {"request": request, "page_title": page_title, "is_exchange_server": static_data.get('is_exchange_server')})

def open_browser():
    """Open the default web browser to the application's page."""
    url = "http://127.0.0.1:8003"
    try:
        webbrowser.open(url, new=2)  # new=2 opens in a new tab, if possible
    except Exception as e:
        print(f"Failed to open browser: {e}")

if __name__ == "__main__":
    import uvicorn

    # Start the web server in a separate thread
    def start_server():
        uvicorn.run(app, host="127.0.0.1", port=8003, log_level="info")

    server_thread = threading.Thread(target=start_server)
    server_thread.start()

    # Give the server a moment to start
    asyncio.run(asyncio.sleep(1))

    # Open the web browser
    open_browser()

    # Wait for the server thread to finish
    server_thread.join()
