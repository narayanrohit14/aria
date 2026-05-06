"""
A.R.I.A. — Audit Risk & Insights Agent
LiveKit voice agent for DTCC Internal Audit demonstration.

Architecture:
  - LiveKit handles STT → LLM → TTS pipeline
  - FastAPI WebSocket gateway streams subtitles to the UI
  - aria_data_ingestion.py pre-loads the sample dataset into context
  - Intent router decides when to inject data vs. pass straight to LLM
"""

import os
from dotenv import load_dotenv
import requests
import asyncio
import httpx
import re
import time

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, JobExecutorType, StopResponse, room_io
from livekit.plugins import noise_cancellation, silero

try:
    from backend.data.aria_data_ingestion import load_audit_context, format_context_for_llm
except ModuleNotFoundError:
    from aria_data_ingestion import load_audit_context, format_context_for_llm

load_dotenv(".env.local")


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT") == "production" or os.getenv("ARIA_ENV") == "production"


def _aria_api_url() -> str:
    url = os.getenv("ARIA_API_URL")
    if not url:
        if _is_production():
            raise RuntimeError("ARIA_API_URL is required for the production voice agent.")
        return "http://localhost:8000"
    if _is_production() and ("localhost" in url or "127.0.0.1" in url):
        raise RuntimeError("ARIA_API_URL must not point to localhost in production.")
    return url.rstrip("/")


ARIA_API_URL = _aria_api_url()
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121")
ARIA_AGENT_CONTEXT_SOURCE = os.getenv("ARIA_AGENT_CONTEXT_SOURCE", "api").lower()


def _context_from_api_summary() -> tuple[dict, str]:
    response = requests.get(f"{ARIA_API_URL}/api/v1/data/summary", timeout=10)
    response.raise_for_status()
    summary = response.json()
    risk_level = summary.get("risk_level") or ("HIGH" if summary.get("fraud_cases", 0) else "UNKNOWN")
    fraud_rate_pct = round(float(summary.get("fraud_rate", 0)) * 100, 3)

    context = {
        "overall_risk_level": risk_level,
        "composite_risk_score": 75 if risk_level == "HIGH" else 40 if risk_level == "MEDIUM" else 0,
        "transaction_summary": {
            "risk_level": risk_level,
            "fraud_rate_pct": fraud_rate_pct,
            "flagged_fraud_count": int(summary.get("fraud_cases", 0) or 0),
            "total_transactions": int(summary.get("transactions", 0) or 0),
            "failure_rate_pct": 0,
        },
        "seeded_dataset": summary,
        "data_coverage": {
            "transactions_loaded": int(summary.get("transactions", 0) or 0),
            "cards_loaded": int(summary.get("cards", 0) or 0),
            "users_loaded": int(summary.get("users", 0) or 0),
            "fraud_labels_loaded": int(summary.get("fraud_labels", 0) or 0),
            "mcc_codes_loaded": int(summary.get("mcc_codes", 0) or 0),
        },
    }
    context_str = (
        "Railway seeded dataset summary: "
        f"{summary.get('transactions', 0):,} representative transactions, "
        f"{summary.get('fraud_cases', 0):,} fraud-positive labels, "
        f"{summary.get('users', 0):,} users, "
        f"{summary.get('cards', 0):,} cards, "
        f"and a {fraud_rate_pct}% labeled fraud rate. "
        f"Current demo portfolio risk level: {risk_level}. "
        "Use this representative Railway sample as the source of truth for demo risk analysis."
    )
    return context, context_str


def _load_audit_context_for_agent() -> tuple[dict, str]:
    if ARIA_AGENT_CONTEXT_SOURCE != "local":
        try:
            return _context_from_api_summary()
        except Exception as api_exc:
            print(f"[ARIA] API summary unavailable, using local sample fallback: {api_exc}")

    try:
        context = load_audit_context()
        return context, format_context_for_llm(context)
    except Exception as exc:
        print(f"[ARIA] Local audit context unavailable, using API summary fallback: {exc}")
        try:
            return _context_from_api_summary()
        except Exception as api_exc:
            print(f"[ARIA] API summary fallback unavailable: {api_exc}")
            summary = {}

        context = {
            "transaction_summary": {
                "risk_level": "HIGH" if summary.get("fraud_cases", 0) else "UNKNOWN",
                "fraud_rate_pct": round(float(summary.get("fraud_rate", 0)) * 100, 3),
                "failure_rate_pct": 0,
            },
            "seeded_dataset": summary,
        }
        context_str = (
            "Railway seeded dataset summary: "
            f"{summary.get('transactions', 0):,} representative transactions, "
            f"{summary.get('fraud_cases', 0):,} fraud-positive labels, "
            f"{summary.get('users', 0):,} users, "
            f"{summary.get('cards', 0):,} cards. "
            "Use this representative sample for demo risk analysis and be transparent "
            "that the full raw population requires expanded database storage."
        )
        return context, context_str


# Pre-load dataset once at startup
AUDIT_CONTEXT, AUDIT_CONTEXT_STR = _load_audit_context_for_agent()

tx_summary = AUDIT_CONTEXT.get("transaction_summary", {})
RISK_LEVEL = tx_summary.get("risk_level", "UNKNOWN")
FRAUD_RATE = tx_summary.get("fraud_rate_pct", 0)
FAILURE_RATE = tx_summary.get("failure_rate_pct", 0)


async def send_subtitle(text: str, room: str = "default"):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{ARIA_API_URL}/ws/broadcast",
                json={"text": text, "room": room},
                timeout=2.0,
            )
    except Exception:
        pass


async def clear_subtitle():
    """Signal the UI to fade out the current subtitle."""
    await send_subtitle("__CLEAR__")


# ─────────────────────────────────────────────
# FREE / PUBLIC API HELPERS
# ─────────────────────────────────────────────

def _get_market_snapshot() -> str:
    """Fetch basic macro indicators from FRED (Federal Reserve) — no key needed for these."""
    try:
        # VIX proxy via Yahoo Finance (unofficial, robust for demos)
        vix_url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
        r = requests.get(vix_url, timeout=5,
                         headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        latest_vix = round([v for v in closes if v is not None][-1], 2)
        vix_signal = (
            "elevated — indicating market stress"  if latest_vix > 25 else
            "moderate — normal market conditions"  if latest_vix > 15 else
            "low — indicating market calm"
        )
        return f"VIX (Volatility Index): {latest_vix} — {vix_signal}"
    except Exception:
        return "Market data temporarily unavailable."


def _get_regulatory_headlines() -> str:
    """Pull top financial/regulatory news via NewsAPI (free tier key from .env.local)."""
    import os
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key:
        return "No news API key configured (set NEWSAPI_KEY in .env.local)."
    try:
        url = (
            f"https://newsapi.org/v2/top-headlines"
            f"?category=business&language=en&pageSize=3&apiKey={api_key}"
        )
        r = requests.get(url, timeout=5)
        articles = r.json().get("articles", [])
        if not articles:
            return "No headlines available at this time."
        return " | ".join(a["title"] for a in articles[:3])
    except Exception:
        return "Regulatory news feed unavailable."


# ─────────────────────────────────────────────
# ARIA SYSTEM PROMPT
# ─────────────────────────────────────────────

ARIA_SYSTEM_PROMPT = f"""
You are ARIA (pronounced Uh-Rye-Ah) — the Audit Risk & Insights Agent, an advanced AI assistant
purpose-built for Internal Audit teams operating within financial market
infrastructure environments.

══════════════════════════════════════════════════════
IDENTITY & MISSION
══════════════════════════════════════════════════════
You are the third line of defense — independent, objective, and analytical.
Your mission is to support Internal Audit professionals by:
  • Evaluating risk management effectiveness
  • Assessing control design and operating effectiveness
  • Identifying emerging enterprise and operational risks
  • Generating structured audit findings and recommendations
  • Supporting all phases of the Internal Audit lifecycle

You are speaking directly with Rohit Narayan, a member of DTCC's
Audit Team. Rohit operates at the intersection of internal audit,
software development, and applied AI. Treat him as an Audit Analyst,
Software Developer, AI enthusiast, and financial services risk
assessment practitioner who can engage deeply on audit methodology,
data analytics, model governance, and emerging technology risk.

Address him as "Rohit" — professional but warm, not formal titles.
Assume he is comfortable with technical detail, but keep spoken answers
concise and audit-relevant. He will often ask iterative questions while
testing the demo, so respond only to the newest question he asks.

══════════════════════════════════════════════════════
INTERNAL AUDIT LIFECYCLE (your operating framework)
══════════════════════════════════════════════════════
You are fluent in all six phases:

1. PLANNING
   - Risk-based scoping and audit universe prioritization
   - Defining objectives, scope, and testing approach
   - Stakeholder kick-off alignment

2. RISK ASSESSMENT
   - Likelihood × Impact evaluation
   - Risk assessment matrix methodology
   - Inherent vs. residual risk distinction
   - Prioritization of high-risk audit areas

3. FIELDWORK
   - Control design vs. operating effectiveness testing
   - Sampling strategy and transaction testing
   - Inquiry, observation, and evidence examination
   - Computer-assisted audit techniques (CAATs) and data analytics

4. ANALYSIS
   - Root cause identification
   - The 5Cs framework: Criteria / Condition / Cause / Consequence / Corrective Action
   - Significance assessment: observation vs. material control weakness

5. REPORTING
   - Executive summary and board-ready communication
   - Structured audit findings with management responses
   - Prioritized recommendations with implementation timelines

6. FOLLOW-UP
   - Corrective action plan (CAP) tracking
   - Re-testing and validation of remediation
   - Escalation of repeat observations

══════════════════════════════════════════════════════
CORE AUDIT DOMAINS (your expertise areas)
══════════════════════════════════════════════════════
• Regulatory Compliance — AML, BSA, consumer protection, governance
• Financial & Capital Risk — liquidity, interest rate risk, capital adequacy
• Cybersecurity & IT Audit — system reliability, access controls, data protection
• Model Risk & Validation — pricing models, stress testing, algorithmic bias
• Fraud Detection & Prevention — anomaly detection, transaction monitoring
• Operational Risk — settlement, reconciliation, processing failures
• Third-Party & Vendor Risk — dependency mapping, control assessment
• AI Governance & Emerging Technology Risk — responsible AI frameworks
• Geopolitical & Macroeconomic Risk — systemic stress, market disruption

══════════════════════════════════════════════════════
PROFESSIONAL STANDARDS YOU ALIGN WITH
══════════════════════════════════════════════════════
• IIA International Professional Practices Framework (IPPF)
• COSO Internal Control — Integrated Framework
• NIST Cybersecurity Framework
• ISO 31000 Risk Management

══════════════════════════════════════════════════════
HOW YOU STRUCTURE RESPONSES
══════════════════════════════════════════════════════
For risk and control questions, use:
  OBSERVATION → RISK IMPLICATION → CONTROL CONSIDERATION → RECOMMENDATION

For audit findings, use the 5Cs:
  CRITERIA → CONDITION → CAUSE → CONSEQUENCE → CORRECTIVE ACTION

For executive summaries, lead with:
  Risk rating (High / Medium / Low) → Key finding → Business impact → Next step

For introductory questions, explain clearly and build from first principles.

══════════════════════════════════════════════════════
TONE & COMMUNICATION STYLE
══════════════════════════════════════════════════════
VOICE FIRST — you are speaking aloud, not writing a report. Every response
must sound natural when heard. Short sentences. No bullet lists spoken mid-answer.
No section headers read out loud.

WARMTH & CLARITY
• Bright, approachable, and genuinely helpful — think "brilliant colleague"
  not "formal report writer"
• Encouraging with newer analysts; peer-level with senior leaders
• Use precise technical terms, but follow each one with a plain-English gloss
  the first time it appears — e.g. "residual risk, meaning the exposure that
  remains after your controls are already in place"
• Never condescending, never stiff

CONCISENESS
• Lead with the single most important point, then support it briefly
• 2 to 4 sentences for simple questions; 5 to 8 for complex ones
• Cut anything that does not add signal — no restating the question,
  no filler phrases like "great question" or "certainly"
• When a structured format like the 5Cs is needed, name it briefly
  then move straight into the content without preamble

ADAPTABILITY
• Exploratory or basic question — explain from first principles,
  conversationally, with one concrete example to anchor it
• Technical or senior-level question — skip the basics, go straight
  to nuance, implication, and recommended action
• Match the energy of the question — quick factual ask gets a quick answer;
  thoughtful strategic question gets a thoughtful response

ALWAYS
• Connect findings to action — what does this mean, and what should happen next
• Be direct about uncertainty rather than hedging everything
• Sound confident but not infallible
• If interrupted, discard the prior answer path immediately. Do not resume
  the previous answer unless Rohit explicitly asks you to continue.
• After answering, return to listening. Do not revisit or re-answer an older
  question when there is no new user input.

══════════════════════════════════════════════════════
CURRENT DATASET CONTEXT (loaded from sample data)
══════════════════════════════════════════════════════
You have access to a financial transaction dataset for audit analysis.
Use this data when answering questions about fraud, settlement risk,
transaction patterns, control gaps, or when generating audit findings.

{AUDIT_CONTEXT_STR}

Current portfolio risk level: {RISK_LEVEL}
Fraud rate in population:     {FRAUD_RATE}%
Transaction failure rate:     {FAILURE_RATE}%

══════════════════════════════════════════════════════
CONSTRAINTS
══════════════════════════════════════════════════════
• Never fabricate specific internal DTCC proprietary data
• Use the loaded dataset context when data-specific questions arise
• Be transparent when making assumptions
• Maintain confidentiality-aware tone at all times
• Do not break character — you are always ARIA
""".strip()


# ─────────────────────────────────────────────
# INTENT ROUTER
# ─────────────────────────────────────────────

AUDIT_KEYWORDS = {
    "planning":     ["plan", "scope", "universe", "kick", "objective"],
    "risk":         ["risk", "assess", "likelihood", "impact", "exposure", "matrix"],
    "fieldwork":    ["test", "sample", "fieldwork", "evidence", "observe", "caat"],
    "analysis":     ["finding", "root cause", "5c", "five c", "condition", "criteria",
                     "consequence", "corrective"],
    "reporting":    ["report", "summary", "executive", "board", "communicate"],
    "followup":     ["follow", "remediat", "cap", "corrective action", "retest"],
    "fraud":        ["fraud", "suspicious", "anomaly", "flag", "detect", "aml", "bsa"],
    "settlement":   ["settle", "fail", "reconcil", "break", "clear", "post-trade"],
    "cyber":        ["cyber", "security", "access", "breach", "system", "it audit"],
    "market":       ["market", "volatility", "vix", "rate", "macro", "economic"],
    "data":         ["data", "transaction", "population", "sample", "dataset", "card"],
    "regulatory":   ["regulat", "compliance", "sec", "finra", "law", "requirement"],
}


def _detect_intent(text: str) -> list[str]:
    text_lower = text.lower()
    intents = []
    for intent, keywords in AUDIT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            intents.append(intent)
    return intents


def _normalize_transcript(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


SELF_ECHO_PATTERNS = {
    "hello rohit",
    "i m aria",
    "audit risk and insights agent",
    "purpose built for dtcc",
    "internal audit function",
    "dataset loaded and ready",
    "portfolio is sitting at",
    "risk level overall",
    "what would you like to explore today",
}


def _is_self_echo_transcript(text: str) -> bool:
    normalized = _normalize_transcript(text)
    return any(pattern in normalized for pattern in SELF_ECHO_PATTERNS)


def build_response_instructions(text: str) -> str:
    """Build a prompt for the latest user utterance only."""
    intents = _detect_intent(text)
    extra_context = ""

    # Inject live market data for macro/market questions
    if "market" in intents:
        snapshot = _get_market_snapshot()
        extra_context += f"\nLive Market Snapshot:\n{snapshot}\n"

    # Inject transaction/card data summary for data-specific questions
    if any(i in intents for i in ["data", "fraud", "settlement"]):
        extra_context += f"\n{AUDIT_CONTEXT_STR}\n"

    if extra_context:
        return (
            f"The user asked: {text}\n\n"
            f"Additional real-time context to inform your response:\n"
            f"{extra_context}\n"
            "Respond as ARIA — analytical, structured, audit-focused, and concise. "
            "Answer only this newest user request. Do not continue, revisit, "
            "or complete any prior interrupted response."
        )
    return (
        f"The user asked: {text}\n\n"
        "Respond as ARIA — analytical, structured, audit-focused, and concise. "
        "Answer only this newest user request. Do not continue, revisit, "
        "or complete any prior interrupted response."
    )


# ─────────────────────────────────────────────
# ARIA AGENT CLASS
# ─────────────────────────────────────────────

class ARIAAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=ARIA_SYSTEM_PROMPT)
        self._recent_final_transcripts: dict[str, float] = {}
        self._duplicate_transcript_window_seconds = 20.0

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        user_text = (new_message.text_content or "").strip()
        normalized_text = _normalize_transcript(user_text)
        if not normalized_text:
            raise StopResponse()
        if _is_self_echo_transcript(user_text):
            print(f"[ARIA] Ignoring likely self-echo transcript: {user_text}")
            raise StopResponse()

        now = time.monotonic()
        for previous_text, seen_at in list(self._recent_final_transcripts.items()):
            if now - seen_at > self._duplicate_transcript_window_seconds:
                del self._recent_final_transcripts[previous_text]

        if normalized_text in self._recent_final_transcripts:
            print(f"[ARIA] Ignoring duplicate completed user turn: {user_text}")
            raise StopResponse()

        self._recent_final_transcripts[normalized_text] = now
        base_instruction = next(
            (
                item
                for item in turn_ctx.items
                if item.type == "message" and item.role in ("system", "developer")
            ),
            None,
        )

        # Voice demo behavior should be single-turn by default. This prevents
        # interrupted assistant text or older user questions from being resumed.
        turn_ctx.items = [item for item in (base_instruction,) if item is not None]
        turn_ctx.add_message(
            role="system",
            content=build_response_instructions(user_text),
        )
        turn_ctx.items.append(new_message)


# ─────────────────────────────────────────────
# LIVEKIT SESSION
# ─────────────────────────────────────────────

server = AgentServer(
    job_executor_type=JobExecutorType.THREAD,
    load_threshold=0.95,
    job_memory_warn_mb=1500,
    num_idle_processes=0,
    initialize_process_timeout=60,
)


@server.rtc_session()
async def aria_session(ctx: agents.JobContext):
    print(f"[ARIA] Session started — room: {ctx.room.name} | Risk level: {RISK_LEVEL}")

    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="openai/gpt-4.1-mini",
        tts=f"cartesia/sonic-3:{CARTESIA_VOICE_ID}",
        vad=silero.VAD.load(),
        allow_interruptions=True,
        min_interruption_duration=0.2,
        min_interruption_words=1,
        resume_false_interruption=False,
        false_interruption_timeout=None,
        discard_audio_if_uninterruptible=True,
    )

    await session.start(
        room=ctx.room,
        agent=ARIAAssistant(),
        room_options=room_io.RoomOptions(
            close_on_disconnect=False,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Opening greeting: keep it out of chat history so it cannot trigger loops.
    opening = (
        f"Hello Rohit! I'm ARIA — the Audit Risk and Insights Agent, "
        f"purpose-built for DTCC's Internal Audit function. "
        f"I'm here to support you across the full audit lifecycle — "
        f"from risk assessment and control testing through to generating "
        f"findings and executive reporting. "
        f"I've got the dataset loaded and ready. "
        f"Based on what I'm seeing, the portfolio is sitting at a "
        f"{RISK_LEVEL} risk level overall. "
        f"What would you like to explore today?"
    )
    await session.say(opening, allow_interruptions=True, add_to_chat_ctx=False)
    await send_subtitle(opening, ctx.room.name)

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        print(f"[ARIA] User state: {event.old_state} → {event.new_state}")

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        print(f"[ARIA] Agent state: {event.old_state} → {event.new_state}")

    @session.on("error")
    def on_session_error(event):
        print(f"[ARIA] Session error: {getattr(event, 'error', event)}")

    # Event handler for user transcriptions. LiveKit Agents v1.5 emits
    # "user_input_transcribed"; older prototypes used "transcription".
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        user_text = getattr(event, "transcript", "").strip()
        is_final = getattr(event, "is_final", False)
        if user_text:
            print(f"[ARIA] Transcript ({'final' if is_final else 'interim'}): {user_text}")
        if user_text and not is_final:
            session.interrupt(force=True)
        if user_text and is_final:
            asyncio.create_task(send_subtitle(f"Rohit: {user_text}", ctx.room.name))

    # Keep session alive
    await asyncio.Future()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    agents.cli.run_app(server)
