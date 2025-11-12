"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.models import AuditRequest, AuditResponse, ExplainRequest, ExplainResponse
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"ok": True}


@app.post("/api/audit", response_model=AuditResponse)
async def audit(request: AuditRequest):
    """
    Audit SQL queries for performance issues.

    Returns comprehensive analysis including issues, rewrites, index suggestions, and LLM explanations.
    """
    try:
        # Validate input sizes
        if len(request.schema_ddl) > settings.max_schema_length:
            raise HTTPException(
                status_code=400,
                detail=f"Schema too large (max {settings.max_schema_length} chars)",
            )

        for idx, query in enumerate(request.queries):
            if len(query) > settings.max_query_length:
                raise HTTPException(
                    status_code=400,
                    detail=f"Query {idx} too large (max {settings.max_query_length} chars)",
                )

        # Run audit pipeline
        response = await audit_queries(
            schema_ddl=request.schema_ddl,
            queries=request.queries,
            dialect=request.dialect,
            use_llm=True,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in audit endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/explain", response_model=ExplainResponse)
async def explain(request: ExplainRequest):
    """
    Explain and optimize a single SQL query.

    Returns issues, optimized rewrite, and LLM explanation for a single query.
    """
    try:
        # Validate input size
        if len(request.schema_ddl) > settings.max_schema_length:
            raise HTTPException(
                status_code=400,
                detail=f"Schema too large (max {settings.max_schema_length} chars)",
            )

        if len(request.query) > settings.max_query_length:
            raise HTTPException(
                status_code=400,
                detail=f"Query too large (max {settings.max_query_length} chars)",
            )

        # Run audit on single query
        audit_response = await audit_queries(
            schema_ddl=request.schema_ddl,
            queries=[request.query],
            dialect=request.dialect,
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
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)

