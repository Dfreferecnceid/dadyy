# BOT/tools/proxy.py

from pyrogram import Client, filters
from pyrogram.types import Message
import json, re, os, asyncio, httpx, random, time, threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Tuple, Set
from datetime import datetime
from collections import defaultdict
import csv

# Import disabled commands functions from Admins module
from ..helper.Admins import (
    is_command_disabled, get_command_offline_message,
    is_user_restricted_for_command
)

# Import the new auth_and_free_restricted decorator
from ..helper.permissions import auth_and_free_restricted

# File paths
PROXY_FILE = "DATA/proxy.json"
GLOBAL_PROXY_FILE = "FILES/proxy.csv"
VALID_PROXY_FILE = "DATA/valid_proxies.json"
DEAD_PROXY_FILE = "DATA/dead_proxies.json"

# Lock for thread-safe operations
_proxy_lock = threading.Lock()

def is_owner(user_id: int) -> bool:
    """Check if user is owner"""
    try:
        with open("FILES/config.json", "r") as f:
            config = json.load(f)
            return str(user_id) == str(config.get("OWNER"))
    except:
        return False

class ProxyManager:
    """Thread-safe proxy manager with dual-site validation"""

    def __init__(self):
        self.user_proxies: Dict[str, List[str]] = {}  # user_id -> list of proxies
        self.user_proxy_map: Dict[str, str] = {}  # proxy -> user_id for ownership
        self.valid_proxies: List[str] = []
        self.dead_proxies: Set[str] = set()
        self.perm_dead_proxies: Set[str] = set()
        self.proxy_stats: Dict[str, Dict] = {}
        self.validation_in_progress = False
        self.executor = ThreadPoolExecutor(max_workers=50)
        self.last_validation = 0
        self.last_cleanup = time.time()

        print("🔄 Initializing Proxy Manager...")
        self.load_and_validate_all_proxies()

    def normalize_proxy(self, proxy_raw: str) -> Optional[str]:
        """Normalize proxy string to URL format - HTTP ONLY"""
        proxy_raw = proxy_raw.strip()

        if not proxy_raw:
            return None

        # Already full proxy URL
        if proxy_raw.startswith("http://") or proxy_raw.startswith("https://"):
            # Force HTTP for compatibility
            return proxy_raw.replace("https://", "http://")

        # Format: USER:PASS@HOST:PORT
        match1 = re.fullmatch(r"(.+?):(.+?)@([a-zA-Z0-9\.\-]+):(\d+)", proxy_raw)
        if match1:
            user, pwd, host, port = match1.groups()
            return f"http://{user}:{pwd}@{host}:{port}"

        # Format: HOST:PORT:USER:PASS
        match2 = re.fullmatch(r"([a-zA-Z0-9\.\-]+):(\d+):(.+?):(.+)", proxy_raw)
        if match2:
            host, port, user, pwd = match2.groups()
            return f"http://{user}:{pwd}@{host}:{port}"

        # Format: HOST:PORT (no auth)
        match3 = re.fullmatch(r"([a-zA-Z0-9\.\-]+):(\d+)", proxy_raw)
        if match3:
            host, port = match3.groups()
            return f"http://{host}:{port}"

        return None

    def load_and_validate_all_proxies(self):
        """Load all proxies and validate them with dual-site check"""
        print("🔄 Loading and validating proxies...")

        with _proxy_lock:
            # Load user-specific proxies
            if os.path.exists(PROXY_FILE):
                try:
                    with open(PROXY_FILE, "r") as f:
                        data = json.load(f)
                        # Load user proxies with backward compatibility
                        if isinstance(data, dict) and "user_proxies" in data:
                            self.user_proxies = data.get("user_proxies", {})
                            self.user_proxy_map = data.get("user_proxy_map", {})
                        else:
                            # Old format - convert
                            self.user_proxies = {}
                            self.user_proxy_map = {}
                            for user_id, proxy in data.items():
                                if proxy:
                                    self.user_proxies.setdefault(str(user_id), []).append(proxy)
                                    self.user_proxy_map[proxy] = str(user_id)
                    print(f"✅ Loaded {len(self.user_proxy_map)} user proxies from {len(self.user_proxies)} users")
                except Exception as e:
                    print(f"❌ Error loading user proxies: {e}")
                    self.user_proxies = {}
                    self.user_proxy_map = {}

            # Load previously validated proxies
            self._load_valid_proxies()

            # Load new proxies from CSV and validate them
            new_proxies = self._load_proxies_from_csv()

            if new_proxies:
                print(f"📥 Found {len(new_proxies)} new proxies in CSV, validating with dual-site check...")
                self._validate_proxy_batch_dual(new_proxies, owner_id="system")
            else:
                print(f"⚠️ No proxies found in {GLOBAL_PROXY_FILE}")

            # Save validated proxies
            self._save_valid_proxies()

            print(f"🎯 Proxy Manager Ready: {len(self.valid_proxies)} valid proxies available")

    def _load_valid_proxies(self):
        """Load previously validated working proxies"""
        try:
            if os.path.exists(VALID_PROXY_FILE):
                with open(VALID_PROXY_FILE, "r") as f:
                    data = json.load(f)
                    self.valid_proxies = data.get('valid', [])
                    self.perm_dead_proxies = set(data.get('dead', []))
                    self.proxy_stats = data.get('stats', {})
                print(f"📂 Loaded {len(self.valid_proxies)} pre-validated proxies")
                print(f"📂 Loaded {len(self.perm_dead_proxies)} known dead proxies")
        except Exception as e:
            print(f"❌ Error loading validated proxies: {e}")
            self.valid_proxies = []
            self.perm_dead_proxies = set()
            self.proxy_stats = {}

    def _load_proxies_from_csv(self) -> List[str]:
        """Load raw proxies from CSV file"""
        raw_proxies = []

        if not os.path.exists(GLOBAL_PROXY_FILE):
            print(f"⚠️ Global proxy file not found: {GLOBAL_PROXY_FILE}")
            return []

        try:
            # Try reading as plain text (one proxy per line)
            with open(GLOBAL_PROXY_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        raw_proxies.append(line)

            # Normalize all proxies
            normalized_proxies = []
            for raw in raw_proxies:
                proxy = self.normalize_proxy(raw)
                if proxy:
                    normalized_proxies.append(proxy)

            # Filter out already known proxies
            new_proxies = []
            for proxy in normalized_proxies:
                if (proxy not in self.valid_proxies and 
                    proxy not in self.perm_dead_proxies and
                    proxy not in self.user_proxy_map):
                    new_proxies.append(proxy)

            return new_proxies

        except Exception as e:
            print(f"❌ Error loading proxies from CSV: {e}")
            return []

    def _test_proxy_dual_sync(self, proxy_url: str) -> Tuple[bool, float, Optional[str], str]:
        """Test proxy with dual-site check (sync for thread pool)"""
        test_sites = [
            ("https://ipinfo.io/json", "ipinfo"),  # HTTPS + detailed info
            ("http://httpbin.org/ip", "httpbin"),   # HTTP + simple response
        ]

        best_result = (False, 10.0, None, "No sites reached")

        for site_url, site_name in test_sites:
            try:
                with httpx.Client(
                    proxy=proxy_url,
                    timeout=8.0,  # Shorter timeout for faster validation
                    follow_redirects=True
                ) as client:
                    start = time.time()
                    response = client.get(site_url)
                    response_time = time.time() - start

                    if response.status_code == 200:
                        # Try to extract IP
                        ip = None
                        try:
                            data = response.json()
                            if site_name == "ipinfo":
                                ip = data.get('ip')
                            elif site_name == "httpbin":
                                ip = data.get('origin')
                        except:
                            ip = "Unknown"

                        # Return first successful site
                        return True, response_time, ip, f"{site_name} ({response_time:.2f}s)"

            except Exception as e:
                error_msg = f"{site_name}: {str(e)[:50]}"
                continue

        return best_result

    def _validate_proxy_batch_dual(self, proxies: List[str], owner_id: str = "system"):
        """Validate a batch of proxies with dual-site checking"""
        if self.validation_in_progress:
            print("⚠️ Validation already in progress, skipping...")
            return

        self.validation_in_progress = True

        try:
            print(f"🔍 Validating {len(proxies)} proxies (dual-site check)...")

            # Submit all validation tasks
            future_to_proxy = {}
            for proxy in proxies:
                future = self.executor.submit(self._test_proxy_dual_sync, proxy)
                future_to_proxy[future] = proxy

            # Process results as they complete
            valid_count = 0
            dead_count = 0

            for future in concurrent.futures.as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    result = future.result(timeout=12)  # (is_valid, response_time, ip, site)
                    if result[0]:  # Valid proxy
                        with _proxy_lock:
                            self.valid_proxies.append(proxy)
                            self.proxy_stats[proxy] = {
                                'success': 1,
                                'fails': 0,
                                'response_time': result[1],
                                'ip': result[2],
                                'site': result[3],
                                'last_used': time.time(),
                                'owner': owner_id if owner_id != "system" else "global"
                            }
                            # Track user ownership
                            if owner_id != "system":
                                self.user_proxy_map[proxy] = owner_id
                                self.user_proxies.setdefault(owner_id, []).append(proxy)
                        valid_count += 1
                        print(f"✅ Proxy validated via {result[3]}: {proxy[:60]}...")
                    else:
                        with _proxy_lock:
                            self.perm_dead_proxies.add(proxy)
                            if owner_id != "system":
                                self.user_proxy_map[proxy] = owner_id
                                self.user_proxies.setdefault(owner_id, []).append(proxy)
                        dead_count += 1
                        print(f"❌ Proxy dead: {proxy[:60]}...")

                except Exception as e:
                    with _proxy_lock:
                        self.perm_dead_proxies.add(proxy)
                        if owner_id != "system":
                            self.user_proxy_map[proxy] = owner_id
                            self.user_proxies.setdefault(owner_id, []).append(proxy)
                    dead_count += 1
                    print(f"❌ Proxy error: {proxy[:60]}... - {str(e)[:50]}")

            print(f"📊 Validation Complete: {valid_count} valid, {dead_count} dead")
            self.last_validation = time.time()

        except Exception as e:
            print(f"❌ Batch validation error: {e}")
        finally:
            self.validation_in_progress = False

    def _save_valid_proxies(self):
        """Save validated proxies to file"""
        try:
            data = {
                'valid': self.valid_proxies,
                'dead': list(self.perm_dead_proxies),
                'stats': self.proxy_stats,
                'user_proxies': self.user_proxies,
                'user_proxy_map': self.user_proxy_map,
                'last_updated': time.time()
            }

            with open(VALID_PROXY_FILE, "w") as f:
                json.dump(data, f, indent=2)

            # Also save user proxies separately
            user_data = {
                'user_proxies': self.user_proxies,
                'user_proxy_map': self.user_proxy_map
            }
            with open(PROXY_FILE, "w") as f:
                json.dump(user_data, f, indent=2)

            print(f"💾 Saved {len(self.valid_proxies)} valid proxies to {VALID_PROXY_FILE}")

        except Exception as e:
            print(f"❌ Error saving validated proxies: {e}")

    def get_proxy_for_user(self, user_id: int, strategy: str = "random") -> Optional[str]:
        """Get proxy for user (personal proxy → valid global proxy → None)"""
        with _proxy_lock:
            # Clean dead proxies periodically
            self._clean_dead_proxies()

            user_str = str(user_id)
            
            # 1. Check user's own proxies first
            if user_str in self.user_proxies:
                user_proxy_list = self.user_proxies[user_str]
                # Filter out dead proxies
                available_user_proxies = [p for p in user_proxy_list 
                                         if p not in self.dead_proxies 
                                         and p not in self.perm_dead_proxies
                                         and p in self.valid_proxies]
                
                if available_user_proxies:
                    proxy = random.choice(available_user_proxies)
                    self._update_stats(proxy)
                    return proxy

            # 2. Use validated global proxy pool (excluding other users' proxies)
            available_proxies = [p for p in self.valid_proxies 
                               if p not in self.dead_proxies 
                               and self.user_proxy_map.get(p) in [None, "global", "system"]]

            if not available_proxies:
                return None

            # Select based on strategy
            if strategy == "random":
                proxy = random.choice(available_proxies)
            elif strategy == "fastest":
                proxy = min(available_proxies,
                          key=lambda p: self.proxy_stats.get(p, {}).get('response_time', 10))
            elif strategy == "least_used":
                proxy = min(available_proxies,
                          key=lambda p: self.proxy_stats.get(p, {}).get('success', 0))
            elif strategy == "round_robin":
                proxy = min(available_proxies,
                          key=lambda p: self.proxy_stats.get(p, {}).get('last_used', 0))
            else:
                proxy = random.choice(available_proxies)

            self._update_stats(proxy)
            return proxy

    def get_random_proxy(self) -> Optional[str]:
        """Get a random proxy (compatibility function for old scripts)"""
        return self.get_proxy_for_user(0, "random")  # Use user_id=0 for system proxy

    def _update_stats(self, proxy: str):
        """Update proxy usage statistics"""
        if proxy not in self.proxy_stats:
            owner = self.user_proxy_map.get(proxy, "global")
            self.proxy_stats[proxy] = {
                'success': 0,
                'fails': 0,
                'response_time': 5.0,
                'ip': 'Unknown',
                'site': 'Unknown',
                'last_used': time.time(),
                'owner': owner
            }
        else:
            self.proxy_stats[proxy]['last_used'] = time.time()

    def mark_proxy_success(self, proxy: str, response_time: float):
        """Mark proxy as successful"""
        with _proxy_lock:
            if proxy in self.proxy_stats:
                self.proxy_stats[proxy]['success'] += 1
                # Update average response time
                old_time = self.proxy_stats[proxy].get('response_time', 5.0)
                new_time = (old_time + response_time) / 2
                self.proxy_stats[proxy]['response_time'] = new_time
                self.dead_proxies.discard(proxy)

    def mark_proxy_failed(self, proxy: str):
        """Mark proxy as failed (temporarily dead)"""
        with _proxy_lock:
            if proxy in self.proxy_stats:
                self.proxy_stats[proxy]['fails'] += 1
                if self.proxy_stats[proxy]['fails'] > 2:
                    self.dead_proxies.add(proxy)

    def _clean_dead_proxies(self):
        """Remove old dead proxies after timeout"""
        current = time.time()
        if current - self.last_cleanup < 300:  # 5 minutes
            return

        to_remove = set()
        for proxy in self.dead_proxies:
            if proxy in self.proxy_stats:
                last_used = self.proxy_stats[proxy].get('last_used', 0)
                if current - last_used > 900:  # 15 minutes
                    to_remove.add(proxy)
                    self.proxy_stats[proxy]['fails'] = 0

        self.dead_proxies -= to_remove
        if to_remove:
            print(f"♻️ Reactivated {len(to_remove)} proxies")

        self.last_cleanup = current

    def validate_single_proxy(self, proxy_raw: str, owner_id: str = "system") -> Tuple[bool, str, float, str]:
        """Validate a single proxy immediately with dual-site check"""
        proxy_url = self.normalize_proxy(proxy_raw)

        if not proxy_url:
            return False, "Invalid format", 0.0, "Invalid"

        # Check if already known
        if proxy_url in self.valid_proxies:
            stats = self.proxy_stats.get(proxy_url, {})
            return True, f"Already valid ({stats.get('site', 'Unknown')})", stats.get('response_time', 0.0), "Cached"

        if proxy_url in self.perm_dead_proxies:
            return False, "Previously marked as dead", 0.0, "Cached"

        # Test the proxy with dual sites
        is_valid, response_time, ip, site = self._test_proxy_dual_sync(proxy_url)

        if is_valid:
            with _proxy_lock:
                self.valid_proxies.append(proxy_url)
                self.proxy_stats[proxy_url] = {
                    'success': 1,
                    'fails': 0,
                    'response_time': response_time,
                    'ip': ip,
                    'site': site,
                    'last_used': time.time(),
                    'owner': owner_id if owner_id != "system" else "global"
                }
                # Track user ownership
                if owner_id != "system":
                    self.user_proxy_map[proxy_url] = owner_id
                    self.user_proxies.setdefault(owner_id, []).append(proxy_url)
                self._save_valid_proxies()
            return True, ip, response_time, site
        else:
            with _proxy_lock:
                self.perm_dead_proxies.add(proxy_url)
                # Still track ownership even if dead
                if owner_id != "system":
                    self.user_proxy_map[proxy_url] = owner_id
                    self.user_proxies.setdefault(owner_id, []).append(proxy_url)
                self._save_valid_proxies()
            return False, f"Failed on both sites", response_time, "Failed"

    def add_proxies_bulk(self, proxies_text: str, user_id: str) -> Dict[str, int]:
        """Add multiple proxies from text (bulk addition)"""
        lines = proxies_text.strip().split('\n')
        normalized_proxies = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                proxy = self.normalize_proxy(line)
                if proxy:
                    normalized_proxies.append(proxy)

        # Filter out already known (owned by this user or global)
        new_proxies = []
        for proxy in normalized_proxies:
            proxy_owner = self.user_proxy_map.get(proxy)
            if proxy_owner is None or proxy_owner == user_id:
                new_proxies.append(proxy)

        if not new_proxies:
            return {'total': 0, 'new': 0, 'duplicate': len(normalized_proxies)}

        # Validate new proxies with user ownership
        self._validate_proxy_batch_dual(new_proxies, owner_id=user_id)
        self._save_valid_proxies()

        stats = self.get_stats_for_user(user_id)
        return {
            'total': len(normalized_proxies),
            'new': len(new_proxies),
            'duplicate': len(normalized_proxies) - len(new_proxies),
            'valid_now': stats['total_valid'],
            'available_now': stats['available_now']
        }

    def remove_proxies_bulk(self, proxies_text: str, user_id: str) -> Dict[str, int]:
        """Remove multiple proxies from text (user can only remove their own)"""
        lines = proxies_text.strip().split('\n')
        normalized_proxies = []

        for line in lines:
            line = line.strip()
            if line:
                proxy = self.normalize_proxy(line)
                if proxy:
                    normalized_proxies.append(proxy)

        removed_count = 0
        with _proxy_lock:
            for proxy in normalized_proxies:
                # Check if user owns this proxy
                proxy_owner = self.user_proxy_map.get(proxy)
                if proxy_owner == user_id:
                    # Remove from valid proxies
                    if proxy in self.valid_proxies:
                        self.valid_proxies.remove(proxy)
                        removed_count += 1

                    # Remove from user's list
                    if user_id in self.user_proxies:
                        if proxy in self.user_proxies[user_id]:
                            self.user_proxies[user_id].remove(proxy)
                            if not self.user_proxies[user_id]:
                                del self.user_proxies[user_id]

                    # Remove from stats and maps
                    if proxy in self.proxy_stats:
                        del self.proxy_stats[proxy]
                    
                    if proxy in self.user_proxy_map:
                        del self.user_proxy_map[proxy]

                    # Remove from dead sets
                    self.dead_proxies.discard(proxy)
                    self.perm_dead_proxies.discard(proxy)

        if removed_count > 0:
            self._save_valid_proxies()

        return {
            'requested': len(normalized_proxies),
            'removed': removed_count,
            'remaining': self.get_user_proxy_count(user_id)
        }

    def get_user_proxy_count(self, user_id: str) -> int:
        """Get count of proxies owned by user"""
        return len(self.user_proxies.get(user_id, []))

    def remove_all_proxies(self) -> int:
        """Remove all proxies from global pool"""
        with _proxy_lock:
            removed_count = len(self.valid_proxies)
            self.valid_proxies = []
            self.dead_proxies = set()
            self.perm_dead_proxies = set()
            self.proxy_stats = {}
            self.user_proxies = {}
            self.user_proxy_map = {}

            # Also clear CSV file
            try:
                open(GLOBAL_PROXY_FILE, 'w').close()
            except:
                pass

            self._save_valid_proxies()

        return removed_count

    def get_stats_for_user(self, user_id: str) -> Dict:
        """Get statistics about user's own proxies"""
        with _proxy_lock:
            user_proxy_list = self.user_proxies.get(user_id, [])
            
            # Calculate user's proxy stats
            valid_count = 0
            dead_count = 0
            temp_dead_count = 0
            
            user_proxy_performance = []
            
            for proxy in user_proxy_list:
                is_valid = proxy in self.valid_proxies
                is_dead = proxy in self.perm_dead_proxies
                is_temp_dead = proxy in self.dead_proxies
                
                if is_valid:
                    valid_count += 1
                elif is_dead:
                    dead_count += 1
                elif is_temp_dead:
                    temp_dead_count += 1
                
                # Get performance stats
                if proxy in self.proxy_stats:
                    stats = self.proxy_stats[proxy]
                    success = stats.get('success', 0)
                    fails = stats.get('fails', 0)
                    total = success + fails
                    rate = (success / total * 100) if total > 0 else 0
                    
                    user_proxy_performance.append({
                        'proxy': proxy,  # User sees complete proxy
                        'success': success,
                        'fails': fails,
                        'rate': rate,
                        'response_time': stats.get('response_time', 0),
                        'site': stats.get('site', 'Unknown'),
                        'status': '✅' if proxy not in self.dead_proxies else '❌',
                        'valid': is_valid
                    })

            user_proxy_performance.sort(key=lambda x: x['rate'], reverse=True)

            return {
                'total_valid': valid_count,
                'total_dead': dead_count,
                'temp_dead': temp_dead_count,
                'available_now': len([p for p in user_proxy_list if p in self.valid_proxies and p not in self.dead_proxies]),
                'user_proxies': user_proxy_performance,
                'total_owned': len(user_proxy_list)
            }

    def get_stats(self, requesting_user_id: str = None) -> Dict:
        """Get full statistics about proxy usage (owner sees ALL proxies)"""
        with _proxy_lock:
            is_owner_user = is_owner(int(requesting_user_id)) if requesting_user_id else False
            
            # Calculate overall stats
            proxy_performance = []
            
            for proxy, stats in self.proxy_stats.items():
                # Owner sees ALL proxies, regular users see only their own
                proxy_owner = stats.get('owner', 'global')
                
                if not is_owner_user and proxy_owner != requesting_user_id:
                    continue  # Regular users only see their own proxies
                    
                success = stats.get('success', 0)
                fails = stats.get('fails', 0)
                total = success + fails
                rate = (success / total * 100) if total > 0 else 0
                
                proxy_performance.append({
                    'proxy': proxy,  # Complete proxy shown
                    'success': success,
                    'fails': fails,
                    'rate': rate,
                    'response_time': stats.get('response_time', 0),
                    'site': stats.get('site', 'Unknown'),
                    'status': '✅' if proxy not in self.dead_proxies else '❌',
                    'owner': proxy_owner,
                    'is_owner': is_owner_user
                })

            proxy_performance.sort(key=lambda x: x['rate'], reverse=True)

            available_proxies = [p for p in self.valid_proxies if p not in self.dead_proxies]
            
            return {
                'total_valid': len(self.valid_proxies),
                'total_user': len(self.user_proxy_map),
                'total_dead': len(self.perm_dead_proxies),
                'temp_dead': len(self.dead_proxies),
                'available_now': len(available_proxies),
                'top_proxies': proxy_performance[:10],
                'last_validation': self.last_validation,
                'validation_in_progress': self.validation_in_progress,
                'is_owner': is_owner_user
            }

    def trigger_validation(self):
        """Trigger validation of all proxies"""
        if self.validation_in_progress:
            return "Validation already in progress"
        
        # Load new proxies from CSV
        new_proxies = self._load_proxies_from_csv()
        
        if new_proxies:
            # Start validation in background
            import threading
            validation_thread = threading.Thread(
                target=self._validate_proxy_batch_dual,
                args=(new_proxies, "system"),
                daemon=True
            )
            validation_thread.start()
            return f"Started validation of {len(new_proxies)} new proxies"
        else:
            return "No new proxies to validate"

# Global proxy manager instance
proxy_manager = ProxyManager()

# Helper functions for checker scripts - ADDED COMPATIBILITY FUNCTIONS
def get_proxy_for_user(user_id: int, strategy: str = "random") -> Optional[str]:
    return proxy_manager.get_proxy_for_user(user_id, strategy)

def mark_proxy_success(proxy: str, response_time: float):
    proxy_manager.mark_proxy_success(proxy, response_time)

def mark_proxy_failed(proxy: str):
    proxy_manager.mark_proxy_failed(proxy)

# NEW: Compatibility functions for old scripts
def get_random_proxy() -> Optional[str]:
    """Get random proxy (compatibility function)"""
    return proxy_manager.get_random_proxy()

def parse_proxy(proxy_str: str) -> Optional[Dict]:
    """Parse proxy string into components (compatibility function)"""
    if not proxy_str:
        return None
    
    # Remove http:// prefix if present
    proxy_str = proxy_str.replace('http://', '').replace('https://', '')
    
    # Try different formats
    # Format: user:pass@host:port
    match1 = re.match(r'^(.+?):(.+?)@(.+?):(\d+)$', proxy_str)
    if match1:
        user, password, host, port = match1.groups()
        return {
            'username': user,
            'password': password,
            'host': host,
            'port': int(port)
        }
    
    # Format: host:port:user:pass
    match2 = re.match(r'^(.+?):(\d+):(.+?):(.+)$', proxy_str)
    if match2:
        host, port, user, password = match2.groups()
        return {
            'username': user,
            'password': password,
            'host': host,
            'port': int(port)
        }
    
    # Format: host:port (no auth)
    match3 = re.match(r'^(.+?):(\d+)$', proxy_str)
    if match3:
        host, port = match3.groups()
        return {
            'username': '',
            'password': '',
            'host': host,
            'port': int(port)
        }
    
    return None

def get_proxy_from_pool() -> Optional[str]:
    """Get proxy from pool (compatibility function)"""
    return proxy_manager.get_random_proxy()

def rotate_proxy() -> Optional[str]:
    """Rotate proxy (compatibility function)"""
    # This is just an alias for get_random_proxy in the new system
    return proxy_manager.get_random_proxy()

def test_proxy(proxy_str: str) -> bool:
    """Test if proxy is working (compatibility function)"""
    try:
        proxy_url = proxy_manager.normalize_proxy(proxy_str)
        if not proxy_url:
            return False
        
        is_valid, _, _, _ = proxy_manager.validate_single_proxy(proxy_str)
        return is_valid
    except:
        return False

# Proxy enabled flag for compatibility
PROXY_ENABLED = True

# ==============================================
# NEW COMMAND HANDLERS
# ==============================================

@Client.on_message(filters.command(["addpx", ".addpx"]))
@auth_and_free_restricted
async def add_proxy_command(client, message: Message):
    """Add proxies (single or bulk via text/file) - AVAILABLE TO ALL USERS"""

    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    # Check for attached document
    if message.document:
        if message.document.file_size > 1024 * 1024:  # 1MB limit
            await message.reply("""<pre>📁 File Too Large</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: File must be less than 1MB.
⟐ <b>Tip</b>: <code>Upload a .txt file with one proxy per line</code>
━━━━━━━━━━━━━""")
            return

        msg = await message.reply("<pre>📥 Downloading proxy file...</pre>")

        try:
            # Download the file
            file_path = await message.download()

            # Read proxies from file
            with open(file_path, 'r') as f:
                proxies_text = f.read()

            # Clean up
            os.remove(file_path)

            await msg.edit("<pre>🔍 Adding proxies from file...</pre>")

        except Exception as e:
            await msg.edit(f"""<pre>❌ File Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to read file.
⟐ <b>Error</b>: <code>{str(e)[:100]}</code>
━━━━━━━━━━━━━""")
            return

    # Check for text in message
    elif len(message.command) > 1:
        proxies_text = message.text.split(maxsplit=1)[1]
        msg = await message.reply("<pre>🔍 Adding proxies from text...</pre>")

    else:
        await message.reply("""<pre>#WAYNE 〔/addpx〕</pre>
━━━━━━━━━━━━━
<pre>Add proxies to your personal pool</pre>
<pre>Methods:</pre>
1. <code>/addpx proxy1:port</code> (single)
2. <code>/addpx proxy1:port\\nproxy2:port</code> (multiple lines)
3. <b>Send .txt file</b> with /addpx command (one proxy per line)
━━━━━━━━━━━━━
<pre>Formats Supported:</pre>
<code>• ip:port</code>
<code>• user:pass@ip:port</code>
<code>• ip:port:user:pass</code> (NEW: supports your format!)
<code>• http://ip:port</code>
━━━━━━━━━━━━━
<pre>Examples:</pre>
<code>/addpx 204.12.199.52:8888:user_8786443f:T5f1464aSzM1FGSj</code>
<code>/addpx user:pass@proxy.com:8080</code>
<code>/addpx 192.168.1.1:8080</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Proxies auto-validate and are added to YOUR personal pool</code>
<b>~ Note:</b> <code>Only you can see and use your own proxies</code>
<b>~ Note:</b> <code>Available for all users in authorized groups</code>""")
        return

    # Process proxies with user ownership
    user_id_str = str(message.from_user.id)
    result = proxy_manager.add_proxies_bulk(proxies_text, user_id_str)

    if result['total'] == 0:
        await msg.edit("""<pre>⚠️ No Proxies Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: No valid proxy formats found in input.
⟐ <b>Tip</b>: <code>Check your proxy format (ip:port:user:pass or user:pass@ip:port)</code>
━━━━━━━━━━━━━""")
        return

    # Get user's stats
    user_stats = proxy_manager.get_stats_for_user(user_id_str)

    await msg.edit(f"""<pre>✅ Proxies Added to Your Pool</pre>
━━━━━━━━━━━━━
<b>Processing Results:</b>
⟐ Total Input: <code>{result['total']}</code>
⟐ New Proxies: <code>{result['new']}</code>
⟐ Duplicates: <code>{result['duplicate']}</code>
━━━━━━━━━━━━━
<b>Your Pool Status:</b>
⟐ Your Valid Proxies: <code>{user_stats['total_valid']}</code>
⟐ Available Now: <code>{user_stats['available_now']}</code>
⟐ Dead Proxies: <code>{user_stats['total_dead']}</code>
⟐ Total Owned: <code>{user_stats['total_owned']}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Proxies validated with dual-site check (ipinfo.io + httpbin.org)</code>
<b>~ Note:</b> <code>Only YOU can see and use these proxies (complete details shown to you)</code>
<b>~ Tip:</b> <code>Use /vpx to validate specific proxies</code>""")

@Client.on_message(filters.command(["rmvpx", ".rmvpx"]))
@auth_and_free_restricted
async def remove_proxy_command(client, message: Message):
    """Remove proxies (single or bulk) - AVAILABLE TO ALL USERS (only own proxies)"""

    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    # Check for attached document
    if message.document:
        msg = await message.reply("<pre>📥 Downloading proxy file...</pre>")

        try:
            file_path = await message.download()
            with open(file_path, 'r') as f:
                proxies_text = f.read()
            os.remove(file_path)
            await msg.edit("<pre>🔍 Removing your proxies from file...</pre>")
        except Exception as e:
            await msg.edit(f"""<pre>❌ File Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to read file.
⟐ <b>Error</b>: <code>{str(e)[:100]}</code>
━━━━━━━━━━━━━""")
            return

    # Check for text in message
    elif len(message.command) > 1:
        proxies_text = message.text.split(maxsplit=1)[1]
        msg = await message.reply("<pre>🔍 Removing your proxies...</pre>")

    else:
        await message.reply("""<pre>#WAYNE 〔/rmvpx〕</pre>
━━━━━━━━━━━━━
<pre>Remove YOUR proxies from your pool</pre>
<pre>Methods:</pre>
1. <code>/rmvpx proxy1:port</code> (single)
2. <code>/rmvpx proxy1:port\\nproxy2:port</code> (multiple)
3. <b>Send .txt file</b> with /rmvpx command
━━━━━━━━━━━━━
<pre>Note:</b> You can only remove YOUR OWN proxies</pre>
<b>~ Note:</b> <code>Available for all users in authorized groups</code>""")
        return

    # Remove proxies (user can only remove their own)
    user_id_str = str(message.from_user.id)
    result = proxy_manager.remove_proxies_bulk(proxies_text, user_id_str)

    await msg.edit(f"""<pre>{'✅ Your Proxies Removed' if result['removed'] > 0 else '⚠️ No Proxies Removed'}</pre>
━━━━━━━━━━━━━
<b>Removal Results:</b>
⟐ Requested: <code>{result['requested']}</code>
⟐ Removed (Yours): <code>{result['removed']}</code>
⟐ Your Remaining: <code>{result['remaining']}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>You can only remove proxies that YOU own</code>
<b>~ Note:</b> <code>Use /addpx to add new proxies to your pool</code>""")

@Client.on_message(filters.command(["rmvall", ".rmvall"]))
@auth_and_free_restricted
async def remove_all_proxies_command(client, message: Message):
    """Remove ALL proxies - OWNER ONLY"""

    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    # Check if owner
    if not is_owner(message.from_user.id):
        await message.reply("""<pre>🚫 Owner Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for owner only.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    # Confirmation button would be better, but for simplicity:
    if len(message.command) < 2 or message.command[1].lower() != "confirm":
        await message.reply("""<pre>⚠️ CONFIRMATION REQUIRED</pre>
━━━━━━━━━━━━━
<b>WARNING:</b> This will remove ALL proxies from global pool!
<b>Action:</b> Clears all valid, dead, and temporary proxies
<b>CSV File:</b> Will be emptied
<b>Stats:</b> Will be reset
<b>User Proxies:</b> Will be removed for ALL users
━━━━━━━━━━━━━
<pre>To confirm, type:</pre>
<code>/rmvall confirm</code>
━━━━━━━━━━━━━
<b>This action cannot be undone!</b>""")
        return

    msg = await message.reply("<pre>🗑️ Removing ALL proxies...</pre>")

    # Get count before removal
    stats_before = proxy_manager.get_stats(str(message.from_user.id))

    # Remove all
    removed_count = proxy_manager.remove_all_proxies()

    await msg.edit(f"""<pre>✅ All Proxies Cleared</pre>
━━━━━━━━━━━━━
<b>Removal Summary:</b>
⟐ Valid Proxies: <code>{stats_before['total_valid']} → 0</code>
⟐ Dead Proxies: <code>{stats_before['total_dead']} → 0</code>
⟐ Temp Dead: <code>{stats_before['temp_dead']} → 0</code>
⟐ Total Removed: <code>{removed_count}</code>
━━━━━━━━━━━━━
<b>CSV File:</b> <code>Cleared</code>
<b>Valid Proxies File:</b> <code>Cleared</code>
<b>Stats File:</b> <code>Reset</code>
<b>User Proxies:</b> <code>Cleared for all users</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Proxy pool is now empty. Users can add new proxies with /addpx</code>""")

@Client.on_message(filters.command(["vpx", ".vpx"]))
@auth_and_free_restricted
async def validate_proxy_command(client, message: Message):
    """Validate specific proxies - AVAILABLE TO ALL USERS (shows complete proxy to user)"""

    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    if len(message.command) < 2:
        usage = """<pre>#WAYNE 〔/vpx〕 - Proxy Validation</pre>
━━━━━━━━━━━━━
<pre>Validate proxies with dual-site check</pre>
<pre>Methods:</pre>
1. <code>/vpx proxy1:port</code> (single)
2. <code>/vpx proxy1:port\\nproxy2:port</code> (multiple)
3. <b>Send .txt file</b> with /vpx command
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Shows complete proxy details (no masking)</code>
<b>~ Note:</b> <code>Available for all users in authorized groups</code>"""

        await message.reply(usage)
        return

    # Check for attached document
    if message.document:
        msg = await message.reply("<pre>📥 Downloading proxy file...</pre>")

        try:
            file_path = await message.download()
            with open(file_path, 'r') as f:
                proxies_text = f.read()
            os.remove(file_path)
        except Exception as e:
            await msg.edit(f"""<pre>❌ File Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to read file.
⟐ <b>Error</b>: <code>{str(e)[:100]}</code>
━━━━━━━━━━━━━""")
            return
    else:
        proxies_text = message.text.split(maxsplit=1)[1]
        msg = await message.reply("<pre>🔍 Validating proxies...</pre>")

    # Parse proxies
    lines = proxies_text.strip().split('\n')
    proxies_to_test = []
    
    user_id_str = str(message.from_user.id)

    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            proxy = proxy_manager.normalize_proxy(line)
            if proxy:
                proxies_to_test.append((line, proxy))

    if not proxies_to_test:
        await msg.edit("""<pre>❌ No Valid Formats</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: No valid proxy formats found.
⟐ <b>Tip</b>: <code>Use ip:port:user:pass or user:pass@ip:port format</code>
━━━━━━━━━━━━━""")
        return

    # Test each proxy
    results = []

    for original, proxy_url in proxies_to_test:
        is_valid, info, response_time, site = proxy_manager.validate_single_proxy(original, user_id_str)

        # User sees complete proxy (no masking)
        display = proxy_url

        results.append({
            'proxy': display,  # Complete proxy shown
            'full_proxy': proxy_url,
            'valid': is_valid,
            'info': info,
            'time': response_time,
            'site': site
        })

    # Format results
    valid_count = sum(1 for r in results if r['valid'])

    response = f"""<pre>📊 Validation Results</pre>
━━━━━━━━━━━━━
<b>Summary:</b>
⟐ Tested: <code>{len(results)}</code>
⟐ Valid: <code>{valid_count}</code> ✅
⟐ Invalid: <code>{len(results) - valid_count}</code> ❌
━━━━━━━━━━━━━
<b>Detailed Results:</b>\n"""

    for i, r in enumerate(results[:10], 1):  # Show first 10
        status = "✅" if r['valid'] else "❌"
        response += f"{i}. {status} <code>{r['proxy']}</code>\n"
        if r['valid']:
            response += f"   → {r['info']} | {r['time']:.2f}s | {r['site']}\n"
        else:
            response += f"   → {r['info']}\n"

    if len(results) > 10:
        response += f"\n... and {len(results) - 10} more proxies\n"

    response += "━━━━━━━━━━━━━\n"
    response += "<b>~ Note:</b> <code>Valid proxies added to your personal pool</code>"
    response += "\n<b>~ Note:</b> <code>Only you can see and use these proxies (complete details shown)</code>"

    await msg.edit(response)

@Client.on_message(filters.command(["pxstats", ".pxstats"]))
@auth_and_free_restricted
async def proxy_stats_handler(client, message: Message):
    """Show detailed proxy statistics - OWNER ONLY with auto-validation"""

    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    # Check if owner
    if not is_owner(message.from_user.id):
        # Show user their own stats instead of owner stats
        user_id_str = str(message.from_user.id)
        user_stats = proxy_manager.get_stats_for_user(user_id_str)
        
        response = f"""<pre>📊 Your Proxy Statistics</pre>
━━━━━━━━━━━━━━━
<b>Your Pool Status:</b>
⟐ Your Valid Proxies: <code>{user_stats['total_valid']}</code>
⟐ Available Now: <code>{user_stats['available_now']}</code>
⟐ Dead Proxies: <code>{user_stats['total_dead']}</code>
⟐ Temporary Dead: <code>{user_stats['temp_dead']}</code>
⟐ Total Owned: <code>{user_stats['total_owned']}</code>
━━━━━━━━━━━━━━━
<b>Your Proxies (Complete Details):</b>\n"""

        for i, proxy_data in enumerate(user_stats['user_proxies'][:5], 1):
            proxy = proxy_data['proxy']  # Complete proxy shown
            success = proxy_data['success']
            fails = proxy_data['fails']
            rate = proxy_data['rate']
            rt = proxy_data['response_time']
            site = proxy_data.get('site', 'Unknown')
            status = proxy_data['status']
            valid = "✅ Valid" if proxy_data['valid'] else "❌ Invalid"
            
            response += f"{i}. {status} <code>{proxy}</code>\n"
            response += f"   → {valid} | {rate:.1f}% | {rt:.2f}s | {site} | {success}✅ {fails}❌\n"

        if len(user_stats['user_proxies']) > 5:
            response += f"\n... and {len(user_stats['user_proxies']) - 5} more of your proxies\n"

        response += "━━━━━━━━━━━━━━━\n"
        response += "<b>~ Note:</b> <code>You can only see your own proxies</code>"
        response += "\n<b>~ Note:</b> <code>Owner can see ALL proxies with /pxstats</code>"
        response += "\n<b>~ Note:</b> <code>Use /addpx to add more proxies</code>"
        
        await message.reply(response)
        return

    msg = await message.reply("<pre>🔄 Triggering proxy validation...</pre>")
    
    # Trigger auto-validation (owner only)
    validation_msg = proxy_manager.trigger_validation()
    
    # Wait a bit for validation to start
    await asyncio.sleep(2)
    
    # Get stats with owner view (sees ALL proxies)
    user_id_str = str(message.from_user.id)
    stats = proxy_manager.get_stats(user_id_str)

    response = f"""<pre>📊 Proxy Statistics (👑 Owner View - ALL PROXIES)</pre>
━━━━━━━━━━━━━━━
<b>Global Pool Status:</b>
⟐ Valid Proxies: <code>{stats['total_valid']}</code>
⟐ Available Now: <code>{stats['available_now']}</code>
⟐ User Proxies: <code>{stats['total_user']}</code>
⟐ Dead Proxies: <code>{stats['total_dead']}</code>
⟐ Temporary Dead: <code>{stats['temp_dead']}</code>
<b>Auto-Validation:</b> <code>{validation_msg}</code>
━━━━━━━━━━━━━━━
<b>Top Performing Proxies (Complete Details):</b>\n"""

    for i, proxy_data in enumerate(stats['top_proxies'][:5], 1):
        proxy = proxy_data['proxy']  # Complete proxy shown to owner
        success = proxy_data['success']
        fails = proxy_data['fails']
        rate = proxy_data['rate']
        rt = proxy_data['response_time']
        site = proxy_data.get('site', 'Unknown')
        status = proxy_data['status']
        owner = proxy_data.get('owner', 'global')

        # Show ownership indicator
        owner_indicator = "👑" if owner == "system" else "👤" if owner != "global" else "🌍"
        
        response += f"{i}. {status} {owner_indicator} <code>{proxy}</code>\n"
        response += f"   → {rate:.1f}% | {rt:.2f}s | {site} | {success}✅ {fails}❌ | Owner: {owner}\n"

    response += "━━━━━━━━━━━━━━━\n"

    if stats['validation_in_progress']:
        response += "<b>🔄 Validation in progress...</b>\n"
    else:
        mins_ago = (time.time() - stats['last_validation']) / 60 if stats['last_validation'] else 999
        response += f"<b>Last Validation:</b> <code>{mins_ago:.1f} minutes ago</code>\n"

    response += "<b>Test Method:</b> Dual-site (ipinfo.io → httpbin.org)\n"
    response += "<b>Proxy Visibility:</b> Users see their own complete proxies only\n"
    response += "<b>Owner Sees:</b> ALL proxies with complete details\n"
    response += "<b>~ Note:</b> <code>Auto-validation triggered on /pxstats command (Owner Only)</code>"

    await msg.edit(response)
