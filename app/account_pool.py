import time
import threading
from typing import Dict, List

from app.logger import logger
from app.notion_client import NotionOpusAPI

class AccountPool:
    def __init__(self, accounts: List[dict]):
        """
        Initialize from a list of account config dicts, one per credential set.
        Also initializes each client instance and its state.
        """
        if not accounts:
            raise ValueError("Account pool initialization failed: no account configuration provided.")
            
        self.clients = [NotionOpusAPI(acc) for acc in accounts]
        # Cooldown release timestamps per client (0 means available)
        self.cooldown_until = [0.0 for _ in self.clients]
        
        # Round-Robin index
        self._current_index = 0
        self._lock = threading.Lock()
        
    def get_client(self, wait_if_cooling: bool = True) -> NotionOpusAPI:
        """
        Return the next available client using Round-Robin.
        Skips clients that are currently in their cooldown period.

        If wait_if_cooling=True (default) and all accounts are cooling,
        waits for the soonest cooldown to expire instead of raising.
        """
        now = time.time()
        with self._lock:
            start_index = self._current_index
            
            while True:
                idx = self._current_index
                # Available if past its cooldown time
                if self.cooldown_until[idx] <= now:
                    # Advance round-robin index
                    self._current_index = (self._current_index + 1) % len(self.clients)
                    return self.clients[idx]
                    
                # Not available — move to next
                self._current_index = (self._current_index + 1) % len(self.clients)
                
                # Full loop with no available client
                if self._current_index == start_index:
                    next_available = min(self.cooldown_until)
                    wait_seconds = max(0.5, next_available - now)

                    if wait_if_cooling and wait_seconds <= 15:
                        # Wait for cooldown to expire then retry
                        logger.info(
                            f"All accounts cooling, waiting {wait_seconds:.1f}s",
                            extra={
                                "request_info": {
                                    "event": "account_pool_wait_cooling",
                                    "wait_seconds": round(wait_seconds, 1),
                                }
                            },
                        )
                        # Release lock before sleeping to avoid blocking other threads
                        self._lock.release()
                        try:
                            time.sleep(wait_seconds)
                        finally:
                            self._lock.acquire()
                        # Refresh timestamp and re-scan
                        now = time.time()
                        continue

                    raise RuntimeError(
                        f"All accounts are cooling down. Please retry in {max(1, int(wait_seconds))} second(s)."
                    )

    def get_status_summary(self) -> Dict[str, int]:
        """Return a brief status summary of the account pool for health checks and logging."""
        now = time.time()
        with self._lock:
            active = sum(1 for ts in self.cooldown_until if ts <= now)
            cooling = len(self.cooldown_until) - active
            return {
                "total": len(self.clients),
                "active": active,
                "cooling": cooling,
            }
                    
    def mark_failed(self, client: NotionOpusAPI, cooldown_seconds: int = 3):
        """
        Mark a client as temporarily unavailable (default: 3-second cooldown).
        """
        with self._lock:
            try:
                idx = self.clients.index(client)
                # Record the future timestamp when this client becomes available again
                self.cooldown_until[idx] = time.time() + cooldown_seconds
                logger.warning(
                    "Account marked as failed",
                    extra={
                        "request_info": {
                            "event": "account_failed",
                            "account": client.account_key,
                            "space_id": client.space_id,
                            "cooldown_seconds": cooldown_seconds,
                        }
                    },
                )
            except ValueError:
                logger.warning(
                    "Attempted to mark unknown account as failed",
                    extra={"request_info": {"event": "account_failed_unknown"}},
                )
