"""CLI entry point for OAuth2 Provider."""
import uvicorn


def run_provider():
    """Run OAuth2 Provider server."""
    uvicorn.run(
        "oauth2_provider.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )


if __name__ == "__main__":
    run_provider()
