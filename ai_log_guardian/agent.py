import os
import json
import time
import logging
import docker
import hashlib
import requests
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
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    model = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")
    fallback_model = os.getenv("FALLBACK_MODEL", "llama3")

    prompt = f"""Analyze this log line from the Docker container '{container_name}':

LOG: {log_line}

Respond ONLY in valid JSON with these fields:
- severity: one of LOW, MEDIUM, HIGH, CRITICAL
- root_cause: short explanation (1-2 sentences)
- suggested_fix: concrete step(s) to resolve
- is_actionable: true or false
- is_noise: true if this is a routine/expected message, false if it needs attention
"""

    try:
        if openrouter_api_key:
            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, data=json.dumps(data), timeout=30
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        else:
            data = {"model": fallback_model, "prompt": prompt, "stream": False, "format": "json"}
            resp = requests.post(ollama_url, data=json.dumps(data), timeout=60)
            resp.raise_for_status()
            return resp.json().get("response", "{}")
    except Exception as e:
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
def build_agent():
    """Creates and returns the LangGraph ReAct agent with all tools."""
    
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("GROQ_API_KEY")
    base_url = None
    model_name = None

    if os.getenv("OPENROUTER_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"
        model_name = os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")
        logger.info(f"Agent using OpenRouter model: {model_name}")
    elif os.getenv("GROQ_API_KEY"):
        base_url = "https://api.groq.com/openai/v1"
        model_name = os.getenv("LLM_MODEL_NAME", "llama-3.3-70b-versatile")
        logger.info(f"Agent using Groq model: {model_name}")
    else:
        raise EnvironmentError("No LLM API key found. Set OPENROUTER_API_KEY or GROQ_API_KEY in .env")

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

Your job is to autonomously monitor Docker container logs and respond to incidents intelligently.

RULES:
1. Use `get_recent_logs` to fetch logs from ALL monitored containers each cycle.
2. Scan for lines containing: ERROR, CRITICAL, FATAL, EXCEPTION, or Traceback.
3. For each suspicious line, use `analyze_log` to understand it deeply.
4. If analysis says is_noise=true OR severity is LOW → call `suppress_alert` with a reason.
5. If severity is HIGH or CRITICAL AND is_actionable=true → call `send_alert`.
6. NEVER send the same alert twice (throttling is built into `send_alert`).
7. Always check `get_incident_history` before acting to avoid duplicates.
8. Be smart: a single "Connection refused" may be transient; three in a row is an incident.

Containers to monitor: {containers}

Think step by step. Be conservative — only alert on real issues.
"""


def run_agent_loop():
    """
    Main agentic loop: runs the LangGraph agent every POLL_INTERVAL seconds.
    """
    containers = os.getenv("MONITOR_CONTAINERS", "hr_hiring_bot_container,hr_api_backend").split(",")
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

    agent = build_agent()
    config = {"configurable": {"thread_id": "log-guardian-main"}}

    logger.info(f"🤖 AI Log Guardian Agent started. Monitoring: {containers} every {poll_interval}s")

    cycle = 0
    while True:
        cycle += 1
        logger.info(f"--- Agent Cycle #{cycle} ---")

        prompt = (
            SYSTEM_PROMPT.format(containers=", ".join(containers))
            + f"\n\nThis is monitoring cycle #{cycle}. "
            + "Check all containers for new issues. Take all necessary actions."
        )

        try:
            result = agent.invoke(
                {"messages": [HumanMessage(content=prompt)]},
                config=config
            )
            final_msg = result["messages"][-1].content
            logger.info(f"Agent completed cycle #{cycle}. Summary: {final_msg[:300]}")
        except Exception as e:
            logger.error(f"Agent error in cycle #{cycle}: {e}")

        logger.info(f"Sleeping {poll_interval}s until next cycle...")
        time.sleep(poll_interval)
