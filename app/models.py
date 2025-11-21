from pydantic import BaseModel, HttpUrl, Field
from typing import List


class ExtractionRequest(BaseModel):
    """Request model for PDF extraction endpoint."""
    url: HttpUrl = Field(..., description="URL of the page containing PDFs")
    s3_bucket: str = Field(..., description="S3 bucket name for storage")
    s3_prefix: str = Field(..., description="S3 prefix/folder path")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://caleprocure.ca.gov/event/0850/0000036230",
                "s3_bucket": "my-solicitations",
                "s3_prefix": "ecal/event-036230/"
            }
        }


class ExtractionResponse(BaseModel):
    """Response model for PDF extraction endpoint."""
    status: str = Field(..., description="Status of the extraction (success/error)")
    files: List[str] = Field(default_factory=list, description="List of S3 file paths")
    message: str = Field(default="", description="Additional message or error details")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "files": [
                    "s3://my-solicitations/ecal/event-036230/solicitation.pdf",
                    "s3://my-solicitations/ecal/event-036230/amendments.pdf"
                ],
                "message": "Successfully extracted 2 PDF files"
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(default="1.0.0", description="API version")
