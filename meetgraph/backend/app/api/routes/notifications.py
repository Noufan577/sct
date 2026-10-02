from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.services.email_service import EmailService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

class RemindRequest(BaseModel):
    person_name: str
    email_address: str
    task_description: str
    meeting_title: Optional[str] = "a recent meeting"

def _send_email_task(req: RemindRequest):
    svc = EmailService()
    subject = f"Action Required: Follow-up from {req.meeting_title}"
    body = f"""Hi {req.person_name},

This is an automated reminder regarding an open commitment from {req.meeting_title}.

Commitment: {req.task_description}

Please let us know if you need any help or if this is already completed.

Thanks,
MeetGraph Automated Assistant
"""
    svc.send_email(req.email_address, subject, body)

@router.post("/remind")
async def send_reminder(req: RemindRequest, background_tasks: BackgroundTasks):
    """Send an automated reminder email for an open commitment."""
    svc = EmailService()
    if not svc.user or not svc.password:
        raise HTTPException(status_code=500, detail="SMTP credentials are not configured in the backend.")
        
    background_tasks.add_task(_send_email_task, req)
    return {"status": "accepted", "message": f"Reminder queued for {req.email_address}"}
