"""
MS Teams Triage Bot — Azure Bot Framework Entry Point
"""

import sys
import traceback
from http import HTTPStatus

from aiohttp import web
from botbuilder.core import BotFrameworkAdapterSettings, BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity, ActivityTypes

from config.settings import Settings
from handlers.triage_bot import TriageBot

# ── Adapter Setup ────────────────────────────────────────────────────────────
settings = Settings()
adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.APP_ID,
    app_password=settings.APP_PASSWORD,
)
adapter = BotFrameworkAdapter(adapter_settings)


async def on_error(context: TurnContext, error: Exception):
    """Global error handler — logs and notifies the user."""
    print(f"[ERROR] Unhandled exception: {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity("⚠️ An unexpected error occurred. Please type `restart` to begin again.")
    if context.activity.channel_id == "emulator":
        await context.send_activity(Activity(
            type=ActivityTypes.trace,
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=None,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        ))


adapter.on_turn_error = on_error

# ── Bot Instance ──────────────────────────────────────────────────────────────
bot = TriageBot(settings)


# ── HTTP Handler ─────────────────────────────────────────────────────────────
async def messages(req: web.Request) -> web.Response:
    """Main webhook endpoint — receives all Teams messages."""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return web.Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    try:
        response = await adapter.process_activity(activity, auth_header, bot.on_turn)
        if response:
            return web.json_response(data=response.body, status=response.status)
        return web.Response(status=HTTPStatus.OK)
    except Exception as e:
        raise e


# ── App Bootstrap ─────────────────────────────────────────────────────────────
app = web.Application()
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        web.run_app(app, host="localhost", port=settings.PORT)
    except Exception as e:
        raise RuntimeError(f"Failed to start bot server: {e}") from e
