"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.core.auth import verify_api_key
from backend.core.config import settings
from backend.core.models import AuditRequest, AuditResponse, ExplainRequest, ExplainResponse
from backend.core.security import (
    sanitize_error_message,
    validate_schema_input,
    validate_sql_input,
)
from backend.services.pipeline import audit_queries

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting SQL Auditor API...")
    yield
    logger.info("Shutting down SQL Auditor API...")


app = FastAPI(
    title="SQL Auditor API",
    description="LLM-driven SQL optimization and analysis tool",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with secure defaults
cors_origins = (
    settings.cors_origins.split(",")
    if hasattr(settings, "cors_origins")
    else ["http://localhost:5173"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint with metrics."""
    from backend.core.monitoring import metrics

    return {
        "ok": True,
        "metrics": metrics.get_metrics(),
        "version": "0.1.0",
    }


@app.get("/api/llm/costs")
async def get_llm_costs(_: bool = Security(verify_api_key)):
    """Get LLM usage and cost information."""
    from backend.services.llm.cost_tracker import get_cost_tracker
    
    try:
        tracker = get_cost_tracker()
        report = tracker.get_usage_report(days=30)
        budget_status = tracker.check_budget(settings.llm_budget_monthly, days=30)
        
        return {
            "usage": report,
            "budget": budget_status,
        }
    except Exception as e:
        logger.error(f"Error getting LLM costs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cost information")


@app.get("/metrics")
async def get_prometheus_metrics():
    """Expose Prometheus metrics."""
    from backend.core.monitoring import metrics
    from fastapi.responses import Response

    return Response(content=metrics.get_prometheus_data(), media_type="text/plain")


@app.get("/api/history")
async def get_audit_history(limit: int = 10, _: bool = Security(verify_api_key)):
    """List recent audit history."""
    from backend.services.persistence import get_persistence
    
    try:
        persistence = get_persistence()
        history = await persistence.list_recent_audits(limit=limit)
        return history
    except Exception as e:
        logger.error(f"Error getting audit history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit history")


@app.get("/api/history/{audit_id}")
async def get_audit_detail(audit_id: int, _: bool = Security(verify_api_key)):
    """Get detailed audit result by ID."""
    from backend.services.persistence import get_persistence
    
    try:
        persistence = get_persistence()
        audit = await persistence.get_audit(audit_id)
        if not audit:
            raise HTTPException(status_code=404, detail="Audit not found")
        return audit
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit detail")




@app.post("/api/audit", response_model=AuditResponse)
@limiter.limit("10/minute")
async def audit(
    audit_request: AuditRequest,
    request: Request = None,
    _: bool = Security(verify_api_key),
):
    """
    Audit SQL queries for performance issues.

    Returns comprehensive analysis including issues, rewrites, index suggestions, and LLM explanations.
    """
    try:
        # Validate inputs
        validate_schema_input(audit_request.schema_ddl, settings.max_schema_length)

        for idx, query in enumerate(audit_request.queries):
            validate_sql_input(query, settings.max_query_length)

        # Run audit pipeline
        response = await audit_queries(
            schema_ddl=audit_request.schema_ddl,
            queries=audit_request.queries,
            dialect=audit_request.dialect,
            use_llm=True,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in audit endpoint: {e}", exc_info=True)
        sanitized_msg = sanitize_error_message(e)
        raise HTTPException(status_code=500, detail=sanitized_msg)


@app.post("/api/explain", response_model=ExplainResponse)
@limiter.limit("10/minute")
async def explain(
    explain_request: ExplainRequest,
    request: Request = None,
    _: bool = Security(verify_api_key),
):
    """
    Explain and optimize a single SQL query.

    Returns issues, optimized rewrite, and LLM explanation for a single query.
    """
    try:
        # Validate inputs
        validate_schema_input(explain_request.schema_ddl, settings.max_schema_length)
        validate_sql_input(explain_request.query, settings.max_query_length)

        # Run audit on single query
        audit_response = await audit_queries(
            schema_ddl=explain_request.schema_ddl,
            queries=[explain_request.query],
            dialect=explain_request.dialect,
            use_llm=True,
        )

        # Convert to ExplainResponse
        rewrite = audit_response.rewrites[0] if audit_response.rewrites else None

        return ExplainResponse(
            issues=audit_response.issues,
            rewrite=rewrite,
            llm_explain=audit_response.llm_explain,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in explain endpoint: {e}", exc_info=True)
        sanitized_msg = sanitize_error_message(e)
        raise HTTPException(status_code=500, detail=sanitized_msg)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
