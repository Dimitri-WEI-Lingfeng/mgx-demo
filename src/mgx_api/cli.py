"""CLI entry point for MGX API."""
import uvicorn


def run_api():
    """Run MGX API server."""
    uvicorn.run(
        "mgx_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    run_api()
