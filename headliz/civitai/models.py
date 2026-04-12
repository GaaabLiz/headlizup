from pydantic import BaseModel, Field


class UploadToCivitaiRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded image binary data")
    title: str = Field(..., min_length=1, max_length=200, description="Title of the image post")
    tags: list[str] = Field(default_factory=list, description="List of tags for the image")
    description: str = Field(default="", max_length=5000, description="Description of the image post")


class UploadToCivitaiResponse(BaseModel):
    success: bool
    message: str
    post_url: str | None = None
