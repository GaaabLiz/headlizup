from pydantic import BaseModel, Field


class UploadToPinterestRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded image binary data")
    title: str = Field(..., min_length=1, max_length=200, description="Title of the pin")
    description: str = Field(default="", max_length=5000, description="Description of the pin")
    tags: list[str] = Field(default_factory=list, description="List of tags for the pin")
    board_name: str = Field(default="", description="Name of the board to pin to (empty = first available)")


class UploadToPinterestResponse(BaseModel):
    success: bool
    message: str
    pin_url: str | None = None
