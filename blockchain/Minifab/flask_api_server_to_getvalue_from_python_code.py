#!/usr/bin/env python3

"""
Flask API Server for IoT Smart Parking System
Serves real data from unified_iot_blockchain.py to the web dashboard
"""

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import threading
import time
import json
import os
from datetime import datetime, timedelta
import logging
from dataclasses import asdict

# Import your existing IoT classes
from unified_iot_blockchain import IoTNetworkManager, BlockchainConnector

app = Flask(__name__)
CORS(app)  # Enable CORS for web dashboard

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IoTDataServer:
    def __init__(self):
        self.network_manager = None
        self.current_data = {
            'system_overview': {
                'total_slots': 0,
                'available_slots': 0,
                'occupied_slots': 0,
                'occupancy_rate': 0,
                'active_sensors': 0,
                'network_health': 0
            },
            'parking_slots': {},
            'environmental': {
                'temperature': 25,
                'humidity': 50,
                'pressure': 1013.25,
                'timestamp': datetime.now().isoformat()
            },
            'battery_status': {},
            'recent_activity': [],
            'blockchain_stats': {
                'total_transactions': 0,
                'successful_updates': 0,
                'avg_response_time': 0,
                'success_rate': 0
            }
        }
        self.is_running = False
        
    def initialize_network(self, num_nodes=12):

        try:
            self.network_manager = IoTNetworkManager()
            success = self.network_manager.initialize_network(num_nodes)
            if success:
                logger.info(f" IoT network initialized with {num_nodes} nodes")
                return True
            else:
                logger.error("Failed to initialize IoT network")
                return False
        except Exception as e:
            logger.error(f" Network initialization error: {str(e)}")
            return False
    
    def start_data_collection(self):

        if not self.network_manager:
            logger.error(" Network manager not initialized")
            return False
            
        self.is_running = True
        

        collection_thread = threading.Thread(target=self._collect_data_loop, daemon=True)
        collection_thread.start()
        
        logger.info("Started real-time data collection")
        return True
    
    def _collect_data_loop(self):

        while self.is_running:
            try:
                # Run network cycle and collect data
                cycle_stats = self.network_manager.run_network_cycle()
                
                # Update system overview
                self._update_system_overview(cycle_stats)
                
                # Update parking slots data
                self._update_parking_slots()
                
                # Update environmental data
                self._update_environmental_data()
                
                # Update battery status
                self._update_battery_status()
                
                # Update blockchain stats
                self._update_blockchain_stats()
                
                # Add recent activity
                self._add_recent_activity(cycle_stats)
                
                # Sleep for next cycle
                time.sleep(10)  # 10 seconds per cycle
                
            except Exception as e:
                logger.error(f" Data collection error: {str(e)}")
                time.sleep(5)
    
    def _update_system_overview(self, cycle_stats):

        total_nodes = len(self.network_manager.nodes)
        active_nodes = cycle_stats['active_nodes']
        occupied_slots = cycle_stats['vehicle_detections']
        
        self.current_data['system_overview'] = {
            'total_slots': total_nodes,
            'available_slots': active_nodes - occupied_slots,
            'occupied_slots': occupied_slots,
            'occupancy_rate': round((occupied_slots / max(1, active_nodes)) * 100, 1),
            'active_sensors': active_nodes,
            'network_health': round((active_nodes / max(1, total_nodes)) * 100, 1),
            'packets_per_min': cycle_stats['successful_transmissions'] * 6,  # Estimate
            'success_rate': round((cycle_stats['successful_transmissions'] / 
                                 max(1, cycle_stats['successful_transmissions'] + 
                                     cycle_stats['failed_transmissions'])) * 100, 1)
        }
    
    def _update_parking_slots(self):

        slots_data = {}
        
        for i, node in enumerate(self.network_manager.nodes, 1):
            slot_id = f"slot-{i}"
            battery_status = node.power.get_battery_status()
            
            slots_data[slot_id] = {
                'id': i,
                'node_id': node.node_id,
                'location': node.location,
                'occupied': node.vehicle_present,
                'online': node.is_online,
                'battery_level': battery_status['charge_percentage'],
                'confidence': 0.95 if node.is_online else 0.0,
                'last_update': datetime.now().isoformat()
            }
        
        self.current_data['parking_slots'] = slots_data
    
    def _update_environmental_data(self):

        if self.network_manager.nodes:
            # Get environmental data from first active node
            for node in self.network_manager.nodes:
                if node.is_online:
                    env_data = node.environmental.read_environment()
                    self.current_data['environmental'] = env_data
                    break
    
    def _update_battery_status(self):

        battery_data = {}
        
        for node in self.network_manager.nodes:
            battery_status = node.power.get_battery_status()
            battery_data[node.node_id] = {
                'charge_percentage': battery_status['charge_percentage'],
                'status': battery_status['status'],
                'solar_panel': battery_status['solar_panel'],
                'estimated_runtime': battery_status['estimated_runtime_hours']
            }
        
        self.current_data['battery_status'] = battery_data
    
    def _update_blockchain_stats(self):

        if self.network_manager.blockchain:
            stats = self.network_manager.blockchain.get_stats()
            self.current_data['blockchain_stats'] = stats
    
    def _add_recent_activity(self, cycle_stats):

        current_time = datetime.now()
        

        if cycle_stats['traffic_events'] > 0:
            activity = {
                'timestamp': current_time.isoformat(),
                'type': 'traffic',
                'message': f"{cycle_stats['traffic_events']} vehicle movement(s) detected",
                'details': f"Blockchain updates: {cycle_stats['blockchain_updates']}"
            }
            self.current_data['recent_activity'].insert(0, activity)
        

        if cycle_stats['low_battery_nodes'] > 0:
            activity = {
                'timestamp': current_time.isoformat(),
                'type': 'warning',
                'message': f"{cycle_stats['low_battery_nodes']} sensor(s) have low battery",
                'details': "Consider maintenance"
            }
            self.current_data['recent_activity'].insert(0, activity)
        

        self.current_data['recent_activity'] = self.current_data['recent_activity'][:20]

# Global data server instance
data_server = IoTDataServer()

@app.route('/')
def dashboard():

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>IoT Dashboard - Redirecting...</title>
        <meta http-equiv="refresh" content="0;url=/static/dashboard.html">
    </head>
    <body>
        <h1>Redirecting to IoT Dashboard...</h1>
        <p>If you are not redirected automatically, <a href="/static/dashboard.html">click here</a>.</p>
        <p>Make sure your dashboard.html is in the static folder or access the API endpoints directly:</p>
        <ul>
            <li><a href="/api/system-overview">/api/system-overview</a></li>
            <li><a href="/api/parking-slots">/api/parking-slots</a></li>
            <li><a href="/api/environmental">/api/environmental</a></li>
            <li><a href="/api/battery-status">/api/battery-status</a></li>
            <li><a href="/api/recent-activity">/api/recent-activity</a></li>
            <li><a href="/api/blockchain-stats">/api/blockchain-stats</a></li>
        </ul>
    </body>
    </html>
    """)

@app.route('/api/system-overview')
def get_system_overview():
    """Get system overview data"""
    return jsonify({
        'status': 'success',
        'data': data_server.current_data['system_overview']
    })

@app.route('/api/parking-slots')
def get_parking_slots():
    """Get parking slots data"""
    return jsonify({
        'status': 'success',
        'data': data_server.current_data['parking_slots']
    })

@app.route('/api/environmental')
def get_environmental():
    """Get environmental sensor data"""
    return jsonify({
        'status': 'success',
        'data': data_server.current_data['environmental']
    })

@app.route('/api/battery-status')
def get_battery_status():
    """Get battery status for all sensors"""
    return jsonify({
        'status': 'success',
        'data': data_server.current_data['battery_status']
    })

@app.route('/api/recent-activity')
def get_recent_activity():
    """Get recent activity log"""
    return jsonify({
        'status': 'success',
        'data': data_server.current_data['recent_activity']
    })

@app.route('/api/blockchain-stats')
def get_blockchain_stats():
    """Get blockchain statistics"""
    return jsonify({
        'status': 'success',
        'data': data_server.current_data['blockchain_stats']
    })

@app.route('/api/all-data')
def get_all_data():

    return jsonify({
        'status': 'success',
        'data': data_server.current_data,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/status')
def get_status():

    return jsonify({
        'status': 'success',
        'server_running': True,
        'data_collection_active': data_server.is_running,
        'network_initialized': data_server.network_manager is not None,
        'total_nodes': len(data_server.network_manager.nodes) if data_server.network_manager else 0,
        'timestamp': datetime.now().isoformat()
    })

def initialize_and_start():

    print(" Initializing IoT Data Server...")
    
    # Initialize network
    if data_server.initialize_network(12):  # 12 IoT nodes
        print(" IoT network initialized successfully")
        
        # Start data collection
        if data_server.start_data_collection():
            print(" Data collection started")
            print(" Flask API server ready to serve real IoT data")
            print("Dashboard can now access real-time data at:")
            print("   - http://localhost:5000/api/all-data")
            print("   - http://localhost:5000/api/system-overview")
            print("   - http://localhost:5000/api/parking-slots")
            return True
        else:
            print("Failed to start data collection")
            return False
    else:
        print("Failed to initialize IoT network")
        return False

if __name__ == '__main__':
    try:
        # Initialize everything
        if initialize_and_start():
            print("\n" + "="*60)
            print(" IoT Smart Parking API Server Starting...")
            print(" Real-time data from blockchain integration")
            print(" Connect your dashboard to: http://localhost:5000")
            print("="*60)
            
            # Start Flask server
            app.run(
                host='0.0.0.0',
                port=5000,
                debug=False,  
                threaded=True
            )
        else:
            print(" Failed to initialize server")
            
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        data_server.is_running = False
    except Exception as e:
        print(f" Server error: {str(e)}")
        data_server.is_running = False
