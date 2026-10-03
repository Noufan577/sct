from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.logging import logger
from app.core.errors import validation_exception_handler, global_exception_handler
import asyncio
from datetime import datetime, timezone
from app.db.database import SessionLocal
from app.db.models import CommitmentModel, CommitmentStatusHistory
from app.services.email_service import EmailService

FRONTEND_INDEX = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html")
)

async def slipped_deadline_monitor():
    while True:
        try:
            with SessionLocal() as db:
                svc = EmailService()
                if svc.user and svc.password:
                    slipped = db.query(CommitmentModel).filter(CommitmentModel.status == "SLIPPED").all()
                    for c in slipped:
                        already_sent = db.query(CommitmentStatusHistory).filter(
                            CommitmentStatusHistory.commitment_id == c.id,
                            CommitmentStatusHistory.changed_by == "system_alert"
                        ).first()
                        
                        if not already_sent:
                            subject = f"Alert: Slipped Deadline for '{c.commitment}'"
                            body = f"Hi {c.person},\n\nYour commitment from MeetGraph has slipped past its deadline.\n\nTask: {c.commitment}\nOriginal deadline: {c.original_deadline or 'N/A'}\n\nPlease update the status in MeetGraph."
                            
                            # For MVP testing, send to the configured SMTP_FROM email so the user actually sees it.
                            test_email = svc.from_email 
                            if test_email:
                                sent = await asyncio.to_thread(svc.send_email, test_email, subject, body)
                                if sent:
                                    hist = CommitmentStatusHistory(
                                        commitment_id=c.id,
                                        old_status="SLIPPED",
                                        new_status="SLIPPED",
                                        changed_by="system_alert",
                                        note=f"Automated slipped deadline alert sent to {test_email}",
                                        changed_at=datetime.now(timezone.utc)
                                    )
                                    db.add(hist)
                                    db.commit()
                                    logger.info(f"Slipped deadline alert sent for commitment {c.id}")
        except Exception as e:
            logger.error(f"Error in slipped deadline monitor: {e}")
            
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} backend starting in {settings.APP_ENV} mode")
    logger.info("Application initialized")
    
    # Start the automated slipped deadline monitor in the background
    monitor_task = asyncio.create_task(slipped_deadline_monitor())
    
    yield
    
    # Clean up
    monitor_task.cancel()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="Local-first, evidence-backed commitment memory layer for Meetily.",
        lifespan=lifespan
    )
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    from app.api.routes import meetings, db_meetings, db_commitments, timeline, query, transcribe, recap, graph, sync, identities, intel, notifications
    app.include_router(meetings.router)
    app.include_router(db_meetings.router)
    app.include_router(db_commitments.router)
    app.include_router(timeline.router)
    app.include_router(query.router)
    app.include_router(transcribe.router)
    app.include_router(recap.router)
    app.include_router(graph.router)
    app.include_router(sync.router)
    app.include_router(identities.router)
    app.include_router(intel.router)
    app.include_router(notifications.router)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")

    @app.get("/health")
    def health_check():
        return {"status": "ok"}
        
    return app

app = create_app()
