import docker
import time
import logging
import json
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LogListener")

class LogListener:
    def __init__(self, container_names):
        self.client = docker.from_env()
        self.container_names = container_names
        self.error_keywords = ["ERROR", "CRITICAL", "FATAL", "EXCEPTION"]

    def stream_logs(self, callback):
        """
        Streams logs from specified containers and triggers callback on error events.
        """
        logger.info(f"Starting log stream for containers: {self.container_names}")
        
        last_poll = {name: time.time() - 30 for name in self.container_names}
        
        while True:
            now = time.time()
            for name in self.container_names:
                try:
                    container = self.client.containers.get(name)
                    # Get recent logs since the last poll timestamp
                    last_ts = last_poll.get(name, now - 30)
                    logs = container.logs(since=int(last_ts), timestamps=True).decode('utf-8')
                    last_poll[name] = now
                    
                    for line in logs.splitlines():
                        if any(keyword in line.upper() for keyword in self.error_keywords):
                            logger.warning(f"Detected potential error in {name}: {line}")
                            callback(name, line)
                except docker.errors.NotFound:
                    logger.error(f"Container {name} not found.")
                except Exception as e:
                    logger.error(f"Error streaming logs from {name}: {e}")
            
            time.sleep(10) # Poll every 10 seconds for simplicity in this version

if __name__ == "__main__":
    # Test logic
    def mock_callback(container, log):
        print(f"DEBUG: Alert triggered for {container}: {log}")

    listener = LogListener(["hr_hiring_bot_container", "hr_api_backend"])
    listener.stream_logs(mock_callback)
