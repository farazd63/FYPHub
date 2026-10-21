from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160, strict=True)]

class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Label
    source: Label
    destination: Label

class PolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Label
    states: list[Label] = Field(min_length=1, max_length=100)
    transitions: list[Transition] = Field(max_length=200)

    @model_validator(mode="after")
    def validate_graph(self):
        normalized = [state.casefold() for state in self.states]
        if len(normalized) != len(set(normalized)):
            raise ValueError("State labels must be unique.")
        if any(t.source not in self.states or t.destination not in self.states for t in self.transitions):
            raise ValueError("Transitions must reference states in this version.")
        return self
