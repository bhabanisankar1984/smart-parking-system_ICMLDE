import subprocess
import json
import time
import random
import threading
from datetime import datetime, timedelta
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional
import queue
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('iot_parking.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class IoTSensor:
    sensor_id: str
    slot_id: str
    location: str
    battery_level: float
    last_reading: datetime
    status: str  # 'active', 'low_battery', 'offline'
    occupied: bool
    confidence: float  # Sensor reading confidence (0-1)

@dataclass
class ParkingEvent:
    sensor_id: str
    slot_id: str
    location: str
    occupied: bool
    timestamp: datetime
    confidence: float
    event_type: str  # 'arrival', 'departure', 'heartbeat'

class IoTBlockchainConnector:
    def __init__(self, minifab_path="./"):
        self.minifab_path = minifab_path
        self.chaincode_name = "parking"
        self.minifab_cmd = self.detect_minifab_command()
        self.transaction_queue = queue.Queue()
        self.is_running = False
        
    def detect_minifab_command(self):

        possible_commands = [
            "./minifab",
            "minifab", 
            "./network.sh",
            "bash network.sh"
        ]
        
        for cmd in possible_commands:
            if cmd == "./minifab" and os.path.exists("minifab"):
                return ["./minifab"]
            elif cmd == "minifab":
                try:
                    subprocess.run(["which", "minifab"], capture_output=True, check=True)
                    return ["minifab"]
                except:
                    continue
            elif cmd == "./network.sh" and os.path.exists("network.sh"):
                return ["bash", "./network.sh"]
        
        return None
    
    def update_blockchain(self, slot_id: str, occupied: bool, location: str) -> bool:

        try:
            occupied_str = "true" if occupied else "false"
            param_str = f'"UpdateStatus","{slot_id}","{occupied_str}","{location}"'
            
            cmd = self.minifab_cmd + [
                "invoke", 
                "-n", self.chaincode_name,
                "-p", param_str
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Blockchain updated: {slot_id} -> {occupied}")
                return True
            else:
                logger.error(f"Blockchain update failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Blockchain update error: {str(e)}")
            return False
    
    def process_transaction_queue(self):

        while self.is_running:
            try:
                event = self.transaction_queue.get(timeout=1)
                success = self.update_blockchain(
                    event.slot_id, 
                    event.occupied, 
                    event.location
                )
                
                if not success:
                    # Retry failed transactions
                    logger.warning(f" Retrying failed transaction for {event.slot_id}")
                    time.sleep(2)
                    self.update_blockchain(event.slot_id, event.occupied, event.location)
                
                self.transaction_queue.task_done()
                
            except queue.Empty:
                continue
        
        logger.info(" Transaction processor stopped")

class IoTSensorSimulator:
    def __init__(self, blockchain_connector: IoTBlockchainConnector):
        self.sensors: Dict[str, IoTSensor] = {}
        self.blockchain = blockchain_connector
        self.event_history: List[ParkingEvent] = []
        self.simulation_active = False
        

        self.car_arrival_rate = 0.1  # Probability per minute
        self.car_departure_rate = 0.05  # Probability per minute
        self.sensor_error_rate = 0.02  # Probability of false reading
        self.battery_drain_rate = 0.001  # Battery % per hour
        
    def create_sensors(self, num_sensors: int):
        """Create IoT sensors for parking slots"""
        logger.info(f" Creating {num_sensors} IoT sensors...")
        
        locations = [
            "Mall Entrance", "Mall Exit", "Ground Floor A", "Ground Floor B",
            "First Floor A", "First Floor B", "Second Floor A", "Second Floor B",
            "VIP Section", "Disabled Parking", "Electric Vehicle", "Visitor Parking"
        ]
        
        for i in range(num_sensors):
            sensor_id = f"IOT-{i+1:03d}"
            slot_id = f"lot-{i+1:03d}"
            location = locations[i % len(locations)]
            
            sensor = IoTSensor(
                sensor_id=sensor_id,
                slot_id=slot_id,
                location=location,
                battery_level=random.uniform(80, 100),
                last_reading=datetime.now(),
                status='active',
                occupied=random.choice([True, False]),
                confidence=random.uniform(0.85, 0.99)
            )
            
            self.sensors[sensor_id] = sensor
            

            self.blockchain.transaction_queue.put(
                ParkingEvent(
                    sensor_id=sensor_id,
                    slot_id=slot_id,
                    location=location,
                    occupied=sensor.occupied,
                    timestamp=datetime.now(),
                    confidence=sensor.confidence,
                    event_type='initialization'
                )
            )
        
        logger.info(f" Created {len(self.sensors)} IoT sensors")
    
    def simulate_car_movement(self, sensor: IoTSensor) -> Optional[ParkingEvent]:

        current_time = datetime.now()
        

        if sensor.status != 'active':
            return None
        

        if sensor.occupied:

            if random.random() < self.car_departure_rate:
                sensor.occupied = False
                sensor.last_reading = current_time
                

                confidence = max(0.7, sensor.confidence - random.uniform(0, 0.1))
                
                return ParkingEvent(
                    sensor_id=sensor.sensor_id,
                    slot_id=sensor.slot_id,
                    location=sensor.location,
                    occupied=False,
                    timestamp=current_time,
                    confidence=confidence,
                    event_type='departure'
                )
        else:

            if random.random() < self.car_arrival_rate:
                sensor.occupied = True
                sensor.last_reading = current_time
                

                confidence = max(0.7, sensor.confidence - random.uniform(0, 0.1))
                
                return ParkingEvent(
                    sensor_id=sensor.sensor_id,
                    slot_id=sensor.slot_id,
                    location=sensor.location,
                    occupied=True,
                    timestamp=current_time,
                    confidence=confidence,
                    event_type='arrival'
                )
        
        return None
    
    def simulate_sensor_issues(self, sensor: IoTSensor):


        sensor.battery_level -= self.battery_drain_rate
        

        if sensor.battery_level < 20:
            sensor.status = 'low_battery'
        elif sensor.battery_level < 5:
            sensor.status = 'offline'
        else:
            sensor.status = 'active'
        

        if random.random() < self.sensor_error_rate:
            sensor.confidence = max(0.5, sensor.confidence - 0.2)
    
    def generate_sensor_heartbeat(self, sensor: IoTSensor) -> ParkingEvent:

        return ParkingEvent(
            sensor_id=sensor.sensor_id,
            slot_id=sensor.slot_id,
            location=sensor.location,
            occupied=sensor.occupied,
            timestamp=datetime.now(),
            confidence=sensor.confidence,
            event_type='heartbeat'
        )
    
    def run_simulation_cycle(self):

        events_generated = 0
        
        for sensor in self.sensors.values():

            self.simulate_sensor_issues(sensor)
            

            event = self.simulate_car_movement(sensor)
            if event:
                self.event_history.append(event)
                

                if event.confidence > 0.75:
                    self.blockchain.transaction_queue.put(event)
                    events_generated += 1
                    
                    logger.info(f" {event.event_type.title()}: {event.slot_id} at {event.location}")
        
        return events_generated
    
    def start_simulation(self, duration_minutes: int = 30):

        logger.info(f" Starting IoT simulation for {duration_minutes} minutes...")
        
        self.simulation_active = True
        self.blockchain.is_running = True
        

        blockchain_thread = threading.Thread(
            target=self.blockchain.process_transaction_queue,
            daemon=True
        )
        blockchain_thread.start()
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        cycle_count = 0
        total_events = 0
        
        try:
            while datetime.now() < end_time and self.simulation_active:
                cycle_count += 1
                events = self.run_simulation_cycle()
                total_events += events
                
                if cycle_count % 10 == 0:  # Status every 10 cycles
                    active_sensors = sum(1 for s in self.sensors.values() if s.status == 'active')
                    occupied_slots = sum(1 for s in self.sensors.values() if s.occupied)
                    
                    logger.info(f" Cycle {cycle_count}: {active_sensors} active sensors, "
                              f"{occupied_slots} occupied slots, {events} new events")
                
                time.sleep(6)  # 6 seconds per cycle = 10 cycles per minute
                
        except KeyboardInterrupt:
            logger.info(" Simulation stopped by user")
        
        self.simulation_active = False
        self.blockchain.is_running = False
        
        logger.info(f" Simulation completed: {total_events} events generated in {cycle_count} cycles")
        
        return self.generate_simulation_report()
    
    def generate_simulation_report(self) -> Dict:

        current_time = datetime.now()
        

        active_sensors = [s for s in self.sensors.values() if s.status == 'active']
        low_battery_sensors = [s for s in self.sensors.values() if s.status == 'low_battery']
        offline_sensors = [s for s in self.sensors.values() if s.status == 'offline']
        

        occupied_slots = [s for s in self.sensors.values() if s.occupied]
        free_slots = [s for s in self.sensors.values() if not s.occupied]
        

        arrivals = [e for e in self.event_history if e.event_type == 'arrival']
        departures = [e for e in self.event_history if e.event_type == 'departure']
        

        avg_confidence = sum(s.confidence for s in self.sensors.values()) / len(self.sensors)
        avg_battery = sum(s.battery_level for s in self.sensors.values()) / len(self.sensors)
        
        report = {
            'simulation_summary': {
                'total_sensors': len(self.sensors),
                'active_sensors': len(active_sensors),
                'low_battery_sensors': len(low_battery_sensors),
                'offline_sensors': len(offline_sensors),
                'sensor_health': f"{(len(active_sensors)/len(self.sensors))*100:.1f}%"
            },
            'parking_status': {
                'occupied_slots': len(occupied_slots),
                'free_slots': len(free_slots),
                'occupancy_rate': f"{(len(occupied_slots)/len(self.sensors))*100:.1f}%"
            },
            'event_statistics': {
                'total_events': len(self.event_history),
                'car_arrivals': len(arrivals),
                'car_departures': len(departures),
                'avg_sensor_confidence': f"{avg_confidence:.2f}",
                'avg_battery_level': f"{avg_battery:.1f}%"
            },
            'location_breakdown': self.get_location_breakdown(),
            'timestamp': current_time.isoformat()
        }
        
        return report
    
    def get_location_breakdown(self) -> Dict:

        location_stats = {}
        
        for sensor in self.sensors.values():
            location = sensor.location
            if location not in location_stats:
                location_stats[location] = {
                    'total_slots': 0,
                    'occupied_slots': 0,
                    'active_sensors': 0
                }
            
            location_stats[location]['total_slots'] += 1
            if sensor.occupied:
                location_stats[location]['occupied_slots'] += 1
            if sensor.status == 'active':
                location_stats[location]['active_sensors'] += 1
        
        # Calculate occupancy rates
        for location, stats in location_stats.items():
            if stats['total_slots'] > 0:
                stats['occupancy_rate'] = f"{(stats['occupied_slots']/stats['total_slots'])*100:.1f}%"
            else:
                stats['occupancy_rate'] = "0%"
        
        return location_stats

class IoTDashboard:
    def __init__(self, simulator: IoTSensorSimulator):
        self.simulator = simulator
    
    def print_real_time_status(self):

        os.system('clear' if os.name == 'posix' else 'cls')
        
        print(" IoT SMART PARKING SYSTEM - REAL-TIME STATUS")
        print("=" * 80)
        print(f" Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        

        total_sensors = len(self.simulator.sensors)
        active_sensors = sum(1 for s in self.simulator.sensors.values() if s.status == 'active')
        occupied_slots = sum(1 for s in self.simulator.sensors.values() if s.occupied)
        
        print(f"\n SYSTEM OVERVIEW:")
        print(f"     Total Sensors: {total_sensors}")
        print(f"     Active Sensors: {active_sensors}")
        print(f"     Occupied Slots: {occupied_slots}")
        print(f"     Free Slots: {total_sensors - occupied_slots}")
        print(f"    Occupancy Rate: {(occupied_slots/total_sensors)*100:.1f}%")
        

        recent_events = self.simulator.event_history[-5:] if self.simulator.event_history else []
        print(f"\n RECENT EVENTS:")
        for event in recent_events:
            icon = "" if event.occupied else "P"
            print(f"    {icon} {event.timestamp.strftime('%H:%M:%S')} - "
                  f"{event.slot_id} ({event.location}) - {event.event_type}")
        

        low_battery = [s for s in self.simulator.sensors.values() if s.status == 'low_battery']
        offline = [s for s in self.simulator.sensors.values() if s.status == 'offline']
        
        if low_battery or offline:
            print(f"\n SENSOR ALERTS:")
            for sensor in low_battery:
                print(f"     {sensor.sensor_id}: Low Battery ({sensor.battery_level:.1f}%)")
            for sensor in offline:
                print(f"    {sensor.sensor_id}: Offline")

def main():

    print(" IoT Smart Parking System with Blockchain Integration")
    print("=" * 60)
    
    # Initialize blockchain connector
    blockchain = IoTBlockchainConnector()
    
    if not blockchain.minifab_cmd:
        print(" Could not detect minifab command!")
        print(" Please ensure you have ./minifab or minifab in PATH")
        return
    
    print(f" Blockchain connector initialized: {' '.join(blockchain.minifab_cmd)}")
    
    # Initialize IoT simulator
    simulator = IoTSensorSimulator(blockchain)
    dashboard = IoTDashboard(simulator)
    
    try:

        num_sensors = int(input(" Number of IoT sensors to create (default: 20): ") or "20")
        duration = int(input(" Simulation duration in minutes (default: 10): ") or "10")
        
        print(f"\n Setting up {num_sensors} IoT sensors...")
        simulator.create_sensors(num_sensors)
        
        print(" IoT sensors created and initialized on blockchain")
        print(f" Starting {duration}-minute simulation...")
        

        report = simulator.start_simulation(duration)
        

        print("\nFINAL IoT SIMULATION REPORT")
        print("=" * 50)
        
        for category, data in report.items():
            print(f"\n{category.replace('_', ' ').title()}:")
            if isinstance(data, dict):
                for key, value in data.items():
                    print(f"    {key.replace('_', ' ').title()}: {value}")
        

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'iot_simulation_report_{timestamp}.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n Detailed report saved: {report_file}")
        print(" IoT simulation completed successfully!")
        
    except KeyboardInterrupt:
        print("\n Simulation interrupted by user")
    except Exception as e:
        logger.error(f" Error during simulation: {str(e)}")
        print(f" Simulation error: {str(e)}")

if __name__ == "__main__":
    main()
