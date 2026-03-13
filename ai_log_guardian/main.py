import os
import argparse
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AILogGuardian")


def run_agent_mode():
    """Runs the fully agentic LangGraph mode — the agent decides everything."""
    logger.info("🤖 Starting in AGENT mode (LangGraph ReAct)")
    from agent import run_agent_loop
    run_agent_loop()


def run_simple_mode():
    """Runs the original rule-based polling loop (legacy / fallback mode)."""
    logger.info("⚙️  Starting in SIMPLE mode (rule-based polling)")
    import json
    from log_listener import LogListener
    from llm_analyzer import LLMAnalyzer
    from alert_engine import AlertEngine
    from notification_tools import NotificationTools

    containers = os.getenv("MONITOR_CONTAINERS", "hr_hiring_bot_container,hr_api_backend").split(",")
    throttle = int(os.getenv("ALERT_THROTTLE_SECONDS", "300"))

    listener = LogListener(containers)
    analyzer = LLMAnalyzer()
    engine = AlertEngine(throttle_seconds=throttle)
    notifier = NotificationTools()

    def process_error(container, log_line):
        should_alert, incident_id = engine.should_trigger(container, log_line)
        if should_alert:
            logger.info(f"Triggering analysis for Incident: {incident_id}")
            analysis_raw = analyzer.analyze_log(container, log_line)
            try:
                if isinstance(analysis_raw, str):
                    clean = analysis_raw.replace("```json", "").replace("```", "").strip()
                    analysis = json.loads(clean)
                else:
                    analysis = analysis_raw
            except Exception as e:
                logger.error(f"Failed to parse LLM analysis: {e}")
                analysis = {"severity": "UNKNOWN", "root_cause": "Parse error", "suggested_fix": "Check logs manually"}
            notifier.send_whatsapp_alert(incident_id, container, analysis)
        else:
            logger.info(f"Alert throttled for {container}")

    try:
        listener.stream_logs(process_error)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


def main():
    parser = argparse.ArgumentParser(description="AI Log Guardian")
    parser.add_argument(
        "--mode",
        choices=["agent", "simple"],
        default="agent",
        help="agent = LangGraph agentic mode (default) | simple = rule-based polling"
    )
    args = parser.parse_args()

    if args.mode == "agent":
        run_agent_mode()
    else:
        run_simple_mode()


if __name__ == "__main__":
    main()
