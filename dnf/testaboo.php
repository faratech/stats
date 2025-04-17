<?php
/**
 * Enhanced DNF Package Timeline Visualizer
 *
 * A polished web application for visualizing package update history from DNF.
 * Features dark/light mode, extended time ranges, and interactive visualizations.
 * This version uses the DNF history database directly on disk.
 *
 * @version 1.2.0
 * @author DNF Visualizer Team
 */

// Start session for potential user preferences storage
session_start();

// For API requests, disable error display and set content type
if (isset($_GET['api'])) {
    ini_set('display_errors', 0);
    error_reporting(0);
    header('Content-Type: application/json');
} else {
    // For regular page views, enable error reporting to debug potential issues
    ini_set('display_errors', 1);
    error_reporting(E_ALL);
}

// Set execution time limit to handle large databases
set_time_limit(300); // 5 minutes

// Configuration - path to DNF history database
$db_path = "/web/stats/dnf/history.sqlite";

// Global variable to store the database connection
$db = null;

// Connect to the database directly
try {
    if (!file_exists($db_path)) {
        throw new Exception("Database file not found: $db_path");
    }
    if (!is_readable($db_path)) {
        throw new Exception("Database file is not readable: $db_path");
    }
    
    error_log("DNF Visualizer: Attempting to open database: $db_path");
    $db = new SQLite3($db_path, SQLITE3_OPEN_READWRITE);
    
    // Verify database accessibility with a lightweight read query
    $test_query = $db->query('SELECT 1 FROM sqlite_master WHERE type="table" LIMIT 1');
    if (!$test_query || !$test_query->fetchArray(SQLITE3_NUM)) {
        throw new Exception("Failed to read database schema: " . $db->lastErrorMsg());
    }
    
    error_log("DNF Visualizer: Database opened successfully");
    
    // Optimize database performance
    $db->exec('PRAGMA synchronous = OFF');
    $db->exec('PRAGMA journal_mode = WAL');
    $db->exec('PRAGMA cache_size = 10000');
} catch (Exception $e) {
    error_log("Database connection error: " . $e->getMessage());
    if ($db) {
        $db->close();
    }
    if (isset($_GET['api'])) {
        http_response_code(500);
        echo json_encode(['error' => 'Exception connecting to database: ' . $e->getMessage(), 'db_path' => $db_path]);
        exit;
    } else {
        die("Error: Unable to connect to database: " . htmlspecialchars($e->getMessage()));
    }
}

// Handle API requests
if (isset($_GET['api'])) {
    $api_action = $_GET['api'];
    
    if ($api_action === 'data') {
        // Get data from database
        $days_back = isset($_GET['days']) ? intval($_GET['days']) : null;
        $start_ts = isset($_GET['start']) ? intval($_GET['start']) : null;
        $end_ts = isset($_GET['end']) ? intval($_GET['end']) : null;
        
        try {
            $data = process_history_data($db, $days_back, $start_ts, $end_ts);
            echo json_encode($data);
        } catch (Exception $e) {
            echo json_encode(['error' => 'Error processing history data: ' . $e->getMessage()]);
        }
        exit;
    }
    
    if ($api_action === 'timerange') {
        // Get the earliest and latest dates from the database
        try {
            $range = get_time_range($db);
            echo json_encode($range);
        } catch (Exception $e) {
            echo json_encode(['error' => 'Error getting time range: ' . $e->getMessage()]);
        }
        exit;
    }
}

/**
 * Get the time range of data in the database
 *
 * @param SQLite3 $db Database connection
 * @return array Time range data including earliest and latest dates
 * @throws Exception If there's an error getting the time range
 */
function get_time_range($db) {
    if (!$db) {
        throw new Exception("Database connection not available");
    }
    
    try {
        // Query for earliest and latest timestamps
        $query = "
        SELECT
            MIN(dt_begin) AS earliest,
            MAX(dt_begin) AS latest
        FROM trans
        ";
        
        $result = $db->query($query);
        if (!$result) {
            throw new Exception("Query failed: " . $db->lastErrorMsg());
        }
        
        $row = $result->fetchArray(SQLITE3_ASSOC);
        
        if (!$row || $row['earliest'] === null || $row['latest'] === null) {
            throw new Exception("No time range data found");
        }
        
        $earliest = $row['earliest'];
        $latest = $row['latest'];
        $range_days = ceil(($latest - $earliest) / (24 * 60 * 60));
        
        return [
            'earliest' => $earliest,
            'latest' => $latest,
            'earliest_date' => human_date($earliest),
            'latest_date' => human_date($latest),
            'range_days' => $range_days
        ];
    } catch (Exception $e) {
        throw new Exception("Error getting time range: " . $e->getMessage());
    }
}

/**
 * Query the DNF history from the database
 *
 * @param SQLite3 $db Database connection
 * @param int|null $start_ts Start timestamp for filtering
 * @param int|null $end_ts End timestamp for filtering
 * @return array Results array with package data
 * @throws Exception If there's an error querying the database
 */
function query_full_history($db, $start_ts = null, $end_ts = null) {
    if (!$db) {
        throw new Exception("Database connection not available");
    }
    
    try {
        // Build query with conditions
        $where_conditions = [];
        $params = [];
        
        if ($start_ts !== null) {
            $where_conditions[] = "trans.dt_begin >= :start_ts";
            $params[':start_ts'] = intval($start_ts);
        }
        if ($end_ts !== null) {
            $where_conditions[] = "trans.dt_begin <= :end_ts";
            $params[':end_ts'] = intval($end_ts);
        }
        
        $where_clause = "";
        if (!empty($where_conditions)) {
            $where_clause = "WHERE " . implode(" AND ", $where_conditions);
        }
        
        // Optimized query with more efficient joins and limiting fields
        $query = "
        SELECT
            rpm.name,
            trans.dt_begin,
            trans_item.state
        FROM trans
        JOIN trans_item ON trans_item.trans_id = trans.id
        JOIN rpm ON trans_item.item_id = rpm.item_id
        $where_clause
        ORDER BY rpm.name, trans.dt_begin
        ";
        
        // Prepare and execute the query
        $stmt = $db->prepare($query);
        
        if (!$stmt) {
            throw new Exception("Failed to prepare query: " . $db->lastErrorMsg());
        }
        
        // Bind parameters if any
        foreach ($params as $param => $value) {
            $stmt->bindValue($param, $value);
        }
        
        // Execute the query
        $result = $stmt->execute();
        
        if (!$result) {
            throw new Exception("Query execution failed: " . $db->lastErrorMsg());
        }
        
        // Fetch all rows efficiently
        $rows = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $rows[] = $row;
        }
        
        return $rows;
    } catch (Exception $e) {
        throw new Exception("Error querying history: " . $e->getMessage());
    }
}

/**
 * Convert timestamp to human-readable date
 *
 * @param int $timestamp Unix timestamp
 * @return string Formatted date string
 */
function human_date($timestamp) {
    try {
        $dt = new DateTime();
        $dt->setTimestamp($timestamp);
        $dt->setTimezone(new DateTimeZone('America/New_York'));
        
        return $dt->format('Y-m-d h:i A');
    } catch (Exception $e) {
        error_log("Date conversion error: " . $e->getMessage());
        return "Invalid date";
    }
}

/**
 * Process history data directly from the database
 *
 * @param SQLite3 $db Database connection
 * @param int|null $days_back Number of days to look back
 * @param int|null $start_ts Start timestamp for filtering
 * @param int|null $end_ts End timestamp for filtering
 * @return array Processed timeline data
 * @throws Exception If there's an error processing the data
 */
function process_history_data($db, $days_back = null, $start_ts = null, $end_ts = null) {
    if (!$db) {
        throw new Exception("Database connection not available");
    }
    
    try {
        // Calculate timestamps for filtering
        $end_ts = $end_ts ?? time();
        $start_ts = $start_ts ?? ($days_back !== null ? ($end_ts - ($days_back * 24 * 60 * 60)) : null);
        
        // Query database
        $rows = query_full_history($db, $start_ts, $end_ts);
        
        if (empty($rows)) {
            return ['packages' => [], 'message' => 'No package history found in the specified time range'];
        }
        
        // Process data with optimized approach
        $pkg_events = [];
        $state_map = [
            1 => "Install",
            2 => "Update",
            3 => "Remove",
            4 => "Downgrade",
            5 => "Reinstall"
        ];
        
        foreach ($rows as $row) {
            $name = $row['name'];
            $dt_begin = $row['dt_begin'];
            $state = $row['state'];
            
            $operation = isset($state_map[$state]) ? $state_map[$state] : "Unknown";
            
            if (!isset($pkg_events[$name])) {
                $pkg_events[$name] = [];
            }
            
            $pkg_events[$name][] = [
                "timestamp" => $dt_begin,
                "human_date" => human_date($dt_begin),
                "operation" => $operation
            ];
        }
        
        // Prepare timeline data with improved sorting
        $timeline_data = [];
        foreach ($pkg_events as $pkg => $events) {
            // Skip packages with no events
            if (empty($events)) {
                continue;
            }
            
            // Sort events by timestamp
            usort($events, function($a, $b) {
                return $a['timestamp'] - $b['timestamp'];
            });
            
            $timeline_data[] = [
                "package" => $pkg,
                "events" => $events,
                "total_events" => count($events),
                "first_event" => $events[0],
                "last_event" => end($events)
            ];
        }
        
        // Sort packages by most recently updated
        usort($timeline_data, function($a, $b) {
            return $b['last_event']['timestamp'] - $a['last_event']['timestamp'];
        });
        
        return $timeline_data;
    } catch (Exception $e) {
        throw new Exception("Error processing history data: " . $e->getMessage());
    }
}
?>

<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Enhanced Package Timeline Visualizer for DNF package management history">
    <title>Enhanced Package Timeline</title>
    
    <!-- Favicon -->
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📊</text></svg>">
    
    <!-- External CSS libraries -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="loading" class="loading" style="display: none;">
        <div class="loading-spinner"></div>
    </div>
    
    <header>
        <div class="header-content">
            <h1><i class="fas fa-box-open"></i> Package Update Timeline</h1>
            <div class="controls-container">
                <span id="timerange-info"></span>
                <button id="header-theme-toggle" class="theme-toggle" aria-label="Toggle dark/light mode">
                    <i class="fas fa-moon"></i>
                </button>
            </div>
        </div>
        
        <div class="filter-controls">
            <div class="filter-group">
                <label for="days-filter">Show updates from the last:</label>
                <select id="days-filter" aria-label="Filter by time range">
                    <option value="all">All time</option>
                    <option value="7">7 days</option>
                    <option value="30" selected>30 days</option>
                    <option value="90">90 days</option>
                    <option value="180">180 days</option>
                    <option value="365">1 year</option>
                    <option value="730">2 years</option>
                    <option value="1095">3 years</option>
                    <option value="1825">5 years</option>
                    <option value="custom">Custom range...</option>
                </select>
            </div>
            
            <div id="custom-date-range" class="filter-group" style="display: none;">
                <label for="start-date">From:</label>
                <input type="date" id="start-date" aria-label="Start date">
                <label for="end-date">To:</label>
                <input type="date" id="end-date" aria-label="End date">
                <button id="apply-custom-range" class="apply-dates-btn">Apply</button>
            </div>
            
            <div class="filter-group search-group">
                <label for="search-filter">Filter packages:</label>
                <input type="text" id="search-filter" placeholder="Type to filter packages..." aria-label="Search packages">
            </div>
        </div>
    </header>
    
    <main>
        <section class="dashboard">
            <div class="stats-container">
                <div class="stat-card">
                    <h3>Total Packages</h3>
                    <div id="total-packages" class="stat-value">0</div>
                </div>
                <div class="stat-card">
                    <h3>Recent Updates</h3>
                    <div id="recent-updates" class="stat-value">0</div>
                </div>
                <div class="stat-card">
                    <h3>Most Active Package</h3>
                    <div id="most-active" class="stat-value">-</div>
                </div>
            </div>
            
            <h2>Operations Summary</h2>
            <div id="operation-summary" class="operation-summary"></div>
            
            <div class="chart-container">
                <h2>Activity Over Time</h2>
                <canvas id="activity-chart"></canvas>
            </div>
        </section>
        
        <section class="timeline-section">
            <h2>Package Timeline
                <div class="timeline-controls">
                    <button id="timeline-zoom-in" class="timeline-control-btn" title="Zoom In" aria-label="Zoom in timeline">
                        <i class="fas fa-search-plus"></i>
                    </button>
                    <button id="timeline-zoom-out" class="timeline-control-btn" title="Zoom Out" aria-label="Zoom out timeline">
                        <i class="fas fa-search-minus"></i>
                    </button>
                    <button id="timeline-reset-zoom" class="timeline-control-btn" title="Reset Zoom" aria-label="Reset timeline zoom">
                        <i class="fas fa-expand"></i>
                    </button>
                </div>
            </h2>
            <div id="timeline"></div>
        </section>
        
        <section class="data-table-section">
            <h2>Package Details</h2>
            <table id="package-table" class="display">
                <thead>
                    <tr>
                        <th>Package</th>
                        <th>Last Updated</th>
                        <th>First Installed</th>
                        <th>Total Events</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="package-table-body">
                    <!-- Data will be populated here -->
                </tbody>
            </table>
        </section>
        
        <section class="package-detail" id="package-detail-section" style="display: none;">
            <h2>Package Details: <span id="detail-package-name"></span>
                <div class="timeline-controls">
                    <button id="detail-zoom-in" class="timeline-control-btn" title="Zoom In" aria-label="Zoom in detail timeline">
                        <i class="fas fa-search-plus"></i>
                    </button>
                    <button id="detail-zoom-out" class="timeline-control-btn" title="Zoom Out" aria-label="Zoom out detail timeline">
                        <i class="fas fa-search-minus"></i>
                    </button>
                    <button id="detail-reset-zoom" class="timeline-control-btn" title="Reset Zoom" aria-label="Reset detail timeline zoom">
                        <i class="fas fa-expand"></i>
                    </button>
                </div>
            </h2>
            <button id="back-to-list" aria-label="Back to package list"><i class="fas fa-arrow-left"></i> Back to Package List</button>
            
            <div class="detail-info-grid">
                <div class="detail-timeline-container">
                    <h3>Event Timeline</h3>
                    <div class="detail-timeline" id="detail-timeline"></div>
                </div>
                
                <div class="detail-chart-container">
                    <h3>Operation Distribution</h3>
                    <div id="operation-chart-container">
                        <canvas id="operation-breakdown-chart"></canvas>
                    </div>
                </div>
            </div>
            
            <h3>Event History</h3>
            <table id="event-table" class="display">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Operation</th>
                    </tr>
                </thead>
                <tbody id="event-table-body">
                    <!-- Data will be populated here -->
                </tbody>
            </table>
        </section>
    </main>
    
    <footer>
        <p>Enhanced Package Timeline Visualizer - Generated on <span id="generation-date"></span></p>
        <p><span id="data-source-info">Using package data from the DNF history database</span></p>
        <div class="footer-controls">
            <button id="toggle-theme" class="theme-toggle" aria-label="Toggle dark/light mode">
                <i class="fas fa-moon"></i> Switch to Dark Mode
            </button>
        </div>
    </footer>
    
    <!-- External JS libraries -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.js"></script>
    <script src="script.js?ver=now"></script>
</body>
</html>
