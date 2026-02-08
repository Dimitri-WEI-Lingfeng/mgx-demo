"""Agent task routes with SSE streaming support."""
import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import loguru

from mgx_api.dao import EventDAO, MessageDAO
from mgx_api.dependencies import get_current_user
from mgx_api.schemas import AgentTaskRequest
from mgx_api.services import SessionService
from mgx_api.services.docker_service import DockerService
from mgx_api.services.session_running_service import SessionRunningService
from shared.agent_stop_signal import request_stop
from shared.schemas import Event, EventType, Message, event_to_sse

router = APIRouter()


async def is_terminal_event(event_type: str) -> bool:
    """Check if an event type is terminal (ends the stream).
    
    Args:
        event_type: Event type to check
    
    Returns:
        True if terminal event
    """
    return event_type in [
        EventType.FINISH.value,
        EventType.AGENT_ERROR.value,
        EventType.AGENT_END.value,  # Agent 可能在 AGENT_END 后、FINISH 前崩溃
    ]


async def stream_events_generator(
    session_id: str,
    since_timestamp: float | None = None,
):
    """Shared event generator for SSE streaming.
    
    This generator:
    0. Ensures agent container is running
    1. Fetches historical events (since_timestamp=None: all; else: after timestamp)
    2. Streams historical events
    3. Continues polling for new events until terminal event or timeout
    
    Args:
        session_id: Session ID
        since_timestamp: Optional Unix timestamp to resume from; None means all events
        
    Yields:
        SSE formatted event strings
    """
    event_dao = EventDAO()
    max_wait_time = 300  # 5 minutes timeout
    poll_interval = 0.5  # 500ms polling interval
    start_time = asyncio.get_event_loop().time()

    loguru.logger.info(
        f"stream_events_generator start session_id={session_id} since_timestamp={since_timestamp}"
    )
    
    try:
        # Ensure agent container is running
        session_service = SessionService()
        session = await session_service.get_session(session_id)
        
        if not session:
            loguru.logger.warning(
                f"stream_events_generator: session not found session_id={session_id}"
            )
            # Send error event if session not found
            error_event = event_to_sse(
                type("Event", (), {
                    "event_id": "error_session_not_found",
                    "event_type": EventType.AGENT_ERROR,
                    "session_id": session_id,
                    "timestamp": asyncio.get_event_loop().time(),
                    "data": {"error": f"Session {session_id} not found"},
                    "trace_id": None,
                    "observation_id": None,
                    "run_id": None,
                    "message_id": None,
                })(),
                "error"
            )
            yield error_event.to_sse()
            return
        
        workspace_id = session.get("workspace_id")
        framework = session.get("framework", "nextjs")
        loguru.logger.debug(
            f"stream_events_generator: session found session_id={session_id} workspace_id={workspace_id} framework={framework}"
        )

    except Exception as e:
        loguru.logger.error(
            f"stream_events_generator: container setup failed session_id={session_id} error={e!s}",
            exc_info=True,
        )
        # Send error event if container setup fails
        error_event = event_to_sse(
            type("Event", (), {
                "event_id": "error_container_setup",
                "event_type": EventType.AGENT_ERROR,
                "session_id": session_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": {"error": f"Failed to ensure container: {str(e)}"},
                "trace_id": None,
                "observation_id": None,
                "run_id": None,
                "message_id": None,
            })(),
            "error"
        )
        yield error_event.to_sse()
        return
    
    try:
        # Track the last processed event timestamp for polling
        last_processed_timestamp: float | None = since_timestamp
        has_terminal_event = False
        
        # Fetch and stream historical events
        if since_timestamp is None:
            loguru.logger.debug(
                f"stream_events_generator: fetching all historical events session_id={session_id}"
            )
            historical_events = await event_dao.get_session_events(
                session_id=session_id,
                limit=1000
            )
        else:
            loguru.logger.debug(
                f"stream_events_generator: fetching events since timestamp session_id={session_id} since_timestamp={since_timestamp}"
            )
            historical_events = await event_dao.get_events_since(
                session_id=session_id,
                since_timestamp=since_timestamp,
                limit=1000
            )

        loguru.logger.info(
            f"stream_events_generator: historical events fetched session_id={session_id} count={len(historical_events)}"
        )
        for event in historical_events:
            loguru.logger.debug(
                f"stream_events_generator: streaming historical event session_id={session_id} event_type={event.event_type.value} event_id={getattr(event, 'event_id', None)}"
            )
            sse_event = event_to_sse(event)
            yield sse_event.to_sse()
            last_processed_timestamp = event.timestamp

            # Check if this is a terminal event
            if await is_terminal_event(event.event_type.value):
                has_terminal_event = True
                loguru.logger.info(
                    f"stream_events_generator: terminal event in history, ending stream session_id={session_id} event_type={event.event_type.value}"
                )
                return  # Exit generator
        
        # Continue polling for new events if no terminal event found
        if not has_terminal_event:
            loguru.logger.info(
                f"stream_events_generator: entering polling loop session_id={session_id} last_processed_timestamp={last_processed_timestamp} max_wait_time={max_wait_time}"
            )
            poll_count = 0
            no_new_events_count = 0  # 连续无新事件的轮询次数
            no_new_events_threshold = 20  # 约 10 秒无新事件时检查 agent 状态
            while True:
                poll_count += 1

                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > max_wait_time:
                    loguru.logger.warning(
                        f"stream_events_generator: timeout, ending stream session_id={session_id} elapsed={round(elapsed, 1)} max_wait_time={max_wait_time} poll_count={poll_count}"
                    )
                    # Send timeout error
                    error_event = event_to_sse(
                        type("Event", (), {
                            "event_id": "timeout",
                            "event_type": EventType.AGENT_ERROR,
                            "session_id": session_id,
                            "timestamp": asyncio.get_event_loop().time(),
                            "data": {"error": "Task timeout after 5 minutes"},
                            "trace_id": None,
                            "observation_id": None,
                            "run_id": None,
                            "message_id": None,
                        })(),
                        "error"
                    )
                    yield error_event.to_sse()
                    break
                
                # Poll for new events
                new_events = await event_dao.get_new_events(
                    session_id=session_id,
                    after_timestamp=last_processed_timestamp,
                    limit=100
                )

                if new_events:
                    no_new_events_count = 0  # 有新事件则重置计数
                    loguru.logger.debug(
                        f"stream_events_generator: new events from poll session_id={session_id} count={len(new_events)} poll_count={poll_count}"
                    )
                else:
                    no_new_events_count += 1
                    # Agent 已停止且长时间无新事件时，检查是否漏掉了 FINISH 事件
                    if no_new_events_count >= no_new_events_threshold:
                        running_service = SessionRunningService()
                        if running_service.is_running(session_id):
                            no_new_events_count = 0  # Agent 仍在运行，重置计数
                        else:
                            # Agent 已停止，检查是否漏掉了 FINISH 或异常退出
                            finish_event_doc = await event_dao.get_finish_event(session_id)
                            if finish_event_doc:
                                # 漏掉了 FINISH，补发并退出（排除 MongoDB _id）
                                doc = {k: v for k, v in finish_event_doc.items() if k != "_id"}
                                finish_event = Event(**doc)
                                sse_event = event_to_sse(finish_event)
                                yield sse_event.to_sse()
                                loguru.logger.info(
                                    f"stream_events_generator: found late FINISH, ending stream session_id={session_id}"
                                )
                                return
                            # Agent 已停止但无 FINISH 事件（如崩溃、被 kill）
                            loguru.logger.warning(
                                f"stream_events_generator: agent stopped without FINISH, ending stream session_id={session_id}"
                            )
                            error_event = event_to_sse(
                                type("Event", (), {
                                    "event_id": "agent_stopped",
                                    "event_type": EventType.AGENT_ERROR,
                                    "session_id": session_id,
                                    "timestamp": asyncio.get_event_loop().time(),
                                    "data": {"error": "Agent stopped without finish event"},
                                    "trace_id": None,
                                    "observation_id": None,
                                    "run_id": None,
                                    "message_id": None,
                                })(),
                                "error"
                            )
                            yield error_event.to_sse()
                            return

                # Stream new events
                for event in new_events:
                    loguru.logger.debug(
                        f"stream_events_generator: streaming polled event session_id={session_id} event_type={event.event_type.value}"
                    )
                    sse_event = event_to_sse(event)
                    yield sse_event.to_sse()
                    last_processed_timestamp = event.timestamp

                    # Check if this is a terminal event
                    if await is_terminal_event(event.event_type.value):
                        loguru.logger.info(
                            f"stream_events_generator: terminal event in poll, ending stream session_id={session_id} event_type={event.event_type.value} poll_count={poll_count}"
                        )
                        return  # Exit generator

                # Wait before next poll
                await asyncio.sleep(poll_interval)
                
    except asyncio.CancelledError:
        loguru.logger.info(
            f"stream_events_generator: client disconnected (CancelledError) session_id={session_id}"
        )
        pass
    except Exception as e:
        loguru.logger.error(
            f"stream_events_generator: unexpected error session_id={session_id} error={e!s}",
            exc_info=True,
        )
        # Send error event
        error_event = event_to_sse(
            type("Event", (), {
                "event_id": "error",
                "event_type": EventType.AGENT_ERROR,
                "session_id": session_id,
                "timestamp": asyncio.get_event_loop().time(),
                "data": {"error": str(e)},
                "trace_id": None,
                "observation_id": None,
                "run_id": None,
                "message_id": None,
            })(),
            "error"
        )
        yield error_event.to_sse()


@router.post("/apps/{session_id}/agent/generate")
async def generate_stream(
    session_id: str,
    body: AgentTaskRequest,
    current_user: dict = Depends(get_current_user),
):
    """Start agent task and return SSE stream.
    
    This endpoint:
    1. Validates session
    2. Submits Celery task
    3. Polls event table for new events
    4. Streams events in SSE format
    5. Continues until finish/error event or timeout
    
    Args:
        session_id: Session ID
        body: Agent task request with prompt
        current_user: Authenticated user
    
    Returns:
        StreamingResponse: SSE event stream
    """
    # Validate session
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if user owns this session
    
    workspace_id = session["workspace_id"]
    framework = session["framework"]
    
    # 创建并存储 user 消息（API 层负责创建）
    message_dao = MessageDAO()
    user_message = Message(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=body.prompt,
        parent_id=None,
        agent_name=None,
        tool_calls=[],
        tool_call_id=None,
        trace_id=None,
        timestamp=time.time(),
    )
    await message_dao.create_message(user_message)
    
    # Import Celery app and submit task（不再传递 prompt）
    from scheduler.tasks import run_team_agent_for_web_app_development
    
    # 在提交任务前记录时间戳，确保只返回本次 generate 产生的新事件
    since_timestamp = time.time()
    task = run_team_agent_for_web_app_development.delay(session_id, workspace_id, framework)
    return StreamingResponse(
        stream_events_generator(session_id=session_id, since_timestamp=since_timestamp),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post("/apps/{session_id}/agent/stop")
async def stop_agent(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Stop running agent task for the session.

    Sends a Redis signal to the agent container. The agent will save its content
    and shutdown gracefully. Waits for the container to exit before returning.
    """
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    request_stop(session_id)

    docker_service = DockerService()
    exited = await docker_service.wait_agent_container_exit(
        session_id, timeout_seconds=90
    )
    SessionRunningService().clear_running(session_id)
    return {"success": True, "exited": exited}


@router.get("/apps/{session_id}/agent/history")
async def get_history(
    session_id: str,
    limit: int = Query(100, description="Maximum number of messages to return", ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
):
    """Get historical messages for a session.
    
    This endpoint is used when entering a session detail page to load
    all historical messages.
    
    Args:
        session_id: Session ID
        limit: Maximum number of messages to return
        current_user: Authenticated user
    
    Returns:
        dict: {"messages": [Message]}
    """
    # Validate session
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if user owns this session
    
    # Get historical messages
    from mgx_api.dao import MessageDAO
    message_dao = MessageDAO()
    messages = await message_dao.get_session_messages(session_id, limit)
    
    # Convert Message objects to dict
    return {
        "messages": [msg.model_dump() for msg in messages]
    }


@router.get("/apps/{session_id}/agent/stream-continue")
async def stream_continue(
    session_id: str,
    since_timestamp: float | None = Query(None, description="Unix timestamp to resume from; omit for all events"),
    current_user: dict = Depends(get_current_user),
):
    """Resume SSE stream from a specific timestamp.
    
    This endpoint is used for reconnection after disconnection.
    It:
    1. Fetches events (since_timestamp=None: all; else: after timestamp)
    2. Streams historical events
    3. If task is still running, continues polling for new events
    4. Streams until finish/error event
    
    Args:
        session_id: Session ID
        since_timestamp: Unix timestamp to resume from; None means return all events
        current_user: Authenticated user
    
    Returns:
        StreamingResponse: SSE event stream
    """
    # Validate session
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if user owns this session
    
    # Return SSE stream using shared generator
    return StreamingResponse(
        stream_events_generator(session_id=session_id, since_timestamp=since_timestamp),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

