"""Bounded extraction contracts. These are proposals, never clinical decisions."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ProfileFact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    section: str = Field(max_length=64)
    field: str = Field(max_length=64)
    value: str = Field(min_length=1, max_length=500)
    source_date: date | None = None
    evidence: str = Field(min_length=1, max_length=2000)


class QuestionnaireExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_type: Literal['questionnaire'] = 'questionnaire'
    facts: list[ProfileFact] = Field(default_factory=list, max_length=200)


class HistoryExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_type: Literal['history'] = 'history'
    facts: list[ProfileFact] = Field(default_factory=list, max_length=200)


class ReportExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_type: Literal['report'] = 'report'
    facts: list[ProfileFact] = Field(default_factory=list, max_length=200)


SCHEMAS = {'report': ReportExtraction, 'questionnaire': QuestionnaireExtraction, 'history': HistoryExtraction}
