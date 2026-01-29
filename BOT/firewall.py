# BOT/firewall_protection.py
"""
AUTOMATIC FIREWALL PROTECTION
- Runs independently
- Monitors and blocks attacks automatically
- No admin commands needed
"""

import os
import sys
import time
import socket
import struct
import select
import threading
from datetime import datetime, timedelta
import ipaddress

class AutoFirewall:
    def __init__(self):
        self.blocked_ips = set()
        self.suspicious_ips = {}
        self.attack_log = []
        self.max_log_size = 1000
        
        # Rate limiting thresholds
        self.MAX_REQUESTS_PER_MIN = 50
        self.BAN_DURATION_HOURS = 24
        self.SUSPICIOUS_THRESHOLD = 5
        
        # Start protection
        self.running = True
        self.protection_thread = threading.Thread(target=self.monitor_attacks, daemon=True)
        self.protection_thread.start()
        
        print("[AUTO-FIREWALL] Automatic protection started")
    
    def is_attack_pattern(self, data):
        """Detect attack patterns"""
        if not data:
            return False
            
        patterns = [
            b'\x16\x03\x01',      # SSL/TLS handshake
            b'\x16\x03\x00',      # SSL/TLS
            b'PRI * HTTP/2.0',    # HTTP/2.0 PRI
            b'GET /wp-admin',     # WordPress scan
            b'GET /phpmyadmin',   # phpMyAdmin scan
            b'GET /admin',        # Admin panel scan
            b'GET /cgi-bin',      # CGI scan
            b'GET /\.env',        # Config file scan
            b'GET /\.git',        # Git scan
            b'SELECT',            # SQL injection
            b'UNION SELECT',      # SQL injection
            b'<script>',          # XSS
            b'../',               # Path traversal
        ]
        
        for pattern in patterns:
            if pattern in data:
                return True
        return False
    
    def monitor_attacks(self):
        """Monitor and block attacks automatically"""
        while self.running:
            try:
                # Check for new attacks (you'd integrate with your web server logs)
                # For now, this is a template - integrate with your actual web server
                self.cleanup_old_blocks()
                time.sleep(60)  # Check every minute
            except Exception as e:
                print(f"[FIREWALL-ERROR] {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def block_ip_automatically(self, ip, reason):
        """Automatically block an IP"""
        if ip in self.blocked_ips:
            return
            
        self.blocked_ips.add(ip)
        
        # Log the attack
        log_entry = f"[{datetime.now()}] AUTO-BLOCKED {ip} - {reason}"
        self.attack_log.append(log_entry)
        
        # Keep log manageable
        if len(self.attack_log) > self.max_log_size:
            self.attack_log = self.attack_log[-self.max_log_size:]
        
        print(log_entry)
        
        # Save to file
        self.save_blocked_ips()
        
        # Schedule auto-unban
        self.schedule_unban(ip)
    
    def schedule_unban(self, ip):
        """Schedule automatic unban after ban duration"""
        def unban_later():
            time.sleep(self.BAN_DURATION_HOURS * 3600)
            if ip in self.blocked_ips:
                self.blocked_ips.remove(ip)
                print(f"[AUTO-FIREWALL] Auto-unbanned {ip} after {self.BAN_DURATION_HOURS}h")
                self.save_blocked_ips()
        
        thread = threading.Thread(target=unban_later, daemon=True)
        thread.start()
    
    def cleanup_old_blocks(self):
        """Clean up old suspicious IP records"""
        current_time = time.time()
        old_ips = []
        
        for ip, (count, first_seen) in list(self.suspicious_ips.items()):
            if current_time - first_seen > 3600:  # 1 hour
                old_ips.append(ip)
        
        for ip in old_ips:
            del self.suspicious_ips[ip]
    
    def save_blocked_ips(self):
        """Save blocked IPs to file"""
        try:
            os.makedirs("DATA", exist_ok=True)
            with open("DATA/blocked_ips.txt", "w") as f:
                for ip in self.blocked_ips:
                    f.write(f"{ip}\n")
                    
            # Also save attack log
            with open("DATA/attack_log.txt", "w") as f:
                for log in self.attack_log:
                    f.write(f"{log}\n")
        except Exception as e:
            print(f"[FIREWALL-SAVE-ERROR] {e}")
    
    def load_blocked_ips(self):
        """Load blocked IPs from file"""
        try:
            if os.path.exists("DATA/blocked_ips.txt"):
                with open("DATA/blocked_ips.txt", "r") as f:
                    for line in f:
                        ip = line.strip()
                        if ip:
                            self.blocked_ips.add(ip)
        except Exception as e:
            print(f"[FIREWALL-LOAD-ERROR] {e}")
    
    def is_ip_blocked(self, ip):
        """Check if IP is blocked"""
        return ip in self.blocked_ips
    
    def stop(self):
        """Stop firewall protection"""
        self.running = False
        self.save_blocked_ips()

# Global firewall instance
firewall = AutoFirewall()
firewall.load_blocked_ips()

# Simple decorator to check IP (if you're running a web server)
def check_request_ip(func):
    """Decorator to check IP before processing request"""
    def wrapper(request, *args, **kwargs):
        # Extract IP from request (implementation depends on your web framework)
        # Example for Flask: request.remote_addr
        # Example for aiohttp: request.remote
        client_ip = get_client_ip_from_request(request)
        
        if firewall.is_ip_blocked(client_ip):
            return "Blocked by firewall", 403
        
        return func(request, *args, **kwargs)
    return wrapper

def get_client_ip_from_request(request):
    """Extract client IP from request object"""
    # This needs to be implemented based on your web framework
    # For Flask: return request.remote_addr
    # For aiohttp: return request.remote
    # For now, return placeholder
    return "0.0.0.0"
