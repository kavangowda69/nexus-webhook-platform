from __future__ import annotations
import bentoml
from pydantic import BaseModel
from typing import Any


class InferenceRequest(BaseModel):
    input: Any
    model: str = "echo"


class InferenceResponse(BaseModel):
    model: str
    input: Any
    prediction: Any
    confidence: float = 0.95


@bentoml.service(name="nexus-inference")
class InferenceService:

    @bentoml.api
    def predict(self, request: InferenceRequest) -> InferenceResponse:
        if request.model == "echo":
            return InferenceResponse(
                model=request.model,
                input=request.input,
                prediction=f"processed:{request.input}",
                confidence=0.95
            )
        return InferenceResponse(
            model=request.model,
            input=request.input,
            prediction=None,
            confidence=0.0
        )