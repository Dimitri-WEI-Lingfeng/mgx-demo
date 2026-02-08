"""Test SSE streaming functionality.

This script tests the SSE stream endpoints.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx


async def test_sse_stream():
    """Test SSE stream endpoint."""
    print("Testing SSE stream endpoint...")
    print("=" * 60)
    
    # Configuration
    base_url = "http://localhost:8000"
    session_id = "test_session_123"
    token = "test_token"  # TODO: Get real token from OAuth2
    
    # Prepare request
    url = f"{base_url}/api/apps/{session_id}/agent/generate"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = {
        "prompt": "Create a simple hello world API endpoint"
    }
    
    print(f"URL: {url}")
    print(f"Request: {data}")
    print("-" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=data,
                timeout=60.0
            ) as response:
                if response.status_code != 200:
                    print(f"Error: {response.status_code}")
                    print(await response.aread())
                    return
                
                print("Streaming events:")
                print("-" * 60)
                
                event_count = 0
                async for line in response.aiter_lines():
                    if line:
                        print(line)
                        event_count += 1
                
                print("-" * 60)
                print(f"Total events received: {event_count}")
                
        except Exception as e:
            print(f"Error: {e}")


async def test_stream_continue():
    """Test stream-continue endpoint."""
    print("\n\nTesting stream-continue endpoint...")
    print("=" * 60)
    
    # Configuration
    base_url = "http://localhost:8000"
    session_id = "test_session_123"
    # since_timestamp: Unix timestamp to resume from; omit for all events
    since_timestamp = 1704067200.0  # Example: 2024-01-01 00:00:00 UTC
    token = "test_token"  # TODO: Get real token from OAuth2
    
    # Prepare request (omit since_timestamp to get all events)
    url = f"{base_url}/api/apps/{session_id}/agent/stream-continue?since_timestamp={since_timestamp}"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    
    print(f"URL: {url}")
    print("-" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "GET",
                url,
                headers=headers,
                timeout=60.0
            ) as response:
                if response.status_code != 200:
                    print(f"Error: {response.status_code}")
                    print(await response.aread())
                    return
                
                print("Streaming events from since_timestamp:")
                print("-" * 60)
                
                event_count = 0
                async for line in response.aiter_lines():
                    if line:
                        print(line)
                        event_count += 1
                
                print("-" * 60)
                print(f"Total events received: {event_count}")
                
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Main test function."""
    print("SSE Stream Test Suite")
    print("=" * 60)
    print("\nNote: This test requires:")
    print("1. MGX API server running on http://localhost:8000")
    print("2. Valid authentication token")
    print("3. Existing session ID")
    print("=" * 60)
    
    # Test generate stream
    await test_sse_stream()
    
    # Test continue stream
    await test_stream_continue()


if __name__ == "__main__":
    asyncio.run(main())
