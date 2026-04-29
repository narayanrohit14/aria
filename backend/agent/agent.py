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

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, JobExecutorType, room_io
from livekit.plugins import noise_cancellation, silero

try:
    from backend.data.aria_data_ingestion import load_audit_context, format_context_for_llm
except ModuleNotFoundError:
    from aria_data_ingestion import load_audit_context, format_context_for_llm

load_dotenv(".env.local")
ARIA_API_URL = os.getenv("ARIA_API_URL", "http://localhost:8000")
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

You are speaking directly with Aadesh Gandhre, Managing Director 
and General Auditor at DTCC. He has nearly two decades of internal 
audit leadership experience, including roles at Goldman Sachs and 
Société Générale. He holds certifications in CIA, CISA, AI governance, 
and cybersecurity. He is deeply familiar with audit methodology, 
emerging technology risk, and innovation in the audit function.

Address him as "Aadesh" — professional but warm, not formal titles.
Match his level of expertise — skip basics, go straight to insight.
He will ask sophisticated questions. Meet him there.

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


async def route_query(text: str, session: AgentSession):
    """
    Decides what additional context to inject before sending to the LLM.
    All paths ultimately call session.generate_reply() so TTS fires normally.
    """
    intents = _detect_intent(text)
    extra_context = ""

    # Inject live market data for macro/market questions
    if "market" in intents:
        snapshot = _get_market_snapshot()
        extra_context += f"\nLive Market Snapshot:\n{snapshot}\n"

    # Inject transaction/card data summary for data-specific questions
    if any(i in intents for i in ["data", "fraud", "settlement"]):
        extra_context += f"\n{AUDIT_CONTEXT_STR}\n"

    # Build enriched prompt
    if extra_context:
        prompt = (
            f"The user asked: {text}\n\n"
            f"Additional real-time context to inform your response:\n"
            f"{extra_context}\n"
            f"Respond as ARIA — analytical, structured, and audit-focused."
        )
    else:
        prompt = text

    response = await session.generate_reply(instructions=prompt)
    await send_subtitle(str(response))
    return response


# ─────────────────────────────────────────────
# ARIA AGENT CLASS
# ─────────────────────────────────────────────

class ARIAAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=ARIA_SYSTEM_PROMPT)


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

    # Opening greeting — session.say() speaks the text verbatim
    opening = (
    f"Hello Aadesh! I'm ARIA — the Audit Risk and Insights Agent, "
    f"purpose-built for DTCC's Internal Audit function. "
    f"I'm here to support you across the full audit lifecycle — "
    f"from risk assessment and control testing through to generating "
    f"findings and executive reporting. "
    f"I've got the dataset loaded and ready. "
    f"Based on what I'm seeing, the portfolio is sitting at a "
    f"{RISK_LEVEL} risk level overall. "
    f"What would you like to explore today?"
)
    await session.say(opening)
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
        if user_text and is_final:
            asyncio.create_task(route_query(user_text, session))

    # Keep session alive
    await asyncio.Future()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    agents.cli.run_app(server)
