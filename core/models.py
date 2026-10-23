"""Pydantic data models and Rules Engine for UML and ERD diagrams."""

import uuid
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator

# Base Node with auto-generated unique XMI ID
class BaseNode(BaseModel):
    """Base architectural node carrying an XML-valid unique XMI ID and rich documentation."""

    id: str = Field(default_factory=lambda: "xmi_" + uuid.uuid4().hex)
    description: str = Field(default="", description="Description or documentation text for Open Specification")


# ---------------------------------------------------------
# 1. UML Class Diagram Models
# ---------------------------------------------------------

ClassRelationType = Literal[
    "Association",
    "Generalization",
    "Composition",
    "Aggregation",
    "Dependency",
    "Realization",
]

VisibilityType = Literal["public", "private", "protected"]
ParamDirectionType = Literal["in", "out", "return"]
ClassElementType = Literal["Class", "Interface"]


class AttributeModel(BaseNode):
    """Represents a UML class attribute/property."""

    name: str = Field(..., min_length=1, description="Attribute name")
    type: str = Field(default="string", description="Data type")
    visibility: VisibilityType = Field(default="public", description="Visibility level")
    multiplicity: str = Field(default="", description="Multiplicity (e.g. '1', '0..1', '*')")


class MethodParam(BaseNode):
    """Represents a method parameter."""

    name: str = Field(..., min_length=1, description="Parameter name")
    type: str = Field(default="string", description="Parameter data type")
    direction: ParamDirectionType = Field(default="in", description="Parameter direction (in/out/return)")


class MethodModel(BaseNode):
    """Represents a UML class method/operation."""

    name: str = Field(..., min_length=1, description="Method name")
    return_type: str = Field(default="void", description="Return type")
    params: list[MethodParam] = Field(default_factory=list, description="Method parameter list")


class ClassNode(BaseNode):
    """Represents a UML Class or Interface classifier."""

    name: str = Field(..., min_length=1, description="Class name")
    is_abstract: bool = Field(default=False, description="Whether the class is abstract")
    element_type: ClassElementType = Field(default="Class", description="Class or Interface")
    package_id: Optional[str] = Field(default=None, description="Optional parent package ID")
    attributes: list[AttributeModel] = Field(default_factory=list, description="Class attributes")
    methods: list[MethodModel] = Field(default_factory=list, description="Class operations")

    @model_validator(mode="after")
    def validate_interface_rules(self) -> "ClassNode":
        if self.element_type == "Interface":
            for attr in self.attributes:
                if attr.visibility == "private":
                    raise ValueError(
                        f"UML Rule Violation: Interface '{self.name}' cannot contain private attributes."
                    )
        return self


class PackageNode(BaseNode):
    """Represents a UML Package namespace that can contain classes and subpackages."""

    name: str = Field(..., min_length=1, description="Package name")
    parent_package_id: Optional[str] = Field(default=None, description="ID of parent package if nested")
    child_package_ids: list[str] = Field(default_factory=list, description="IDs of nested packages")
    class_ids: list[str] = Field(default_factory=list, description="IDs of classes contained in this package")


# Backwards compatibility alias
ClassModel = ClassNode
PackageModel = PackageNode


# ---------------------------------------------------------
# 2. ER Diagram Models
# ---------------------------------------------------------

ERRelationType = Literal["1:1", "1:N", "M:N"]


class ColumnModel(BaseNode):
    """Represents an entity/table column."""

    name: str = Field(..., min_length=1, description="Column name")
    type: str = Field(default="VARCHAR", description="Column SQL / primitive data type")
    is_pk: bool = Field(default=False, description="Flag indicating Primary Key constraint")
    is_fk: bool = Field(default=False, description="Flag indicating Foreign Key constraint")
    length: Optional[int] = Field(default=None, description="Optional length or precision (e.g. 255)")
    is_nullable: bool = Field(default=True, description="Whether column allows NULL values")

    @model_validator(mode="before")
    @classmethod
    def handle_pk_fk_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "is_primary_key" in data and "is_pk" not in data:
                data["is_pk"] = data["is_primary_key"]
            if "is_foreign_key" in data and "is_fk" not in data:
                data["is_fk"] = data["is_foreign_key"]
        return data

    @property
    def is_primary_key(self) -> bool:
        return self.is_pk

    @property
    def is_foreign_key(self) -> bool:
        return self.is_fk

    @model_validator(mode="after")
    def validate_pk_not_nullable(self) -> "ColumnModel":
        if self.is_pk:
            self.is_nullable = False
        return self


class EntityNode(BaseNode):
    """Represents an ER entity (table)."""

    name: str = Field(..., min_length=1, description="Entity name")
    columns: list[ColumnModel] = Field(default_factory=list, description="Entity columns")

    def has_foreign_key(self) -> bool:
        return any(col.is_fk for col in self.columns)

    def has_primary_key(self) -> bool:
        return any(col.is_pk for col in self.columns)


# Backwards compatibility alias
EntityModel = EntityNode


# ---------------------------------------------------------
# 3. Use Case Diagram Models
# ---------------------------------------------------------

UCRelationType = Literal["Association", "Include", "Extend"]


class ActorNode(BaseNode):
    """Represents an external Actor in a Use Case diagram."""

    name: str = Field(..., min_length=1, description="Actor name")


class UseCaseNode(BaseNode):
    """Represents a Use Case."""

    name: str = Field(..., min_length=1, description="Use Case name")


# Backwards compatibility aliases
ActorModel = ActorNode
UseCaseModel = UseCaseNode


# ---------------------------------------------------------
# 4. State Machine Diagram Models
# ---------------------------------------------------------

StateType = Literal["Initial", "State", "Final"]


class StateNode(BaseNode):
    """Represents a state vertex in a State Machine."""

    name: str = Field(..., min_length=1, description="State name")
    type: StateType = Field(default="State", description="State vertex type: Initial, State, Final")
    entry_action: str = Field(default="", description="Behavior executed upon state entry (entry / action)")
    do_activity: str = Field(default="", description="Ongoing activity executed while in state (do / activity)")
    exit_action: str = Field(default="", description="Behavior executed upon state exit (exit / action)")


# Backwards compatibility alias
StateModel = StateNode


# ---------------------------------------------------------
# 5. General Relationships & Rules Engine
# ---------------------------------------------------------

class RelationModel(BaseNode):
    """Represents a relationship or connection between two nodes."""

    name: str = Field(default="", description="Relationship name or label")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    type: str = Field(default="Association", description="Relationship type")
    source_multiplicity: str = Field(default="", description="Multiplicity at source end (e.g. '0..1', '1', '*')")
    target_multiplicity: str = Field(default="", description="Multiplicity at target end (e.g. '0..1', '1', '*')")
    trigger_event: str = Field(default="", description="Trigger event name for state transitions")
    guard_condition: str = Field(default="", description="Optional guard condition expression, e.g. '[balance >= total]'")

    @model_validator(mode="after")
    def validate_rules(self) -> "RelationModel":
        # 1. No self-referencing relationship for hierarchy/extensions
        if self.type in ("Generalization", "Include", "Extend") and self.source_id == self.target_id:
            raise ValueError(
                f"UML Rule Violation: Element cannot have a self-referencing '{self.type}' relationship."
            )

        # 2. Context-aware validation via ProjectState if available
        try:
            from core.state import state

            # Rule: Include / Extend only allowed between UseCaseNode
            if self.type in ("Include", "Extend"):
                src_node = state.find_node_by_id(self.source_id)
                tgt_node = state.find_node_by_id(self.target_id)
                if src_node is not None and not isinstance(src_node, UseCaseNode):
                    raise ValueError(
                        f"UML Rule Violation: '{self.type}' relationship source must be a UseCaseNode, "
                        f"got '{type(src_node).__name__}' ('{getattr(src_node, 'name', self.source_id)}')."
                    )
                if tgt_node is not None and not isinstance(tgt_node, UseCaseNode):
                    raise ValueError(
                        f"UML Rule Violation: '{self.type}' relationship target must be a UseCaseNode, "
                        f"got '{type(tgt_node).__name__}' ('{getattr(tgt_node, 'name', self.target_id)}')."
                    )

            # Rule: 1:N in ERD requires target entity to have at least one foreign key column
            if self.type == "1:N":
                tgt_node = state.find_node_by_id(self.target_id)
                if tgt_node is not None and isinstance(tgt_node, EntityNode):
                    if not tgt_node.has_foreign_key():
                        raise ValueError(
                            f"ERD Rule Violation: Relation 1:N requires target entity '{tgt_node.name}' "
                            f"to have at least one Foreign Key column defined (is_fk=True)."
                        )

            # Rule: Cyclic inheritance detection
            if self.type == "Generalization":
                if state.would_cause_inheritance_cycle(self.source_id, self.target_id):
                    src_cls = state.find_class(self.source_id)
                    tgt_cls = state.find_class(self.target_id)
                    src_name = src_cls.name if src_cls else self.source_id
                    tgt_name = tgt_cls.name if tgt_cls else self.target_id
                    raise ValueError(
                        f"UML Rule Violation: Cyclic inheritance detected! "
                        f"Class '{src_name}' cannot inherit from '{tgt_name}' because an inheritance loop would be formed."
                    )
        except ImportError:
            pass

        return self


# ---------------------------------------------------------
# 6. Universal Diagram Elements (Notes & Boundaries)
# ---------------------------------------------------------

class NoteNode(BaseNode):
    """Represents an architectural annotation Note (yellow sticky comment) on diagrams."""

    name: str = Field(default="Note", description="Note label")
    text: str = Field(..., min_length=1, description="Text content of the note")
    target_id: Optional[str] = Field(default=None, description="Optional ID of model element linked via Anchor")


class SystemBoundaryNode(BaseNode):
    """Represents a System Boundary box on a Use Case Diagram enclosing use cases."""

    name: str = Field(default="System", min_length=1, description="Name/title of the system boundary")
    use_case_ids: list[str] = Field(default_factory=list, description="IDs of use cases inside this boundary")


# Backwards compatibility aliases
ClassRelation = RelationModel
ERRelation = RelationModel
UCRelation = RelationModel
TransitionModel = RelationModel
NoteModel = NoteNode
SystemBoundaryModel = SystemBoundaryNode
