from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

class IntentMode(str, Enum):
    CHAT='CHAT'; QUESTION='QUESTION'; ANALYZE='ANALYZE'; ACTION='ACTION'; CONTINUE='CONTINUE'; CANCEL='CANCEL'
class RunStatus(str, Enum):
    PLANNED='PLANNED'; RUNNING='RUNNING'; CANCEL_REQUESTED='CANCEL_REQUESTED'; CANCELLED='CANCELLED'; CANCEL_FAILED='CANCEL_FAILED'; SUCCESS='SUCCESS'; FAILED='FAILED'; PARTIAL='PARTIAL'; BLOCKED='BLOCKED'; UNVERIFIED='UNVERIFIED'
class ConstraintStatus(str, Enum):
    ACTIVE='ACTIVE'; REVOKED='REVOKED'; SUPERSEDED='SUPERSEDED'; EXPIRED='EXPIRED'

@dataclass
class IntentObject:
    owner_intent: IntentMode; conversation_mode:str=''; target:str|None=None; requested_action:str|None=None
    constraints:list[str]=field(default_factory=list); context_references:list[str]=field(default_factory=list)
    tools_required:list[str]=field(default_factory=list); forbidden_actions:list[str]=field(default_factory=list)
    expected_result:str=''; confidence:float=0.0; reason:str=''; explicit_command:bool=False
    prospective_only:bool=False; needs_clarification:bool=False
    def to_dict(self):
        d=asdict(self); d['owner_intent']=self.owner_intent.value; return d

@dataclass
class ConstraintRule:
    id:str; scope:str; rule:str; effect:str; target:str|None=None; tool:str|None=None; file_scope:str|None=None
    created_at:float=0.0; source_turn:int=0; status:ConstraintStatus=ConstraintStatus.ACTIVE; superseded_by:str|None=None
    task_id:str|None=None; action_turn:int|None=None; expires_after_use:bool=False
    def to_dict(self):
        d=asdict(self); d['status']=self.status.value; return d

@dataclass
class ToolSpec:
    name:str; target:str; description:str; inputs:dict[str,Any]; outputs:dict[str,Any]; side_effects:list[str]
    requirements:list[str]; limitations:list[str]; success_conditions:list[str]; required_evidence:list[str]; failure_conditions:list[str]
    supported_intents:list[str]=field(default_factory=lambda:['ACTION','CONTINUE'])
    def public_dict(self): return asdict(self)

@dataclass
class ActionPlan:
    target:str; tool_name:str; action:str; fields:dict[str,Any]=field(default_factory=dict); files:list[str]=field(default_factory=list)
    constraints:list[str]=field(default_factory=list); forbidden_actions:list[str]=field(default_factory=list); expected_result:str=''
    needs_user:str=''; reason:str=''; confidence:float=0.0; status:RunStatus=RunStatus.PLANNED; execution_id:str=''
    def to_dict(self):
        d=asdict(self); d['status']=self.status.value; d['brain_mode']='v11_3_core'; return d

@dataclass
class VerificationResult:
    status:RunStatus; ok:bool; evidence:list[str]=field(default_factory=list); message:str=''; execution_id:str=''
    def to_dict(self):
        d=asdict(self); d['status']=self.status.value; return d
