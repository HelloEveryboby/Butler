import logging
import threading
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from butler.core.secret_vault import secret_vault
from butler.core.sensing_api import sensing_api
from butler.core.sec_utils.certs import generate_self_signed_cert

logger = logging.getLogger("APIGateway")

app = FastAPI(
    title="Butler Secure API Gateway",
    description="Secured, asynchronous REST API Gateway for the Butler Automation system.",
    version="2.0.0"
)

# 1. Bearer Token Authentication Scheme
security_scheme = HTTPBearer()

def verify_api_token(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """Verifies the REST API Bearer token against the value stored in SecretVault."""
    token = credentials.credentials
    try:
        expected_token = secret_vault.get_secret("rest_api_bearer_token")
    except Exception as e:
        logger.error(f"Error reading token from SecretVault: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vault not initialized or inaccessible."
        )

    if not expected_token or token != expected_token:
        logger.warning("Unauthorized REST API request attempted.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

# 2. CORS Whitelist Mapping
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost:3000",
    "https://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Custom HTTP Protection Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 4. REST API Routes
@app.get("/health")
def health_check():
    """Simple authenticated/unauthenticated health check."""
    return {"status": "ok", "service": "butler-api-gateway", "version": "2.0.0"}

@app.post("/sensor/data")
def post_sensor_data(data: dict, token: str = Depends(verify_api_token)):
    """
    Asynchronously parses JSON sensor data and forwards it to SensingAPI.
    Requires Bearer Token authentication.
    """
    if not sensing_api:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SensingAPI is not initialized."
        )

    import json
    try:
        # Convert dict payload back to string to match process_sensor_data's interface
        data_str = json.dumps(data)
        sensing_api.process_sensor_data(data_str)
        return {"status": "success", "message": "Sensor data processed asynchronously"}
    except Exception as e:
        logger.error(f"Failed to process sensor data via REST API: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process sensor data: {str(e)}"
        )

# 5. Background Thread API Server Launcher
def run_api_server(host: str = "0.0.0.0", port: int = 5001, use_ssl: bool = True):
    """Launches the FastAPI Gateway using uvicorn."""
    ssl_cert, ssl_key = None, None
    if use_ssl:
        try:
            ssl_cert, ssl_key = generate_self_signed_cert()
            logger.info(f"Using SSL certificates from: {ssl_cert}")
        except Exception as e:
            logger.error(f"Failed to generate self-signed cert for API server fallback: {e}")
            use_ssl = False

    config_kwargs = {
        "app": "butler.core.api:app",
        "host": host,
        "port": port,
        "log_level": "info",
    }
    if use_ssl and ssl_cert and ssl_key:
        config_kwargs["ssl_certfile"] = str(ssl_cert)
        config_kwargs["ssl_keyfile"] = str(ssl_key)

    uvicorn.run(**config_kwargs)

def start_api_server_thread(host: str = "0.0.0.0", port: int = 5001, use_ssl: bool = True) -> threading.Thread:
    """Starts the REST API Server in a daemon background thread."""
    t = threading.Thread(target=run_api_server, args=(host, port, use_ssl), daemon=True)
    t.start()
    logger.info(f"Secure REST API server thread launched on {host}:{port}")
    return t
