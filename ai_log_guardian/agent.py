import os
import json
import time
import logging
import docker
import hashlib
import requests
import re
from typing import Annotated
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from twilio.rest import Client as TwilioClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AgentCore")

# ─────────────────────────────────────────────
# Shared state (in-memory for the agent's session)
# ─────────────────────────────────────────────
_incident_history: list[dict] = []
_suppressed: dict[str, int] = {}   # hash -> suppressed_until timestamp
_throttle_map: dict[str, int] = {} # hash -> last_alerted timestamp
_last_poll: dict[str, float] = {}  # container_name -> timestamp of last poll
_pattern_cache: dict[str, float] = {} # hash -> timestamp of last occurrence


def _make_hash(container: str, log_line: str) -> str:
    sig = f"{container}:{log_line[:60]}"
    return hashlib.md5(sig.encode()).hexdigest()


# ─────────────────────────────────────────────
# TOOL 1: Get recent logs from Docker containers
# ─────────────────────────────────────────────
@tool
def get_recent_logs(container_name: str, last_seconds: int = 30) -> str:
    """
    Fetch recent logs from a running Docker container.
    Returns log lines as a single string. Use this first to check if there are errors.

    Args:
        container_name: Name of the Docker container to fetch logs from.
        last_seconds: How many seconds back to look (default 30).
    """
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        since = int(time.time() - last_seconds)
        logs = container.logs(since=since, timestamps=True).decode("utf-8", errors="replace")
        if not logs.strip():
            return f"[{container_name}] No new logs in the last {last_seconds}s."
        return f"[{container_name}] Logs:\n{logs}"
    except docker.errors.NotFound:
        return f"[ERROR] Container '{container_name}' not found. Is it running?"
    except Exception as e:
        return f"[ERROR] Could not fetch logs from '{container_name}': {e}"


# ─────────────────────────────────────────────
# TOOL 2: Analyze a specific log line with LLM
# ─────────────────────────────────────────────
@tool
def analyze_log(container_name: str, log_line: str) -> str:
    """
    Analyze a specific log line from a container using an LLM.
    Returns a JSON with: severity, root_cause, suggested_fix, is_actionable.
    Call this only when you have found a suspicious or error log line.

    Args:
        container_name: The name of the container (for context).
        log_line: The specific log line to analyze.
    """
    try:
        from llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer()
        content = analyzer.analyze_log(container_name, log_line)
        if not content or not content.strip():
             return "{}"
        return content
    except Exception as e:
        import json
        return json.dumps({
            "severity": "UNKNOWN",
            "root_cause": f"Analysis failed: {e}",
            "suggested_fix": "Check the LLM API config and try again.",
            "is_actionable": False,
            "is_noise": False
        })


# ─────────────────────────────────────────────
# TOOL 3: Send a WhatsApp alert via Twilio
# ─────────────────────────────────────────────
@tool
def send_alert(container_name: str, incident_id: str, severity: str, root_cause: str, suggested_fix: str) -> str:
    """
    Send a WhatsApp alert via Twilio for a confirmed critical incident.
    Only call this after analyze_log confirms HIGH or CRITICAL severity and is_actionable=true.
    Handles throttling internally — will refuse to send the same alert twice within 5 minutes.

    Args:
        container_name: The container where the incident occurred.
        incident_id: A unique incident identifier string.
        severity: Severity level (HIGH or CRITICAL).
        root_cause: Brief root cause description.
        suggested_fix: Suggested resolution steps.
    """
    # Throttle check
    sig_hash = _make_hash(container_name, incident_id)
    throttle_secs = int(os.getenv("ALERT_THROTTLE_SECONDS", "300"))
    last_sent = _throttle_map.get(sig_hash, 0)
    if time.time() - last_sent < throttle_secs:
        remaining = int(throttle_secs - (time.time() - last_sent))
        return f"[THROTTLED] Alert for {container_name} suppressed. Retry in {remaining}s."

    _throttle_map[sig_hash] = int(time.time())

    body = f"""🚨 *AI Log Guardian Alert* 🚨
*Incident ID:* {incident_id}
*Container:* {container_name}
*Severity:* {severity}

*Root Cause:* {root_cause}

*Suggested Fix:* {suggested_fix}"""

    # Log to incident history
    _incident_history.append({
        "incident_id": incident_id,
        "container": container_name,
        "severity": severity,
        "root_cause": root_cause,
        "timestamp": int(time.time())
    })

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    to_number = os.getenv("USER_WHATSAPP_NUMBER")

    if account_sid and auth_token and to_number:
        try:
            twilio_client = TwilioClient(account_sid, auth_token)
            msg = twilio_client.messages.create(
                from_=f"whatsapp:{from_number}",
                body=body,
                to=f"whatsapp:{to_number}"
            )
            logger.info(f"WhatsApp alert sent: {msg.sid}")
            return f"[SUCCESS] WhatsApp alert sent. SID={msg.sid}. Incident {incident_id} logged."
        except Exception as e:
            logger.error(f"Twilio error: {e}")
            return f"[ERROR] Twilio failed: {e}. Message body was:\n{body}"
    else:
        logger.info("[DRY RUN] Twilio not configured.\n" + body)
        return f"[DRY RUN] Alert not sent (Twilio not configured). Body:\n{body}"


# ─────────────────────────────────────────────
# TOOL 4: Suppress a noisy alert
# ─────────────────────────────────────────────
@tool
def suppress_alert(container_name: str, log_line: str, reason: str) -> str:
    """
    Suppress/ignore an alert that is determined to be noise or expected behavior.
    Use this when the log looks like an error but is actually routine.

    Args:
        container_name: The container the log came from.
        log_line: The log line being suppressed.
        reason: Why you are suppressing this (brief).
    """
    sig_hash = _make_hash(container_name, log_line)
    _suppressed[sig_hash] = int(time.time()) + 3600  # suppress for 1 hour
    logger.info(f"[SUPPRESSED] {container_name}: {reason}")
    return f"[OK] Log suppressed for 1 hour. Reason: {reason}"


# ─────────────────────────────────────────────
# TOOL 5: Get incident history
# ─────────────────────────────────────────────
@tool
def get_incident_history() -> str:
    """
    Returns the list of all incidents that have been sent as alerts in this session.
    Use this to check what has already been reported.
    """
    if not _incident_history:
        return "No incidents recorded yet in this session."
    return json.dumps(_incident_history, indent=2)


# ─────────────────────────────────────────────
# Build the LangGraph ReAct Agent
# ─────────────────────────────────────────────
def _filter_messages(messages):
    """
    Ensures no message content is empty before reaching the LLM API.
    Gemini returns 400 if any message has empty 'parts' (content).
    """
    for m in messages:
        if hasattr(m, "content") and (not m.content or (isinstance(m.content, str) and not m.content.strip())):
            if hasattr(m, "tool_calls") and m.tool_calls:
                # Assistant messages with tool calls but empty content are valid
                pass
            else:
                m.content = "[No content]"
    return messages


def build_agent():
    """Creates and returns the LangGraph ReAct agent with all tools."""

    api_key = os.getenv("GROQ_API_KEY")
    base_url = "https://api.groq.com/openai/v1"
    model_name = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        raise EnvironmentError("No LLM API key found. Set GROQ_API_KEY in .env")

    logger.info(f"Agent using Groq model: {model_name}")

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0
    )

    tools = [
        get_recent_logs,
        analyze_log,
        send_alert,
        suppress_alert,
        get_incident_history,
    ]

    memory = MemorySaver()
    agent = create_react_agent(llm, tools, checkpointer=memory)
    return agent


SYSTEM_PROMPT = """You are AI Log Guardian, an expert DevOps monitoring agent.

Your job is to autonomously analyze specific suspicious log lines provided to you and respond intelligently.

RULES:
1. You will be provided with specific suspicious log lines that have already passed initial pattern filtering.
2. For each suspicious line provided, use `analyze_log` to understand it deeply. You may use `get_recent_logs` if you need more context before analyzing.
3. If analysis says is_noise=true OR severity is LOW → call `suppress_alert` with a reason.
4. If severity is MEDIUM, HIGH or CRITICAL AND is_actionable=true → call `send_alert`.
5. NEVER send the same alert twice (throttling is built into `send_alert`).
6. Always check `get_incident_history` before acting to avoid duplicates.
7. Be smart: a single "Connection refused" may be transient; three in a row is an incident.

Containers you are monitoring: {containers}

Think step by step. Be conservative — only alert on real issues.
"""


def get_filtered_errors(containers: list[str]) -> list[tuple[str, str]]:
    """Returns a list of (container_name, log_line) that are new and unique."""
    client = docker.from_env()
    results = []
    now = time.time()
    
    for name in containers:
        try:
            container = client.containers.get(name)
            last_ts = _last_poll.get(name, now - 30)
            logs = container.logs(since=int(last_ts), timestamps=True).decode("utf-8", errors="replace")
            _last_poll[name] = now
            
            if not logs.strip():
                continue
                
            for line in logs.splitlines():
                if any(kw in line.upper() for kw in ["ERROR", "CRITICAL", "FATAL", "EXCEPTION", "TRACEBACK"]):
                    # Pattern detection: remove timestamps, generic IDs to generalize the log pattern
                    pattern = re.sub(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d+)?Z?', '', line)
                    pattern = re.sub(r'\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b', 'UUID', pattern)
                    
                    sig_hash = _make_hash(name, pattern)
                    
                    # Deduplication: if pattern hasn't been seen in the exact container in the last 10 minutes (600s), process it
                    if now - _pattern_cache.get(sig_hash, 0) > 600:
                        _pattern_cache[sig_hash] = now
                        # clean log string up to limit tokens returned to LLM
                        clean_line = line[:1000]
                        results.append((name, clean_line))
                        
        except Exception as e:
            logger.error(f"Error fetching logs for pattern detection for {name}: {e}")
            
    return results


def run_agent_loop():
    """
    Main agentic loop: runs the LangGraph agent every POLL_INTERVAL seconds.
    """
    containers_env = os.getenv("MONITOR_CONTAINERS", "all")
    if (containers_env or "").lower() == "all":
        try:
            client = docker.from_env()
            containers = [c.name for c in client.containers.list()]
        except Exception as e:
            logger.error(f"Auto-discovery failed: {e}")
            containers = ["hr_hiring_bot_container", "hr_api_backend"]
    else:
        containers = containers_env.split(",")
        
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

    agent = build_agent()

    containers_str = ", ".join(containers)
    system_prompt = SYSTEM_PROMPT.format(containers=containers_str)

    logger.info(f"🤖 AI Log Guardian Agent started. Monitoring: {containers} every {poll_interval}s")

    cycle = 0
    while True:
        cycle += 1
        
        new_errors = get_filtered_errors(containers)
        
        if not new_errors:
            # Sleeping peacefully, no LLM cost incurred
            time.sleep(poll_interval)
            continue
            
        logger.info(f"--- Agent Cycle #{cycle} --- Found {len(new_errors)} new suspicious logs!")

        # Use a fresh thread_id per cycle to avoid accumulating empty messages
        # in history that trigger Gemini's 400 error.
        config = {"configurable": {"thread_id": f"log-guardian-cycle-{cycle}"}}

        instructions = "I found the following new suspicious logs that passed the pattern filter:\n\n"
        for container, err in new_errors:
            instructions += f"Container: {container}\nLog: {err}\n\n"
        instructions += "Please analyze each of these logs using `analyze_log`. " \
                        "If the severity is MEDIUM, HIGH or CRITICAL and actionable, use `send_alert`. " \
                        "If it is LOW/noise, use `suppress_alert`. " \
                        "Check `get_incident_history` to avoid duplicate alerts. Summarize your actions."

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=instructions),
            ]

            result = agent.invoke({"messages": messages}, config=config)

            res_messages = result.get("messages", [])
            if res_messages:
                final_content = res_messages[-1].content
                if final_content:
                    logger.info(f"Agent completed cycle #{cycle}. Summary: {final_content[:300]}...")
                else:
                    logger.info(f"Agent completed cycle #{cycle} with empty summary.")
            else:
                logger.warning(f"Agent cycle #{cycle} returned no messages.")

        except Exception as e:
            # Better error logging for the specific 400 error
            if "400" in str(e):
                logger.error(f"FATAL: LLM rejected request in cycle #{cycle} (possibly empty content): {e}")
            else:
                logger.error(f"Agent error in cycle #{cycle}: {e}")

        logger.info(f"Sleeping {poll_interval}s until next cycle...")
        time.sleep(poll_interval)


if __name__ == "__main__":
    run_agent_loop()
