"""Database query routes for app databases."""
from fastapi import APIRouter, Depends, HTTPException

from mgx_api.dependencies import get_current_user
from mgx_api.schemas import (
    DatabaseQueryRequest,
    DatabaseQueryResponse,
    CollectionsResponse,
    CollectionInfo,
)
from mgx_api.services import SessionService, DatabaseService

router = APIRouter()


@router.get("/apps/{session_id}/database/collections", response_model=CollectionsResponse)
async def list_collections(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List all collections in an app's database.
    
    Args:
        session_id: Session ID
        current_user: Authenticated user
    
    Returns:
        CollectionsResponse: List of collections with document counts
    """
    # Validate session
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if user owns this session
    if session.get("creator") != current_user.get("sub", "unknown"):
        raise HTTPException(status_code=403, detail="Not authorized to access this session")
    
    # Get collections
    db_service = DatabaseService()
    collections = await db_service.list_collections(session_id)
    
    return CollectionsResponse(
        collections=[CollectionInfo(**col) for col in collections]
    )


@router.post("/apps/{session_id}/database/query", response_model=DatabaseQueryResponse)
async def query_collection(
    session_id: str,
    body: DatabaseQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Query a collection in an app's database.
    
    Args:
        session_id: Session ID
        body: Query request with collection, filter, limit, and skip
        current_user: Authenticated user
    
    Returns:
        DatabaseQueryResponse: Query results with documents and metadata
    """
    # Validate session
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if user owns this session
    if session.get("creator") != current_user.get("sub", "unknown"):
        raise HTTPException(status_code=403, detail="Not authorized to access this session")
    
    # Query collection
    db_service = DatabaseService()
    try:
        documents, count, has_more = await db_service.query_collection(
            session_id=session_id,
            collection=body.collection,
            filter_query=body.filter,
            limit=body.limit,
            skip=body.skip,
        )
        
        return DatabaseQueryResponse(
            collection=body.collection,
            documents=documents,
            count=count,
            has_more=has_more,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
