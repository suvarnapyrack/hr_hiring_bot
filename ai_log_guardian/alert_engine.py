import time
import hashlib
import json
import logging

logger = logging.getLogger("AlertEngine")

class AlertEngine:
    def __init__(self, throttle_seconds=300):
        self.throttle_seconds = throttle_seconds
        self.sent_alerts = {} # hash -> last_sent_timestamp

    def should_trigger(self, container_name, log_content):
        """
        Determines if an alert should be triggered based on throttling.
        Uses a hash of the container name and the error message (simplified).
        """
        # Create a signature for the error to avoid spamming the same error
        # We'll take the first 50 chars of the log content to group similar errors
        error_sig = f"{container_name}:{log_content[:50]}"
        content_hash = hashlib.md5(error_sig.encode()).hexdigest()
        
        current_time = time.time()
        last_sent = self.sent_alerts.get(content_hash, 0)
        
        if current_time - last_sent > self.throttle_seconds:
            self.sent_alerts[content_hash] = int(current_time)
            return True, self.generate_incident_id(content_hash)
        
        return False, None

    def generate_incident_id(self, content_hash):
        timestamp = int(time.time())
        return f"INC-{timestamp}-{content_hash[:6].upper()}"

if __name__ == "__main__":
    # Test logic
    engine = AlertEngine(throttle_seconds=5)
    print(engine.should_trigger("app", "Error 1")) # True
    print(engine.should_trigger("app", "Error 1")) # False
    time.sleep(6)
    print(engine.should_trigger("app", "Error 1")) # True
