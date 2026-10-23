"""Small stable DTO for daemon connectivity diagnostics."""
from pydantic import BaseModel

class DockerDiagnostic(BaseModel):
    status: str
    version: str | None = None
    containers: int | None = None
    message: str | None = None
