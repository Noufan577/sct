from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.repositories.db_repository import DBRepository
from app.graph.store import build_graph
from app.api.responses import GraphResponse

router = APIRouter(prefix="/api/graph", tags=["Relation Graph"])


@router.get("", response_model=GraphResponse)
def get_graph(
    person: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Meeting relation graph from LadybugDB: Person -made-> Commitment
    -in-> Meeting, plus same-thread links across meetings.
    Optionally filtered to one person (case-insensitive)."""
    try:
        items = DBRepository(db).get_all_commitments()
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")
    try:
        return build_graph(items, person=person)
    except Exception as e:
        print(f"Graph Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to build graph")
