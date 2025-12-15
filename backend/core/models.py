"""Pydantic models for API requests and responses."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AuditRequest(BaseModel):
    """Request model for SQL audit endpoint."""

    schema_ddl: str = Field(..., alias="schema", description="Database schema DDL")
    queries: list[str] = Field(..., min_length=1, description="SQL queries to audit")
    dialect: Literal["postgres", "sqlite"] = Field(default="postgres", description="SQL dialect")
    options: Optional[dict[str, int]] = Field(
        default=None, description="Optional settings like maxSuggestions"
    )

    class Config:
        populate_by_name = True


class Issue(BaseModel):
    """Represents a detected issue in a SQL query."""

    code: str = Field(..., description="Issue code (e.g., R001)")
    severity: Literal["info", "warn", "error"] = Field(..., description="Issue severity level")
    message: str = Field(..., description="Human-readable issue message")
    snippet: Optional[str] = Field(None, description="Relevant SQL snippet")
    line: Optional[int] = Field(None, description="Line number in query")
    rule: Optional[str] = Field(None, description="Rule name that detected this")
    query_index: Optional[int] = Field(None, description="Index of query in the input list")


class Rewrite(BaseModel):
    """Optimized SQL rewrite suggestion."""

    original: str = Field(..., description="Original SQL query")
    optimized: str = Field(..., description="Optimized SQL query")
    rationale: str = Field(..., description="Explanation of changes")
    query_index: Optional[int] = Field(None, description="Index of query in the input list")


class IndexSuggestion(BaseModel):
    """Index recommendation."""

    table: str = Field(..., description="Table name")
    columns: list[str] = Field(..., description="Column names for index")
    type: Optional[str] = Field(default="btree", description="Index type (btree, gin, gist, etc.)")
    rationale: str = Field(..., description="Why this index helps")
    expected_improvement: Optional[str] = Field(
        None, description="Expected performance improvement"
    )


class Summary(BaseModel):
    """Audit summary statistics."""

    total_issues: int = Field(..., alias="totalIssues")
    high_severity: int = Field(..., alias="highSeverity")
    est_improvement: Optional[str] = Field(
        None, alias="estImprovement", description="Estimated improvement"
    )

    class Config:
        populate_by_name = True


class AuditResponse(BaseModel):
    """Response model for SQL audit endpoint."""

    summary: Summary
    issues: list[Issue]
    rewrites: list[Rewrite]
    indexes: list[IndexSuggestion] = Field(default_factory=list)
    llm_explain: str = Field(
        default="", alias="llmExplain", description="LLM-generated explanation"
    )

    class Config:
        populate_by_name = True


class ExplainRequest(BaseModel):
    """Request model for single query explain endpoint."""

    schema_ddl: str = Field(..., alias="schema", description="Database schema DDL")
    query: str = Field(..., description="SQL query to explain")
    dialect: Literal["postgres", "sqlite"] = Field(default="postgres", description="SQL dialect")

    class Config:
        populate_by_name = True


class ExplainResponse(BaseModel):
    """Response model for explain endpoint."""

    issues: list[Issue]
    rewrite: Optional[Rewrite] = None
    llm_explain: str = Field(
        default="", alias="llmExplain", description="LLM-generated explanation"
    )

    class Config:
        populate_by_name = True
