"""Local MCP Server for Visual Paradigm UML Architecture Design.

Allows LLM agents to design software architecture (classes, attributes,
methods, relations) interactively and export the result to valid XMI 2.1
compatible with Visual Paradigm.
"""

import os
import uuid
from typing import Any, Optional

# Supports official MCP SDK v1 (FastMCP) and v2 (MCPServer)
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("mcp-visual-paradigm")
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("mcp-visual-paradigm")

from models import (
    AttributeModel,
    ClassModel,
    DiagramState,
    MethodModel,
    RelationModel,
    RelationType,
    VisibilityType,
)
from xmi_builder import generate_xmi

# Global in-memory diagram state
state = DiagramState()


def _normalize_visibility(vis: str) -> VisibilityType:
    """Normalize user input or shorthand symbols (+, -, #, ~) into UML visibility."""
    vis_clean = (vis or "public").strip().lower()
    mapping: dict[str, VisibilityType] = {
        "+": "public",
        "-": "private",
        "#": "protected",
        "~": "package",
        "pub": "public",
        "priv": "private",
        "prot": "protected",
        "pkg": "package",
        "public": "public",
        "private": "private",
        "protected": "protected",
        "package": "package",
    }
    return mapping.get(vis_clean, "public")


def _normalize_relation_type(rel_type: str) -> RelationType:
    """Validate and normalize relation type to the strict Literal."""
    rel_clean = (rel_type or "").strip().capitalize()
    allowed: dict[str, RelationType] = {
        "Association": "Association",
        "Aggregation": "Aggregation",
        "Composition": "Composition",
        "Generalization": "Generalization",
        "Dependency": "Dependency",
    }
    if rel_clean not in allowed:
        valid_options = ", ".join(allowed.keys())
        raise ValueError(
            f"Invalid relation_type '{rel_type}'. Allowed types: {valid_options}."
        )
    return allowed[rel_clean]


@mcp.tool()
def init_diagram(name: str = "SoftwareArchitecture") -> str:
    """Initialize a new UML diagram and clear existing in-memory state.

    Call this tool when starting the design of a new software architecture
    or when you need to discard previous changes and begin fresh.

    Args:
        name: The name of the architecture model/diagram (default: "SoftwareArchitecture").

    Returns:
        Confirmation message that diagram state has been reset.
    """
    state.clear(name=name)
    return f"Initialized new UML diagram '{name}'. All previous classes and relations have been cleared."


@mcp.tool()
def add_class(name: str) -> str:
    """Create a new UML class in the diagram.

    Generates a unique uuid4-based hex ID for the class (critical for XMI xmi:id)
    and stores it in the in-memory state.

    Args:
        name: Name of the class (e.g. 'OrderService', 'Customer', 'DatabasePool').

    Returns:
        JSON string or status confirming creation along with the unique class ID.
    """
    class_name = name.strip()
    if not class_name:
        raise ValueError("Class name cannot be empty.")

    # Check if a class with this name already exists
    existing = state.find_class(class_name)
    if existing:
        return f"Class '{class_name}' already exists with ID: {existing.id}"

    # Generate unique ID (prefixed with '_' to ensure valid XML ID specification)
    class_id = f"_{uuid.uuid4().hex}"
    new_class = ClassModel(id=class_id, name=class_name)
    state.classes[class_id] = new_class

    return f"Created class '{class_name}' with ID: {class_id}"


@mcp.tool()
def add_attribute(
    class_name: str,
    attr_name: str,
    type: str = "string",
    visibility: str = "public",
) -> str:
    """Add an attribute (field/property) to an existing UML class.

    Args:
        class_name: Name or ID of the target class to modify.
        attr_name: Name of the attribute (e.g. 'id', 'email', 'createdAt').
        type: Data type of the attribute (e.g. 'string', 'int', 'boolean', 'UUID', or another Class name).
        visibility: Access level ('public', 'private', 'protected', 'package' or symbols '+', '-', '#', '~').

    Returns:
        Confirmation message with attribute details.
    """
    target_class = state.find_class(class_name)
    if not target_class:
        available = [c.name for c in state.classes.values()]
        raise ValueError(
            f"Class '{class_name}' not found. Available classes: {available}"
        )

    clean_attr_name = attr_name.strip()
    if not clean_attr_name:
        raise ValueError("Attribute name cannot be empty.")

    norm_vis = _normalize_visibility(visibility)
    attr = AttributeModel(name=clean_attr_name, type=type.strip(), visibility=norm_vis)
    target_class.attributes.append(attr)

    return (
        f"Added attribute '{norm_vis} {clean_attr_name}: {type}' "
        f"to class '{target_class.name}'."
    )


@mcp.tool()
def add_method(
    class_name: str,
    method_name: str,
    return_type: str = "void",
    params: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Add a method (operation) to an existing UML class.

    Args:
        class_name: Name or ID of the target class to modify.
        method_name: Name of the method/function (e.g. 'calculateTotal', 'findById').
        return_type: Method return type (e.g. 'void', 'bool', 'Order', 'List[Item]'). Default is 'void'.
        params: Optional list of parameter dicts, e.g. [{"name": "userId", "type": "int"}, {"name": "active", "type": "bool"}].

    Returns:
        Confirmation message with method signature.
    """
    target_class = state.find_class(class_name)
    if not target_class:
        available = [c.name for c in state.classes.values()]
        raise ValueError(
            f"Class '{class_name}' not found. Available classes: {available}"
        )

    clean_method_name = method_name.strip()
    if not clean_method_name:
        raise ValueError("Method name cannot be empty.")

    parsed_params: list[dict[str, Any]] = params or []
    method = MethodModel(
        name=clean_method_name,
        return_type=return_type.strip(),
        params=parsed_params,
    )
    target_class.methods.append(method)

    params_str = ", ".join(
        f"{p.get('name', 'arg')}: {p.get('type', 'any')}" for p in parsed_params
    )
    return (
        f"Added method '+{clean_method_name}({params_str}): {return_type}' "
        f"to class '{target_class.name}'."
    )


@mcp.tool()
def add_relationship(
    source_class: str,
    target_class: str,
    rel_type: str,
    src_mult: str = "",
    tgt_mult: str = "",
) -> str:
    """Create a UML relationship between two classes.

    Validates that both source and target classes exist in the current diagram state.

    Args:
        source_class: Name or ID of the source class.
        target_class: Name or ID of the target class.
        rel_type: Type of relationship. Must be one of:
                  - 'Association': General relationship between classes
                  - 'Aggregation': Shared 'has-a' relationship (part can exist independently)
                  - 'Composition': Strong 'part-of' relationship (part lifecycle tied to whole)
                  - 'Generalization': Inheritance ('is-a' relationship, source inherits target)
                  - 'Dependency': Usage dependency ('client uses supplier', source depends on target)
        src_mult: Multiplicity at source end (e.g. '1', '0..1', '*', '1..*').
        tgt_mult: Multiplicity at target end (e.g. '1', '0..1', '*', '1..*').

    Returns:
        Confirmation message with relationship details and unique relationship ID.
    """
    src = state.find_class(source_class)
    if not src:
        available = [c.name for c in state.classes.values()]
        raise ValueError(
            f"Source class '{source_class}' not found. Available classes: {available}"
        )

    tgt = state.find_class(target_class)
    if not tgt:
        available = [c.name for c in state.classes.values()]
        raise ValueError(
            f"Target class '{target_class}' not found. Available classes: {available}"
        )

    normalized_type = _normalize_relation_type(rel_type)
    rel_id = f"_rel_{uuid.uuid4().hex}"

    relation = RelationModel(
        id=rel_id,
        source_id=src.id,
        target_id=tgt.id,
        relation_type=normalized_type,
        source_multiplicity=src_mult.strip(),
        target_multiplicity=tgt_mult.strip(),
    )
    state.relations.append(relation)

    mult_info = ""
    if src_mult or tgt_mult:
        mult_info = f" [{src_mult or '1'} -> {tgt_mult or '1'}]"

    return (
        f"Created {normalized_type} relationship: '{src.name}' -> '{tgt.name}'"
        f"{mult_info} (ID: {rel_id})"
    )


@mcp.tool()
def export_xmi(filepath: str) -> str:
    """Export the current diagram state to a standard XMI 2.1 file.

    Generates a valid OMG UML 2.1 / XMI 2.1 XML document structured for direct
    import into Visual Paradigm (via Project > Import > XMI...).

    Args:
        filepath: File path to save the .xmi file (e.g. './architecture.xmi' or 'C:/models/app.xmi').

    Returns:
        Status message with the absolute path of the generated file and diagram statistics.
    """
    if not filepath.lower().endswith(".xmi"):
        filepath = f"{filepath}.xmi"

    abs_path = generate_xmi(state, filepath)
    class_count = len(state.classes)
    rel_count = len(state.relations)

    return (
        f"Successfully exported XMI 2.1 file to: {abs_path}\n"
        f"Diagram: '{state.name}' | Classes: {class_count} | Relationships: {rel_count}\n"
        f"Ready for import in Visual Paradigm via: Project > Import > XMI..."
    )


@mcp.tool()
def get_diagram_summary() -> str:
    """Inspect the current in-memory diagram state.

    Useful for checking existing classes, methods, attributes, and relationships
    before making further architectural decisions.

    Returns:
        Detailed summary of classes and relationships currently in the diagram.
    """
    if not state.classes:
        return f"Diagram '{state.name}' is currently empty. Use add_class() to begin."

    lines = [f"=== Diagram: {state.name} ===", f"Classes ({len(state.classes)}):"]
    for cls in state.classes.values():
        lines.append(f"  Class: {cls.name} (id: {cls.id})")
        if cls.attributes:
            lines.append("    Attributes:")
            for a in cls.attributes:
                lines.append(f"      - {a.visibility} {a.name}: {a.type}")
        if cls.methods:
            lines.append("    Methods:")
            for m in cls.methods:
                p_str = ", ".join(f"{p.get('name')}: {p.get('type')}" for p in m.params)
                lines.append(f"      - +{m.name}({p_str}): {m.return_type}")

    if state.relations:
        lines.append(f"\nRelationships ({len(state.relations)}):")
        for r in state.relations:
            src = state.find_class(r.source_id)
            tgt = state.find_class(r.target_id)
            src_name = src.name if src else r.source_id
            tgt_name = tgt.name if tgt else r.target_id
            mult = ""
            if r.source_multiplicity or r.target_multiplicity:
                mult = f" [{r.source_multiplicity}..{r.target_multiplicity}]"
            lines.append(f"  - {src_name} --({r.relation_type}{mult})--> {tgt_name}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Run the MCP server over standard I/O (stdio)
    try:
        mcp.run(transport="stdio")
    except TypeError:
        # Fallback for SDK variants where run defaults to stdio without transport argument
        mcp.run()
