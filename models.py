"""Pydantic models for UML diagram state management."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# Supported UML relationship types
RelationType = Literal[
    "Association",
    "Aggregation",
    "Composition",
    "Generalization",
    "Dependency",
]

# Supported visibility levels in UML
VisibilityType = Literal["public", "private", "protected", "package"]


class AttributeModel(BaseModel):
    """Represents a class attribute (property/field) in UML."""

    name: str = Field(..., description="Attribute name")
    type: str = Field(default="string", description="Attribute data type (e.g. str, int, UUID, or ClassName)")
    visibility: VisibilityType = Field(default="public", description="Visibility level: public, private, protected, package")


class MethodModel(BaseModel):
    """Represents a class method (operation) in UML."""

    name: str = Field(..., description="Method name")
    return_type: str = Field(default="void", description="Return type of the method (e.g. void, bool, dict, ClassName)")
    params: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of parameters, each dict usually having 'name' and 'type' keys",
    )


class ClassModel(BaseModel):
    """Represents a UML Class classifier."""

    id: str = Field(..., description="Unique identifier for the class (XML ID)")
    name: str = Field(..., description="Name of the class")
    attributes: list[AttributeModel] = Field(default_factory=list, description="Class attributes")
    methods: list[MethodModel] = Field(default_factory=list, description="Class methods")


class RelationModel(BaseModel):
    """Represents a UML relationship between two classes."""

    id: str = Field(..., description="Unique identifier for the relationship")
    source_id: str = Field(..., description="Source class ID")
    target_id: str = Field(..., description="Target class ID")
    relation_type: RelationType = Field(..., description="Type of relationship")
    source_multiplicity: str = Field(default="", description="Multiplicity at source end (e.g. 1, 0..1, *, 1..*)")
    target_multiplicity: str = Field(default="", description="Multiplicity at target end (e.g. 1, 0..1, *, 1..*)")


class DiagramState(BaseModel):
    """In-memory state of the active UML diagram."""

    name: str = Field(default="SoftwareArchitecture", description="Diagram / Model name")
    classes: dict[str, ClassModel] = Field(default_factory=dict, description="Map of class_id -> ClassModel")
    relations: list[RelationModel] = Field(default_factory=list, description="List of relations")

    def clear(self, name: str = "SoftwareArchitecture") -> None:
        """Reset the diagram state with a new name."""
        self.name = name
        self.classes.clear()
        self.relations.clear()

    def find_class(self, identifier: str) -> Optional[ClassModel]:
        """Find a class by its ID or by its name (case-insensitive fallback)."""
        if identifier in self.classes:
            return self.classes[identifier]

        # Search by exact name first
        for cls in self.classes.values():
            if cls.name == identifier:
                return cls

        # Search by case-insensitive name
        identifier_lower = identifier.lower()
        for cls in self.classes.values():
            if cls.name.lower() == identifier_lower:
                return cls

        return None
