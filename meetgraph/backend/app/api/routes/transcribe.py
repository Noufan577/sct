from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from app.api.responses import TranscribeResponse
from app.services.transcribe import TranscribeService, TranscriptionUnavailable

router = APIRouter(prefix="/api/transcribe", tags=["Speech-to-Text"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024


def get_transcribe_service() -> TranscribeService:
    return TranscribeService()


@router.post("", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    language_code: str = Query(default="ml-IN"),
    service: TranscribeService = Depends(get_transcribe_service),
):
    """Transcribe uploaded meeting audio (WAV/MP3/...).

    Primary engine is Sarvam Saaras; the offline wav2vec2 model is
    tried automatically when Sarvam is unavailable."""
    audio = await file.read()
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB).")
    if not audio:
        raise HTTPException(status_code=422, detail="Empty audio file.")
    try:
        result = await service.transcribe_audio(
            audio, filename=file.filename or "audio.wav", language_code=language_code
        )
    except TranscriptionUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Transcription failed")
    return TranscribeResponse(**result)
