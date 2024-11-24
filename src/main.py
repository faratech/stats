from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import psutil
from datetime import datetime
import aiofiles
import platform
import socket
import os

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
    static_data['logged_in_users'] = len(psutil.users())

# Function to check service status using systemctl
async def get_service_status():
    services = {
        'lsws': 'LiteSpeed Web Server',
        'mysql': 'MySQL (MariaDB)',
        'aiapi': 'AI Apps Service (FastAPI)',
        'elasticsearch': 'Elasticsearch',
        'fastapi': 'FastAPI for XenForo Universal Search'
    }
    service_status = {}
    tasks = []
    for service_name, display_name in services.items():
        tasks.append(check_service_status(service_name, display_name))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            continue  # Handle exceptions if necessary
        display_name, status = result
        service_status[display_name] = status
    return service_status

async def check_service_status(service_name, display_name):
    try:
        status = await run_command_output(f'systemctl is-active {service_name}')
        return (display_name, status.strip() == 'active')
    except Exception:
        return (display_name, False)

async def run_command_output(command):
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
        return stdout.decode() + stderr.decode()
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return ''
    except asyncio.CancelledError:
        process.kill()
        await process.communicate()
        raise

# Function to get network connections
def get_network_connections():
    try:
        connections = psutil.net_connections(kind='inet')
        formatted_connections = []
        for conn in connections:
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
            formatted_connections.append({
                'type': str(conn.type),
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
        disk = psutil.disk_usage('/')
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

        # Load average (for UNIX systems)
        if hasattr(os, 'getloadavg'):
            load_avg = os.getloadavg()
            load_avg_str = f"1 min: {load_avg[0]:.2f}, 5 min: {load_avg[1]:.2f}, 15 min: {load_avg[2]:.2f}"
        else:
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
    except Exception:
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
            previous_net_io = stats['current_net_io']
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()

# Serve the HTML page
@app.get("/", response_class=HTMLResponse)
async def index():
    async with aiofiles.open('index.html', 'r') as f:
        html_content = await f.read()
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)