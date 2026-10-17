from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Requirement(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id: str
    text: str = Field(min_length=4, max_length=2500)
    kind: Literal['functional','non-functional','business-rule','assumption'] = 'functional'
    source_id: str = 'SRC-001'
    source_reference: str = 'Brief'

class Analysis(BaseModel):
    requirements: list[Requirement] = Field(min_length=1, max_length=30)
    open_questions: list[str] = Field(default_factory=list)
    potential_conflicts: list[str] = Field(default_factory=list)

class Story(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id: str
    requirement_ids: list[str] = Field(min_length=1)
    role: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    benefit: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)

class StorySet(BaseModel):
    stories: list[Story] = Field(min_length=1, max_length=30)
    assumptions: list[str] = Field(default_factory=list)

def _gemini_field_schema(schema: dict[str, object]) -> None:
    # Gemini's response_schema rejects this keyword; Pydantic still forbids extras locally.
    schema.pop('additionalProperties', None)

class UIField(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra=_gemini_field_schema)
    id: str
    label: str
    type: Literal['text','date','select','email'] = 'text'
    required: bool = False
    options: list[str] = Field(default_factory=list)

class Screen(BaseModel):
    id: str
    title: str
    description: str = ''
    kind: Literal['intake','approval','checklist']
    fields: list[UIField] = Field(default_factory=list)

class Concept(BaseModel):
    id: str
    name: str
    description: str
    primaryColor: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')

class PrototypeSpec(BaseModel):
    title: str
    subtitle: str
    concepts: list[Concept] = Field(min_length=2, max_length=2)
    screens: list[Screen] = Field(min_length=3, max_length=3)
    primary_color: str = Field(default='#2563eb', pattern=r'^#[0-9a-fA-F]{6}$')

def validate_prototype(spec: PrototypeSpec) -> None:
    if [s.kind for s in spec.screens] != ['intake', 'approval', 'checklist']:
        raise ValueError('Prototype must have intake, approval, checklist screens in order')
    for items in (spec.screens, spec.concepts, *(s.fields for s in spec.screens)):
        if any(not item.id.strip() for item in items) or len({item.id for item in items}) != len(items):
            raise ValueError('Prototype IDs must be nonempty and unique within screens, concepts and fields')
    if not spec.title.strip() or any(not s.title.strip() for s in spec.screens):
        raise ValueError('Prototype and screen titles must not be empty')
    if any(not c.name.strip() for c in spec.concepts):
        raise ValueError('Prototype concept names must not be empty')
    if not spec.screens[0].fields:
        raise ValueError('Prototype intake must contain fields')
    if any(s.fields for s in spec.screens[1:]):
        raise ValueError('Only the intake screen supports editable fields')
    for field in spec.screens[0].fields:
        if not field.label.strip():
            raise ValueError('Prototype field labels must not be empty')
        if field.type == 'select' and (not field.options or any(not o.strip() for o in field.options)):
            raise ValueError('Prototype select fields must contain nonempty options')

class PrototypeUpdate(BaseModel):
    prototype: PrototypeSpec

class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=120)
    brief: str = Field(min_length=25, max_length=20000)
    description: str = Field(default='', max_length=2000)
    business_domain: str = Field(default='', max_length=120)
    client_name: str = Field(default='', max_length=160)
    client_email: str = Field(default='', max_length=254, pattern=r'^(?:[^\s@]+@[^\s@]+\.[^\s@]+)?$')
    expected_timeline: str = Field(default='', max_length=200)
    additional_notes: str = Field(default='', max_length=4000)

class ApprovalCreate(BaseModel):
    artifact_version: int = Field(ge=1)
    decision: Literal['approved','rejected']
    note: str = ''

class RequirementsUpdate(BaseModel):
    requirements: list[Requirement] = Field(max_length=30)
    open_questions: list[str] = Field(default_factory=list)

class StoriesUpdate(BaseModel):
    stories: list[Story] = Field(max_length=30)

def _srs_generation_schema(schema: dict[str, object]) -> None:
    # Keep generation constraints small; Pydantic still enforces all field limits locally.
    for key in ('minLength', 'maxLength', 'minItems', 'maxItems'):
        schema.pop(key, None)
    for value in schema.values():
        if isinstance(value, dict):
            _srs_generation_schema(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _srs_generation_schema(item)

class SRSSection(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra=_srs_generation_schema)
    id: Literal['purpose','scope','functional','non_functional','interfaces','data','assumptions','acceptance']
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=6000)
    requirement_ids: list[str] = Field(default_factory=list, max_length=30)
    source_ids: list[str] = Field(default_factory=list, max_length=50)

class SRSDocument(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra=_srs_generation_schema)
    title: str = Field(min_length=1, max_length=160)
    sections: list[SRSSection] = Field(min_length=8, max_length=8)

class SRSGenerate(BaseModel):
    base_version: int = Field(ge=0)

class SRSUpdate(SRSGenerate):
    document: SRSDocument

class JiraCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirmed: Literal[True]

class VoiceStart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: Literal[True]

class HandoffEmailDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    recipients: list[str] = Field(min_length=1, max_length=10)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=12000)

class HandoffEmailSend(HandoffEmailDraft):
    fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirmed: Literal[True]

class DemoAction(BaseModel):
    action: Literal['submit','approve','request_changes','toggle']
    request_id: str | None = None
    values: dict[str, str] = Field(default_factory=dict)
    item: str | None = None
