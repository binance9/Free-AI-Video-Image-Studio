from pydantic import BaseModel, Field, model_validator


class VideoCutRequest(BaseModel):
    source: str = Field(min_length=1, max_length=4096)
    output: str = Field(min_length=1, max_length=4096)
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class VideoMergeRequest(BaseModel):
    sources: list[str] = Field(min_length=2, max_length=100)
    output: str = Field(min_length=1, max_length=4096)


class EditorCutRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("Điểm cuối phải lớn hơn điểm đầu")
        return self


class OverlayLayer(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    type: str = Field(pattern=r"^(text|image|sticker|gif)$")
    source_kind: str | None = Field(default=None, pattern=r"^(asset|builtin|giphy)$")
    source: str | None = Field(default=None, max_length=4096)
    text: str | None = Field(default=None, max_length=1000)
    x: float = 0.5
    y: float = 0.5
    width_ratio: float = Field(default=0.22, gt=0, le=1.5)
    opacity: float = Field(default=1, ge=0.05, le=1)
    rotation: float = Field(default=0, ge=-360, le=360)
    start: float = Field(default=0, ge=0)
    end: float = Field(default=999999, ge=0)
    font_size_ratio: float = Field(default=0.05, gt=0, le=0.3)
    color: str = "#ffffff"
    outline_color: str = "#000000"
    outline_width: int = Field(default=3, ge=0, le=20)
    background: str = "#000000"
    background_opacity: float = Field(default=0, ge=0, le=1)
    font_family: str = Field(default="segoe", pattern=r"^(segoe|arial|impact|georgia)$")
    shadow_color: str = "#000000"
    shadow_opacity: float = Field(default=0, ge=0, le=1)
    shadow_blur: int = Field(default=0, ge=0, le=30)


class RenderRequest(BaseModel):
    layers: list[OverlayLayer] = Field(default_factory=list, max_length=200)
