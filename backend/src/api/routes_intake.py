import os
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from src.stages.intake_email import poll_inbox
from src.stages.intake_sms import process_incoming_sms

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake", tags=["intake"])

# Shared secret to protect the poll endpoint from unauthorized calls
INTAKE_WEBHOOK_SECRET = os.getenv("INTAKE_WEBHOOK_SECRET", "")


def _verify_secret(request: Request):
    """Verify webhook secret for internal endpoints."""
    if not INTAKE_WEBHOOK_SECRET:
        return  # No secret configured — allow in dev
    token = request.headers.get("X-Webhook-Secret", "")
    if token != INTAKE_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


@router.post("/email/poll")
async def trigger_email_poll(request: Request, background_tasks: BackgroundTasks):
    """
    Trigger email inbox polling. Call this on a schedule (e.g. every 5 min via cron).
    Protected by X-Webhook-Secret header.
    """
    _verify_secret(request)
    background_tasks.add_task(poll_inbox)
    return {"status": "polling"}


@router.post("/sms")
async def twilio_sms_webhook(request: Request):
    """
    Twilio SMS/MMS webhook endpoint.
    Twilio sends POST with form data. We process and return TwiML reply.

    Set this URL in Twilio console → Phone Number → Messaging webhook:
    https://legoworlds-api-production.up.railway.app/api/intake/sms
    """
    form = await request.form()
    form_data = dict(form)

    result = await process_incoming_sms(form_data)

    # Return TwiML response for Twilio to send as reply
    reply_text = result["reply"]
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>{reply_text}</Message>
</Response>"""

    return PlainTextResponse(content=twiml, media_type="text/xml")
