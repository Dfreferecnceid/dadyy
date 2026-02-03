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
        self.user_proxies: Dict[str, str] = {}  # User-specific personal proxies
        self.user_added_proxies: Dict[str, List[str]] = {}  # Track which user added which proxies
        self.valid_proxies: List[str] = []  # ALL valid proxies in system (global pool)
        self.dead_proxies: Set[str] = set()  # Temporarily dead proxies
        self.perm_dead_proxies: Set[str] = set()  # Permanently dead proxies
        self.proxy_stats: Dict[str, Dict] = {}
        self.validation_in_progress = False
        self.executor = ThreadPoolExecutor(max_workers=50)
        self.last_validation = 0
        self.last_cleanup = time.time()
        self.failure_threshold = 3  # Mark as dead after 3 consecutive failures

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
            # Load user-specific personal proxies
            if os.path.exists(PROXY_FILE):
                try:
                    with open(PROXY_FILE, "r") as f:
                        self.user_proxies = json.load(f)
                    print(f"✅ Loaded {len(self.user_proxies)} user-specific proxies")
                except Exception as e:
                    print(f"❌ Error loading user proxies: {e}")
                    self.user_proxies = {}

            # Load previously validated proxies (GLOBAL POOL)
            self._load_valid_proxies()

            # Load new proxies from CSV and validate them
            new_proxies = self._load_proxies_from_csv()

            if new_proxies:
                print(f"📥 Found {len(new_proxies)} new proxies in CSV, validating with dual-site check...")
                self._validate_proxy_batch_dual(new_proxies)
            else:
                print(f"⚠️ No proxies found in {GLOBAL_PROXY_FILE}")

            # Save validated proxies
            self._save_valid_proxies()

            # Clean dead proxies on startup
            self._clean_dead_proxies()
            
            print(f"🎯 Proxy Manager Ready: {len(self.valid_proxies)} valid proxies available in global pool")

    def _load_valid_proxies(self):
        """Load previously validated working proxies"""
        try:
            if os.path.exists(VALID_PROXY_FILE):
                with open(VALID_PROXY_FILE, "r") as f:
                    data = json.load(f)
                    self.valid_proxies = data.get('valid', [])
                    self.perm_dead_proxies = set(data.get('dead', []))
                    self.proxy_stats = data.get('stats', {})
                    self.user_added_proxies = data.get('user_added', {})
                print(f"📂 Loaded {len(self.valid_proxies)} pre-validated proxies")
                print(f"📂 Loaded {len(self.perm_dead_proxies)} known dead proxies")
        except Exception as e:
            print(f"❌ Error loading validated proxies: {e}")
            self.valid_proxies = []
            self.perm_dead_proxies = set()
            self.proxy_stats = {}
            self.user_added_proxies = {}

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
                    proxy not in self.perm_dead_proxies):
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

    def _validate_proxy_batch_dual(self, proxies: List[str]):
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
                        self.valid_proxies.append(proxy)
                        self.proxy_stats[proxy] = {
                            'success': 1,
                            'fails': 0,
                            'response_time': result[1],
                            'ip': result[2],
                            'site': result[3],
                            'last_used': time.time(),
                            'last_validated': time.time()
                        }
                        valid_count += 1
                        print(f"✅ Proxy validated via {result[3]}: {proxy[:50]}...")
                    else:
                        self.perm_dead_proxies.add(proxy)
                        dead_count += 1
                        print(f"❌ Proxy dead: {proxy[:50]}...")

                except Exception as e:
                    self.perm_dead_proxies.add(proxy)
                    dead_count += 1
                    print(f"❌ Proxy error: {proxy[:50]}... - {str(e)[:50]}")

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
                'user_added': self.user_added_proxies,
                'last_updated': time.time()
            }

            with open(VALID_PROXY_FILE, "w") as f:
                json.dump(data, f, indent=2)

            print(f"💾 Saved {len(self.valid_proxies)} valid proxies to {VALID_PROXY_FILE}")

        except Exception as e:
            print(f"❌ Error saving validated proxies: {e}")

    def get_proxy_for_user(self, user_id: int, strategy: str = "random") -> Optional[str]:
        """Get proxy for user (personal proxy → valid global proxy → None)"""
        with _proxy_lock:
            # Clean dead proxies first
            self._clean_dead_proxies()

            # 1. Check user-specific personal proxy first
            user_str = str(user_id)
            if user_str in self.user_proxies:
                personal_proxy = self.user_proxies[user_str]
                # Check if personal proxy is still valid
                if (personal_proxy in self.valid_proxies and 
                    personal_proxy not in self.dead_proxies and 
                    personal_proxy not in self.perm_dead_proxies):
                    self._update_stats(personal_proxy)
                    return personal_proxy
                else:
                    # Personal proxy is dead, remove it
                    print(f"⚠️ Personal proxy for user {user_id} is dead, removing...")
                    self.user_proxies.pop(user_str, None)
                    self.save_user_proxies()

            # 2. Get from global pool - FILTER OUT ALL DEAD PROXIES
            available_proxies = [
                p for p in self.valid_proxies 
                if p not in self.dead_proxies and p not in self.perm_dead_proxies
            ]

            if not available_proxies:
                # No available proxies, try to revive some
                self._revive_proxies()
                available_proxies = [
                    p for p in self.valid_proxies 
                    if p not in self.dead_proxies and p not in self.perm_dead_proxies
                ]
                
                if not available_proxies:
                    return None

            # 3. Select based on strategy
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
            self.proxy_stats[proxy] = {
                'success': 0,
                'fails': 0,
                'response_time': 5.0,
                'ip': 'Unknown',
                'site': 'Unknown',
                'last_used': time.time(),
                'last_validated': time.time()
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
                # Reset fail count on success
                self.proxy_stats[proxy]['fails'] = 0
                self.proxy_stats[proxy]['last_validated'] = time.time()

    def mark_proxy_failed(self, proxy: str):
        """Mark proxy as failed (temporarily dead)"""
        with _proxy_lock:
            if proxy in self.proxy_stats:
                self.proxy_stats[proxy]['fails'] += 1
                if self.proxy_stats[proxy]['fails'] >= self.failure_threshold:
                    self.dead_proxies.add(proxy)
                    print(f"⚠️ Marked proxy as dead after {self.failure_threshold} failures: {proxy[:50]}...")
                    # If consistently failing, mark as permanently dead
                    if self.proxy_stats[proxy]['fails'] >= self.failure_threshold * 2:
                        self.perm_dead_proxies.add(proxy)
                        self.dead_proxies.discard(proxy)
                        if proxy in self.valid_proxies:
                            self.valid_proxies.remove(proxy)
                        print(f"🗑️ Moved proxy to permanently dead: {proxy[:50]}...")

    def _clean_dead_proxies(self):
        """Remove old dead proxies after timeout"""
        current = time.time()
        if current - self.last_cleanup < 300:  # 5 minutes
            return

        to_remove = set()
        for proxy in self.dead_proxies:
            if proxy in self.proxy_stats:
                last_validated = self.proxy_stats[proxy].get('last_validated', 0)
                if current - last_validated > 1800:  # 30 minutes
                    to_remove.add(proxy)
                    # If still dead after 30 minutes, mark as permanently dead
                    self.perm_dead_proxies.add(proxy)
                    if proxy in self.valid_proxies:
                        self.valid_proxies.remove(proxy)
                    print(f"🗑️ Auto-removed permanently dead proxy: {proxy[:50]}...")

        self.dead_proxies -= to_remove
        
        # Also clean old permanently dead proxies
        self._clean_old_permanent_dead()
        
        self.last_cleanup = current

    def _clean_old_permanent_dead(self):
        """Clean old permanently dead proxies from memory (keep only recent ones)"""
        current = time.time()
        old_dead = set()
        
        # We'll keep permanent dead records for 24 hours only
        for proxy in self.perm_dead_proxies:
            if proxy in self.proxy_stats:
                last_used = self.proxy_stats[proxy].get('last_used', 0)
                if current - last_used > 86400:  # 24 hours
                    old_dead.add(proxy)
        
        if old_dead:
            self.perm_dead_proxies -= old_dead
            print(f"🧹 Cleared {len(old_dead)} old permanently dead proxies")

    def _revive_proxies(self):
        """Try to revive some dead proxies if pool is empty"""
        if not self.dead_proxies:
            return
            
        print(f"🔄 Trying to revive {len(self.dead_proxies)} dead proxies...")
        
        revived = 0
        proxies_to_test = list(self.dead_proxies)[:10]  # Test only 10 at a time
        
        for proxy in proxies_to_test:
            is_valid, _, _, _ = self._test_proxy_dual_sync(proxy)
            if is_valid:
                self.dead_proxies.remove(proxy)
                if proxy not in self.valid_proxies:
                    self.valid_proxies.append(proxy)
                self.proxy_stats[proxy]['fails'] = 0
                self.proxy_stats[proxy]['last_validated'] = time.time()
                revived += 1
                print(f"✅ Revived proxy: {proxy[:50]}...")
        
        if revived > 0:
            print(f"🎉 Revived {revived} proxies")
            self._save_valid_proxies()

    def save_user_proxies(self):
        """Save user-specific proxies to file"""
        try:
            with open(PROXY_FILE, "w") as f:
                json.dump(self.user_proxies, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving user proxies: {e}")

    def validate_single_proxy(self, proxy_raw: str) -> Tuple[bool, str, float, str]:
        """Validate a single proxy immediately with dual-site check"""
        proxy_url = self.normalize_proxy(proxy_raw)

        if not proxy_url:
            return False, "Invalid format", 0.0, "Invalid"

        # Check if already known as permanently dead
        if proxy_url in self.perm_dead_proxies:
            return False, "Previously marked as permanently dead", 0.0, "Cached"

        # Check if already known as valid
        if proxy_url in self.valid_proxies and proxy_url not in self.dead_proxies:
            stats = self.proxy_stats.get(proxy_url, {})
            return True, f"Already valid ({stats.get('site', 'Unknown')})", stats.get('response_time', 0.0), "Cached"

        # Test the proxy with dual sites
        is_valid, response_time, ip, site = self._test_proxy_dual_sync(proxy_url)

        if is_valid:
            with _proxy_lock:
                if proxy_url not in self.valid_proxies:
                    self.valid_proxies.append(proxy_url)
                self.proxy_stats[proxy_url] = {
                    'success': 1,
                    'fails': 0,
                    'response_time': response_time,
                    'ip': ip,
                    'site': site,
                    'last_used': time.time(),
                    'last_validated': time.time()
                }
                # Remove from dead lists if present
                self.dead_proxies.discard(proxy_url)
                self.perm_dead_proxies.discard(proxy_url)
                self._save_valid_proxies()
            return True, ip, response_time, site
        else:
            with _proxy_lock:
                self.perm_dead_proxies.add(proxy_url)
                self._save_valid_proxies()
            return False, f"Failed on both sites", response_time, "Failed"

    def add_proxies_bulk(self, proxies_text: str, user_id: Optional[int] = None) -> Dict[str, int]:
        """Add multiple proxies from text (bulk addition)"""
        lines = proxies_text.strip().split('\n')
        normalized_proxies = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                proxy = self.normalize_proxy(line)
                if proxy:
                    normalized_proxies.append(proxy)

        # Filter out already known as permanently dead
        new_proxies = []
        for proxy in normalized_proxies:
            if proxy not in self.perm_dead_proxies:
                new_proxies.append(proxy)

        if not new_proxies:
            return {'total': 0, 'new': 0, 'duplicate': len(normalized_proxies)}

        # Track user who added proxies
        user_str = str(user_id) if user_id else "system"
        if user_str not in self.user_added_proxies:
            self.user_added_proxies[user_str] = []
        
        for proxy in new_proxies:
            if proxy not in self.user_added_proxies[user_str]:
                self.user_added_proxies[user_str].append(proxy)

        # Validate new proxies
        self._validate_proxy_batch_dual(new_proxies)
        self._save_valid_proxies()

        stats = self.get_stats()
        return {
            'total': len(normalized_proxies),
            'new': len(new_proxies),
            'duplicate': len(normalized_proxies) - len(new_proxies),
            'valid_now': stats['total_valid'],
            'available_now': stats['available_now']
        }

    def remove_proxies_bulk(self, proxies_text: str, user_id: Optional[int] = None) -> Dict[str, int]:
        """Remove multiple proxies from text"""
        lines = proxies_text.strip().split('\n')
        normalized_proxies = []

        for line in lines:
            line = line.strip()
            if line:
                proxy = self.normalize_proxy(line)
                if proxy:
                    normalized_proxies.append(proxy)

        removed_count = 0
        user_str = str(user_id) if user_id else "system"
        
        with _proxy_lock:
            for proxy in normalized_proxies:
                # Remove from valid proxies
                if proxy in self.valid_proxies:
                    self.valid_proxies.remove(proxy)
                    removed_count += 1

                # Remove from user added tracking
                if user_str in self.user_added_proxies and proxy in self.user_added_proxies[user_str]:
                    self.user_added_proxies[user_str].remove(proxy)

                # Remove from stats
                if proxy in self.proxy_stats:
                    del self.proxy_stats[proxy]

                # Remove from dead sets
                self.dead_proxies.discard(proxy)
                self.perm_dead_proxies.discard(proxy)

        if removed_count > 0:
            self._save_valid_proxies()

        return {
            'requested': len(normalized_proxies),
            'removed': removed_count,
            'remaining': len(self.valid_proxies)
        }

    def remove_all_proxies(self) -> int:
        """Remove all proxies from global pool"""
        with _proxy_lock:
            removed_count = len(self.valid_proxies)
            self.valid_proxies = []
            self.dead_proxies = set()
            self.perm_dead_proxies = set()
            self.proxy_stats = {}
            self.user_added_proxies = {}

            # Also clear CSV file
            try:
                open(GLOBAL_PROXY_FILE, 'w').close()
            except:
                pass

            self._save_valid_proxies()

        return removed_count

    def get_stats(self) -> Dict:
        """Get statistics about proxy usage"""
        with _proxy_lock:
            # Calculate success rates
            proxy_performance = []
            for proxy, stats in self.proxy_stats.items():
                success = stats.get('success', 0)
                fails = stats.get('fails', 0)
                total = success + fails
                rate = (success / total * 100) if total > 0 else 0
                proxy_performance.append({
                    'proxy': proxy,
                    'success': success,
                    'fails': fails,
                    'rate': rate,
                    'response_time': stats.get('response_time', 0),
                    'site': stats.get('site', 'Unknown'),
                    'status': '✅' if proxy not in self.dead_proxies and proxy not in self.perm_dead_proxies else '❌'
                })

            proxy_performance.sort(key=lambda x: x['rate'], reverse=True)

            # Count available proxies (not in any dead list)
            available_now = len([
                p for p in self.valid_proxies 
                if p not in self.dead_proxies and p not in self.perm_dead_proxies
            ])

            return {
                'total_valid': len(self.valid_proxies),
                'total_user': len(self.user_proxies),
                'total_dead': len(self.perm_dead_proxies),
                'temp_dead': len(self.dead_proxies),
                'available_now': available_now,
                'top_proxies': proxy_performance[:10],
                'last_validation': self.last_validation,
                'validation_in_progress': self.validation_in_progress,
                'failure_threshold': self.failure_threshold
            }

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
<pre>Add proxies to global pool</pre>
<pre>Methods:</pre>
1. <code>/addpx proxy1:port</code> (single)
2. <code>/addpx proxy1:port\\nproxy2:port</code> (multiple lines)
3. <b>Send .txt file</b> with /addpx command (one proxy per line)
━━━━━━━━━━━━━
<pre>Formats Supported:</pre>
<code>• ip:port</code>
<code>• user:pass@ip:port</code>
<code>• ip:port:user:pass</code>
<code>• http://ip:port</code>
━━━━━━━━━━━━━
<pre>Examples:</pre>
<code>/addpx 192.168.1.1:8080</code>
<code>/addpx user:pass@proxy.com:8080</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Proxies auto-validate and classify as good/bad</code>
<b>~ Note:</b> <code>Available for all users</code>""")
        return

    # Process proxies
    result = proxy_manager.add_proxies_bulk(proxies_text, message.from_user.id)

    if result['total'] == 0:
        await msg.edit("""<pre>⚠️ No Proxies Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: No valid proxy formats found in input.
⟐ <b>Tip</b>: <code>Check your proxy format (ip:port or user:pass@ip:port)</code>
━━━━━━━━━━━━━""")
        return

    # Get updated stats
    stats = proxy_manager.get_stats()

    await msg.edit(f"""<pre>✅ Proxies Added</pre>
━━━━━━━━━━━━━
<b>Processing Results:</b>
⟐ Total Input: <code>{result['total']}</code>
⟐ New Proxies: <code>{result['new']}</code>
⟐ Duplicates: <code>{result['duplicate']}</code>
━━━━━━━━━━━━━
<b>Current Pool Status:</b>
⟐ Valid Proxies: <code>{result['valid_now']}</code>
⟐ Available Now: <code>{result['available_now']}</code>
⟐ Known Dead: <code>{stats['total_dead']}</code>
━━━━━━━━━━━━━
<b>~ Tip:</b> <code>Use /vpx to validate specific proxies</code>""")

@Client.on_message(filters.command(["rmvpx", ".rmvpx"]))
@auth_and_free_restricted
async def remove_proxy_command(client, message: Message):
    """Remove proxies (single or bulk) - AVAILABLE TO ALL USERS"""

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
            await msg.edit("<pre>🔍 Removing proxies from file...</pre>")
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
        msg = await message.reply("<pre>🔍 Removing proxies from text...</pre>")

    else:
        await message.reply("""<pre>#WAYNE 〔/rmvpx〕</pre>
━━━━━━━━━━━━━
<pre>Remove proxies from global pool</pre>
<pre>Methods:</pre>
1. <code>/rmvpx proxy1:port</code> (single)
2. <code>/rmvpx proxy1:port\\nproxy2:port</code> (multiple)
3. <b>Send .txt file</b> with /rmvpx command
━━━━━━━━━━━━━
<pre>Note:</b> Removes only your added proxies from global pool</pre>
<b>~ Note:</b> <code>Available for all users</code>""")
        return

    # Remove proxies (only those added by this user)
    result = proxy_manager.remove_proxies_bulk(proxies_text, message.from_user.id)

    await msg.edit(f"""<pre>{'✅ Proxies Removed' if result['removed'] > 0 else '⚠️ No Proxies Removed'}</pre>
━━━━━━━━━━━━━
<b>Removal Results:</b>
⟐ Requested: <code>{result['requested']}</code>
⟐ Removed: <code>{result['removed']}</code>
⟐ Remaining: <code>{result['remaining']}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Only removes proxies you added to global pool</code>""")


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
━━━━━━━━━━━━━
<pre>To confirm, type:</pre>
<code>/rmvall confirm</code>
━━━━━━━━━━━━━
<b>This action cannot be undone!</b>""")
        return

    msg = await message.reply("<pre>🗑️ Removing ALL proxies...</pre>")

    # Get count before removal
    stats_before = proxy_manager.get_stats()

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
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Proxy pool is now empty. Add new proxies with /addpx</code>""")

@Client.on_message(filters.command(["vpx", ".vpx"]))
@auth_and_free_restricted
async def validate_proxy_command(client, message: Message):
    """Validate specific proxies - AVAILABLE TO ALL USERS"""

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
<b>~ Note:</b> <code>Available for all users</code>"""

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

    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            proxy = proxy_manager.normalize_proxy(line)
            if proxy:
                proxies_to_test.append((line, proxy))  # Keep original for display

    if not proxies_to_test:
        await msg.edit("""<pre>❌ No Valid Formats</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: No valid proxy formats found.
⟐ <b>Tip</b>: <code>Use ip:port or user:pass@ip:port format</code>
━━━━━━━━━━━━━""")
        return

    # Test each proxy
    results = []

    for original, proxy_url in proxies_to_test:
        is_valid, info, response_time, site = proxy_manager.validate_single_proxy(original)

        # Shorten for display
        if '@' in proxy_url:
            display = '...' + proxy_url.split('@')[-1][:30]
        else:
            display = proxy_url.replace('http://', '')[:30]

        results.append({
            'proxy': display,
            'original': original[:40],
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

    await msg.edit(response)

@Client.on_message(filters.command(["pxstats", ".pxstats"]))
@auth_and_free_restricted
async def proxy_stats_handler(client, message: Message):
    """Show detailed proxy statistics - OWNER ONLY"""

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

    stats = proxy_manager.get_stats()

    response = f"""<pre>📊 Proxy Statistics</pre>
━━━━━━━━━━━━━━━
<b>Pool Status:</b>
⟐ Valid Proxies: <code>{stats['total_valid']}</code>
⟐ Available Now: <code>{stats['available_now']}</code>
⟐ User Proxies: <code>{stats['total_user']}</code>
⟐ Dead Proxies: <code>{stats['total_dead']}</code>
⟐ Temporary Dead: <code>{stats['temp_dead']}</code>
━━━━━━━━━━━━━━━
<b>Proxy Health:</b>
⟐ Failure Threshold: <code>{stats['failure_threshold']} consecutive fails</code>
⟐ Auto-cleanup: <code>Every 5 minutes</code>
⟐ Permanent Dead: <code>After 30 minutes</code>
━━━━━━━━━━━━━━━
<b>Top Performing Proxies:</b>\n"""

    for i, proxy_data in enumerate(stats['top_proxies'][:5], 1):
        proxy = proxy_data['proxy']
        success = proxy_data['success']
        fails = proxy_data['fails']
        rate = proxy_data['rate']
        rt = proxy_data['response_time']
        site = proxy_data.get('site', 'Unknown')
        status = proxy_data['status']

        # Shorten for display
        if '@' in proxy:
            short_proxy = '...' + proxy.split('@')[-1][-25:]
        else:
            short_proxy = proxy.replace('http://', '')[:25]

        response += f"{i}. {status} <code>{short_proxy}</code>\n"
        response += f"   → {rate:.1f}% | {rt:.2f}s | {site} | {success}✅ {fails}❌\n"

    response += "━━━━━━━━━━━━━━━\n"

    if stats['validation_in_progress']:
        response += "<b>🔄 Validation in progress...</b>\n"
    else:
        mins_ago = (time.time() - stats['last_validation']) / 60 if stats['last_validation'] else 999
        response += f"<b>Last Validation:</b> <code>{mins_ago:.1f} minutes ago</code>\n"

    response += "<b>Test Method:</b>\n"
    response += "<b>Proxy Policy:</b> All gates use ALL valid proxies from global pool\n"
    response += "<b>Dead Proxy Handling:</b> Auto-removed after verification\n"
    response += "<b>~ Note:</b> <code>Owner Only Command</code>"

    await message.reply(response)
