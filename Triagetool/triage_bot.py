"""
handlers/triage_bot.py
Core Azure Bot Framework activity handler.

Channel behaviour:
  - ANY new root message posted in the channel auto-starts a triage session.
  - All follow-up Q&A happens IN THE SAME THREAD as the original message.
  - Session key = thread_id (conversation.id + reply_to_id) so multiple
    reporters can run parallel sessions without collision.

DM / 1-to-1 behaviour (fallback):
  - Session key = user_id (unchanged from before).
"""

from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import Activity, ChannelAccount

from config.settings import Settings
from config.questions import TOTAL_STEPS
from services.session_manager import SessionManager
from services.elk_client import ELKClient
from services.model_client import ModelClient

WELCOME_TEXT = (
    "🚨 **Issue Triage Started**\n\n"
    "Thanks for reporting! I'll ask you **6 quick questions** so I can "
    "query the logs and run a root cause analysis — all in this thread.\n\n"
    "Type `skip` for any optional field. Let's go! 👇"
)


def _is_channel_message(turn_context: TurnContext) -> bool:
    """Returns True when the message comes from a Teams channel (not a DM)."""
    return turn_context.activity.conversation.is_group or \
           turn_context.activity.channel_id == "msteams"


def _is_root_message(turn_context: TurnContext) -> bool:
    """
    A 'root' channel message has no reply_to_id — it's a brand-new post,
    not a reply inside an existing thread.
    """
    return not turn_context.activity.reply_to_id


def _session_key(turn_context: TurnContext) -> str:
    """
    Channel messages  → keyed by thread (conversation_id + activity_id of root post).
    DMs               → keyed by user_id.

    Using the thread as the key means two different people can each report
    an issue simultaneously in the same channel without interfering.
    """
    if _is_channel_message(turn_context):
        # reply_to_id is set for all replies in a thread; it holds the root
        # message's activity_id. For the ROOT message itself reply_to_id is
        # empty, so we use the activity's own id as the thread anchor.
        thread_anchor = (
            turn_context.activity.reply_to_id
            or turn_context.activity.id
        )
        return f"thread:{turn_context.activity.conversation.id}:{thread_anchor}"
    return f"user:{turn_context.activity.from_property.id}"


class TriageBot(ActivityHandler):

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.sessions = SessionManager(ttl=settings.SESSION_TTL)
        self.elk = ELKClient(settings)
        self.model = ModelClient(settings)

    # ── Entry point ──────────────────────────────────────────────────────────

    async def on_message_activity(self, turn_context: TurnContext):
        session_key = _session_key(turn_context)
        text_raw = (turn_context.activity.text or "").strip()
        text = text_raw.lower()

        # ── Global override commands (work anywhere) ─────────────────────────
        if text in {"restart", "reset", "cancel"}:
            self.sessions.reset(session_key)
            await self._reply(turn_context, "🔄 Triage session reset. Post a new issue to start again.")
            return

        if text in {"help", "?"}:
            await self._reply(
                turn_context,
                "**Commands:** `restart` — reset this triage  |  `skip` — skip an optional question"
            )
            return

        # ── Channel: auto-start on every NEW root message ────────────────────
        if _is_channel_message(turn_context) and _is_root_message(turn_context):
            # Always create a fresh session for each new channel post
            self.sessions.reset(session_key)
            session = self.sessions.create(session_key)
            # Store the root activity_id so we can reply in-thread later
            session.thread_activity_id = turn_context.activity.id
            # Pre-fill description from the original message
            session.issue_description = text_raw
            await self._reply_in_thread(turn_context, WELCOME_TEXT, turn_context.activity.id)
            await self._ask_current_question(turn_context, session)
            return

        # ── Collect answers for an active session ────────────────────────────
        session = self.sessions.get(session_key)

        if session is None or not session.active:
            # In a channel, only respond if we recognise the thread
            if _is_channel_message(turn_context):
                return  # silently ignore unrelated channel messages
            await self._reply(turn_context, "👋 Post a message in the issue channel to start triage.")
            return

        if session.is_complete():
            await self._reply(turn_context, "⏳ Already processing — please wait...")
            return

        # Validate
        current_q = session.current_question()
        if current_q.validator and text != "skip":
            if not current_q.validator(text_raw):
                await self._reply(
                    turn_context,
                    f"⚠️ Invalid input. {current_q.hint}\n\nPlease try again:"
                )
                return

        # Save and advance
        session.save_answer(text_raw)

        if session.is_complete():
            session.active = False
            await self._run_pipeline(turn_context, session)
        else:
            await self._ask_current_question(turn_context, session)

    # ── Pipeline ─────────────────────────────────────────────────────────────

    async def _run_pipeline(self, turn_context: TurnContext, session):
        session_key = _session_key(turn_context)
        answers = session.answers

        # Summary of collected info
        await self._reply(turn_context,
            f"✅ **All details collected!**\n\n{self._format_answers_summary(answers)}"
        )

        # ELK query
        await self._reply(turn_context, "🔍 Querying ELK logs...")
        elk_result = await self.elk.search(answers)

        if elk_result["error"]:
            await self._reply(turn_context,
                f"❌ **ELK Error:** `{elk_result['error']}`\n\nType `restart` to try again."
            )
            self.sessions.reset(session_key)
            return

        if elk_result["total"] == 0:
            await self._reply(turn_context,
                "⚠️ **No logs found** for the given criteria.\n\n"
                "Try a wider time range or different keyword.\n\nType `restart` to retry."
            )
            self.sessions.reset(session_key)
            return

        await self._reply(turn_context,
            f"📊 Found **{elk_result['total']} log entries**. Running root cause analysis..."
        )

        # Refinement model
        formatted_data = self.elk.format_for_model(elk_result, answers)
        await self._reply(turn_context, "⚙️ Analyzing with refinement model...")
        rca = await self.model.analyze(formatted_data, answers)

        # Final RCA report — same thread
        report = self.model.format_rca_report(rca, answers)
        await self._reply(turn_context, report)

        self.sessions.reset(session_key)

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _ask_current_question(self, turn_context: TurnContext, session):
        q = session.current_question()
        if not q:
            return
        msg = q.prompt
        if q.skippable:
            msg += "\n\n*💡 Optional — type `skip` to continue.*"
        await self._reply(turn_context, msg)

    async def _reply(self, turn_context: TurnContext, text: str):
        """Send a message, always replying inside the current thread."""
        activity = MessageFactory.text(text)
        # Preserve the reply chain so Teams keeps everything in one thread
        if turn_context.activity.reply_to_id:
            activity.reply_to_id = turn_context.activity.reply_to_id
        elif _is_channel_message(turn_context):
            # First bot reply to a root message — set thread anchor
            activity.reply_to_id = turn_context.activity.id
        await turn_context.send_activity(activity)

    async def _reply_in_thread(self, turn_context: TurnContext, text: str, root_id: str):
        """Explicitly reply to a specific root activity_id to start a thread."""
        activity = MessageFactory.text(text)
        activity.reply_to_id = root_id
        await turn_context.send_activity(activity)

    def _format_answers_summary(self, answers: dict) -> str:
        def val(k):
            return f"`{answers.get(k)}`" if answers.get(k) else "*not provided*"
        return (
            "| Field | Value |\n"
            "|---|---|\n"
            f"| Service | {val('service_name')} |\n"
            f"| Environment | {val('environment')} |\n"
            f"| Time Range | {val('time_range')} |\n"
            f"| Error Keyword | {val('error_keyword')} |\n"
            f"| Trace ID | {val('trace_id')} |\n"
            f"| User / Team | {val('user_id')} |\n"
        )
