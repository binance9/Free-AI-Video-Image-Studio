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


class EditorCutRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("Điểm cuối phải lớn hơn điểm đầu")
        return self
