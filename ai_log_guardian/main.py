import os
import json
import logging
from log_listener import LogListener
from llm_analyzer import LLMAnalyzer
from alert_engine import AlertEngine
from notification_tools import NotificationTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AILogGuardian")

def main():
    logger.info("Starting AI Log Guardian...")
    
    # Configuration
    containers_to_monitor = os.getenv("MONITOR_CONTAINERS", "hr_hiring_bot_container,hr_api_backend").split(",")
    throttle_time = int(os.getenv("ALERT_THROTTLE_SECONDS", "300"))
    
    # Initialize components
    listener = LogListener(containers_to_monitor)
    analyzer = LLMAnalyzer()
    engine = AlertEngine(throttle_seconds=throttle_time)
    notifier = NotificationTools()

    def process_error(container, log_line):
        """
        Callback triggered when an error log is detected.
        """
        should_alert, incident_id = engine.should_trigger(container, log_line)
        
        if should_alert:
            logger.info(f"Triggering analysis for Incident: {incident_id}")
            
            # Analyze log with LLM
            analysis_raw = analyzer.analyze_log(container, log_line)
            
            try:
                # Attempt to parse JSON if string
                if isinstance(analysis_raw, str):
                    # Clean up markdown if present
                    clean_json = analysis_raw.replace("```json", "").replace("```", "").strip()
                    analysis = json.loads(clean_json)
                else:
                    analysis = analysis_raw
            except Exception as e:
                logger.error(f"Failed to parse LLM analysis: {e}. Raw content: {analysis_raw}")
                analysis = {"severity": "UNKNOWN", "root_cause": "Failed to parse analysis", "suggested_fix": "Check logs manually"}

            # Send Notification
            notifier.send_whatsapp_alert(incident_id, container, analysis)
        else:
            logger.info(f"Alert throttled for {container}")

    # Start streaming
    try:
        listener.stream_logs(process_error)
    except KeyboardInterrupt:
        logger.info("Shutting down AI Log Guardian...")

if __name__ == "__main__":
    main()
