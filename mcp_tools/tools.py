"""MCP Tools for UML and ERD modeling with Rules Engine feedback and XMI export."""

from typing import Any, Optional
from core.models import (
    ActorModel,
    ActorNode,
    AttributeModel,
    ClassElementType,
    ClassModel,
    ClassNode,
    ClassRelation,
    ClassRelationType,
    ColumnModel,
    EntityModel,
    EntityNode,
    ERRelation,
    ERRelationType,
    MethodModel,
    MethodParam,
    PackageModel,
    PackageNode,
    ParamDirectionType,
    StateModel,
    StateNode,
    StateType,
    TransitionModel,
    UCRelation,
    UCRelationType,
    UseCaseModel,
    UseCaseNode,
    VisibilityType,
)
try:
    from core.state import state
    from exporters.xmi_builder import XMIBuilder
    from core.doc_reader import RequirementsDocReader
except ImportError:
    from ..core.state import state
    from ..exporters.xmi_builder import XMIBuilder
    from ..core.doc_reader import RequirementsDocReader



# ---------------------------------------------------------
# Normalizers & Type Checkers
# ---------------------------------------------------------

def _normalize_visibility(vis: str) -> VisibilityType:
    clean = (vis or "public").strip().lower()
    mapping: dict[str, VisibilityType] = {
        "+": "public",
        "-": "private",
        "#": "protected",
        "public": "public",
        "private": "private",
        "protected": "protected",
    }
    return mapping.get(clean, "public")


def _normalize_class_rel_type(rel_type: str) -> ClassRelationType:
    clean = (rel_type or "").strip().capitalize()
    allowed: dict[str, ClassRelationType] = {
        "Association": "Association",
        "Generalization": "Generalization",
        "Composition": "Composition",
        "Aggregation": "Aggregation",
        "Dependency": "Dependency",
        "Realization": "Realization",
    }
    if clean not in allowed:
        raise ValueError(
            f"Invalid class relation type '{rel_type}'. Allowed types: {', '.join(allowed.keys())}"
        )
    return allowed[clean]


def _normalize_er_rel_type(rel_type: str) -> ERRelationType:
    clean = (rel_type or "").strip().upper()
    allowed: dict[str, ERRelationType] = {
        "1:1": "1:1",
        "1:N": "1:N",
        "N:1": "N:1",
        "M:1": "N:1",
        "M:N": "M:N",
        "1..1": "1:1",
        "1..N": "1:N",
        "N..1": "N:1",
        "M..1": "N:1",
        "M..N": "M:N",
        "N:M": "M:N",
    }
    if clean not in allowed:
        raise ValueError(
            f"Invalid ER relation type '{rel_type}'. Allowed types: 1:1, 1:N, N:1, M:N"
        )
    return allowed[clean]


def _normalize_uc_rel_type(rel_type: str) -> UCRelationType:
    clean = (rel_type or "").strip().capitalize()
    allowed: dict[str, UCRelationType] = {
        "Association": "Association",
        "Include": "Include",
        "Extend": "Extend",
    }
    if clean not in allowed:
        raise ValueError(
            f"Invalid Use Case relation type '{rel_type}'. Allowed types: Association, Include, Extend"
        )
    return allowed[clean]


def _normalize_state_type(state_type: str) -> StateType:
    clean = (state_type or "State").strip().capitalize()
    allowed: dict[str, StateType] = {
        "Initial": "Initial",
        "State": "State",
        "Final": "Final",
    }
    if clean not in allowed:
        raise ValueError(
            f"Invalid State type '{state_type}'. Allowed types: Initial, State, Final"
        )
    return allowed[clean]


# ---------------------------------------------------------
# Tool Functions
# ---------------------------------------------------------

def init_project(name: str = "ProjectModel") -> str:
    """Initialize a new architecture project and reset the in-memory state.

    Call this tool at the beginning of an architectural design session or
    when starting a new model from scratch. It clears all previously stored
    classes, entities, use cases, and states.

    Args:
        name: Name of the project/model (default: 'ProjectModel').

    Returns:
        Status message confirming project initialization.
    """
    try:
        clean_name = name.strip() or "ProjectModel"
        state.clear(name=clean_name)
        return f"Project '{clean_name}' successfully initialized. In-memory state cleared."
    except Exception as e:
        return f"ERROR: Failed to initialize project: {str(e)}"


# --- UML Package & Class Diagram Tools ---

def add_package(name: str, parent_package: Optional[str] = None) -> str:
    """Create a UML Package (namespace container) to group classes and subpackages.

    Packages provide modular domain organization. Visual Paradigm renders them as container
    boxes with tabs, dynamically sized so all child elements fit neatly inside without overflowing.

    Args:
        name: Name of the package (e.g., 'Domain', 'Billing', 'Controllers').
        parent_package: Optional name or ID of a parent package for hierarchical nesting.

    Returns:
        Confirmation message with Package ID and nesting hierarchy.
    """
    try:
        clean_name = name.strip()
        if not clean_name:
            return "ERROR: Package name cannot be empty."

        clean_parent = parent_package.strip() if parent_package else None
        pkg = state.create_package(clean_name, clean_parent)
        parent_info = f" nested under '{clean_parent}'" if clean_parent else ""
        return f"Created UML Package '{pkg.name}'{parent_info} (ID: {pkg.id})."
    except Exception as e:
        return f"ERROR: Failed to create package: {str(e)}"


def move_class_to_package(class_name: str, package_name: str) -> str:
    """Assign or move an existing UML class into a specified Package container.

    Args:
        class_name: Name or ID of the class to move.
        package_name: Name or ID of the destination package.

    Returns:
        Confirmation message or error feedback.
    """
    try:
        clean_cls = class_name.strip()
        clean_pkg = package_name.strip()
        cls_obj, pkg_obj = state.move_class_to_package(clean_cls, clean_pkg)
        return f"Moved Class '{cls_obj.name}' into Package '{pkg_obj.name}'."
    except Exception as e:
        return f"ERROR: Failed to move class to package: {str(e)}"


def add_class(
    name: str,
    is_abstract: bool = False,
    element_type: str = "Class",
    package: Optional[str] = None,
    description: str = "",
) -> str:
    """Create a new UML Class or Interface classifier in the model.

    Args:
        name: Name of the class/interface (e.g., 'OrderService', 'Customer', 'IRepository').
        is_abstract: Set True if this class is abstract (cannot be directly instantiated).
        element_type: 'Class' or 'Interface'.
        package: Optional name of the package container to place this class into.
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message with class ID or error description.
    """
    try:
        clean_name = name.strip()
        if not clean_name:
            return "ERROR: Class name cannot be empty."

        existing = state.find_class(clean_name)
        if existing:
            if description:
                existing.description = description
            return f"Class '{clean_name}' already exists with ID: {existing.id}."

        clean_elem_type: ClassElementType = "Interface" if element_type.strip().capitalize() == "Interface" else "Class"
        new_class = ClassModel(
            name=clean_name,
            is_abstract=bool(is_abstract),
            element_type=clean_elem_type,
            description=description,
        )
        state.add_node(new_class)

        pkg_msg = ""
        if package and package.strip():
            cls_obj, pkg_obj = state.move_class_to_package(clean_name, package.strip())
            pkg_msg = f" inside Package '{pkg_obj.name}'"

        abstract_str = "Abstract " if is_abstract else ""
        return f"Created UML {abstract_str}{clean_elem_type} '{clean_name}'{pkg_msg} (ID: {new_class.id})."
    except Exception as e:
        return f"ERROR: Failed to create class: {str(e)}"


def add_class_attribute(
    class_name: str,
    name: str,
    type: str = "string",
    visibility: str = "public",
    multiplicity: str = "",
    description: str = "",
) -> str:
    """Add an attribute (field/property) to an existing UML class.

    Args:
        class_name: Name or ID of the target UML class.
        name: Name of the attribute (e.g., 'id', 'email', 'createdAt').
        type: Data type (e.g., 'string', 'int', 'UUID', 'UserStatus').
        visibility: Access level ('public', 'private', or 'protected').
        multiplicity: Multiplicity constraint (e.g., '1', '0..1', '*', '1..*').
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message or error feedback.
    """
    try:
        cls = state.find_class(class_name)
        if not cls:
            available = [c.name for c in state.classes.values()]
            return f"ERROR: Class '{class_name}' not found. Available classes: {available}"

        attr_name = name.strip()
        if not attr_name:
            return "ERROR: Attribute name cannot be empty."

        norm_vis = _normalize_visibility(visibility)
        if cls.element_type == "Interface" and norm_vis == "private":
            return f"ERROR: UML Rule Violation: Interface '{cls.name}' cannot have private attributes."

        attr = AttributeModel(
            name=attr_name,
            type=type.strip(),
            visibility=norm_vis,
            multiplicity=multiplicity.strip(),
            description=description,
        )
        cls.attributes.append(attr)
        mult_str = f" [{multiplicity}]" if multiplicity else ""
        return f"Added attribute '{norm_vis} {attr_name}: {type}'{mult_str} to {cls.element_type} '{cls.name}'."
    except Exception as e:
        return f"ERROR: Failed to add attribute: {str(e)}"


def add_class_method(
    class_name: str,
    name: str,
    return_type: str = "void",
    params: Optional[list[dict[str, Any]]] = None,
    description: str = "",
) -> str:
    """Add a method (operation) to an existing UML class.

    Args:
        class_name: Name or ID of the target UML class.
        name: Name of the method (e.g., 'authenticate', 'calculateTotal').
        return_type: Return type (e.g., 'void', 'bool', 'Order', 'List[Item]').
        params: Optional parameter dicts, e.g. [{"name": "password", "type": "string", "direction": "in"}].
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message with method signature or error feedback.
    """
    try:
        cls = state.find_class(class_name)
        if not cls:
            available = [c.name for c in state.classes.values()]
            return f"ERROR: Class '{class_name}' not found. Available classes: {available}"

        method_name = name.strip()
        if not method_name:
            return "ERROR: Method name cannot be empty."

        param_models: list[MethodParam] = []
        if params:
            for p in params:
                p_name = p.get("name", "arg").strip()
                p_type = p.get("type", "string").strip()
                p_dir_raw = p.get("direction", "in").strip().lower()
                p_dir: ParamDirectionType = "in"
                if p_dir_raw in ("in", "out", "return"):
                    p_dir = p_dir_raw  # type: ignore
                param_models.append(MethodParam(name=p_name, type=p_type, direction=p_dir))

        method = MethodModel(
            name=method_name,
            return_type=return_type.strip(),
            params=param_models,
            description=description,
        )
        cls.methods.append(method)

        params_repr = ", ".join(f"{p.name}: {p.type}" for p in param_models)
        return f"Added method '+{method_name}({params_repr}): {return_type}' to {cls.element_type} '{cls.name}'."
    except Exception as e:
        return f"ERROR: Failed to add method: {str(e)}"


def add_class_relation(
    src_name: str,
    tgt_name: str,
    type: str,
    src_mult: str = "",
    tgt_mult: str = "",
) -> str:
    """Create a UML relationship between two classes with Rules Engine validation.

    Supported types:
    - 'Association': General relationship between classes
    - 'Generalization': Inheritance ('is-a', source inherits target)
    - 'Composition': Strong whole-part link (part lifecycle tied to whole)
    - 'Aggregation': Shared whole-part link
    - 'Dependency': Usage dependency (source client depends on target supplier)
    - 'Realization': Interface implementation (source realizes target interface)

    Args:
        src_name: Name or ID of the source class.
        tgt_name: Name or ID of the target class.
        type: Relationship type (Association, Generalization, Composition, Aggregation, Dependency, Realization).
        src_mult: Optional multiplicity at source end (e.g. '0..1', '1', '*').
        tgt_mult: Optional multiplicity at target end (e.g. '0..1', '1', '*').

    Returns:
        Confirmation message or error explanation.
    """
    try:
        src = state.find_class(src_name)
        if not src:
            available = [c.name for c in state.classes.values()]
            return f"ERROR: Source class '{src_name}' not found. Available: {available}"

        tgt = state.find_class(tgt_name)
        if not tgt:
            available = [c.name for c in state.classes.values()]
            return f"ERROR: Target class '{tgt_name}' not found. Available: {available}"

        norm_type = _normalize_class_rel_type(type)

        # Rules Engine: Check for cyclic inheritance
        if norm_type == "Generalization":
            if state.would_cause_inheritance_cycle(src.id, tgt.id):
                return (
                    f"ERROR: UML Rule Violation: Cyclic inheritance detected! "
                    f"Class '{src.name}' cannot inherit from '{tgt.name}' because an inheritance loop would be formed."
                )

        rel = ClassRelation(
            source_id=src.id,
            target_id=tgt.id,
            type=norm_type,
            source_multiplicity=src_mult.strip(),
            target_multiplicity=tgt_mult.strip(),
        )
        state.add_relation(rel)

        mult_info = f" [{src_mult}..{tgt_mult}]" if (src_mult or tgt_mult) else ""
        return f"Created Class relation [{norm_type}]: '{src.name}' -> '{tgt.name}'{mult_info} (ID: {rel.id})."
    except Exception as e:
        return f"ERROR: Failed to create class relation: {str(e)}"


# --- Semantic Relationship Decision Engine ---

def _resolve_semantic_relation(src_obj: Any, tgt_obj: Any, intent: str) -> dict[str, Any]:
    """Helper to deduce OMG UML relationship type, visual notation, and multiplicities based on semantics."""
    intent_lower = intent.lower()

    # Case A: UML Class Diagram
    if isinstance(src_obj, ClassNode) and isinstance(tgt_obj, ClassNode):
        # 1. Realization (implements interface)
        if (
            tgt_obj.element_type == "Interface"
            or any(w in intent_lower for w in ["implement", "realiz", "contract"])
        ):
            return {
                "diagram": "Class",
                "type": "Realization",
                "visual": "Dashed line with hollow closed triangular arrow pointing to interface: [Class] - - - |> [Interface]",
                "src_mult": "",
                "tgt_mult": "",
                "rationale": f"Class '{src_obj.name}' implements interface contract '{tgt_obj.name}'. In OMG UML, realization is represented by a dashed line with a hollow closed triangle pointing to the interface.",
                "action": "ClassRelation",
            }

        # 2. Generalization (is a / inheritance)
        if any(w in intent_lower for w in ["is a", "is-a", "inherits", "extends", "subclass", "derived", "child of", "generalization"]):
            return {
                "diagram": "Class",
                "type": "Generalization",
                "visual": "Solid line with hollow closed triangular arrow pointing to parent: [Child] -----|> [Parent]",
                "src_mult": "",
                "tgt_mult": "",
                "rationale": f"Class '{src_obj.name}' is a child/specialization of '{tgt_obj.name}' (IS-A relationship). Inherits attributes and operations, sharing polymorphic identity.",
                "action": "ClassRelation",
            }

        # 3. Composition (exclusive whole-part, strictly tied lifecycle)
        if any(w in intent_lower for w in [
            "composed of", "owns exclusively", "owns", "exclusive", "part of",
            "cascade delete", "destroy together", "cannot exist without",
            "lifecycle tied", "composition", "strictly contains"
        ]):
            return {
                "diagram": "Class",
                "type": "Composition",
                "visual": "Solid line with filled diamond <#> at Owner: [Owner] <#>----- [Part]",
                "src_mult": "1",
                "tgt_mult": "1..*",
                "rationale": f"Strong whole-part ownership. '{src_obj.name}' exclusively owns '{tgt_obj.name}'. If '{src_obj.name}' is destroyed, '{tgt_obj.name}' ceases to exist.",
                "action": "ClassRelation",
            }

        # 4. Aggregation (shared whole-part, independent lifecycles)
        if any(w in intent_lower for w in [
            "aggregat", "has a", "has-a", "shared", "collection of",
            "can exist without", "independent", "loose collection", "aggregation", "member of"
        ]):
            return {
                "diagram": "Class",
                "type": "Aggregation",
                "visual": "Solid line with hollow diamond <> at Whole: [Whole] <>----- [Part]",
                "src_mult": "1",
                "tgt_mult": "*",
                "rationale": f"Shared whole-part aggregation. '{src_obj.name}' aggregates '{tgt_obj.name}', but parts can exist independently if '{src_obj.name}' is destroyed.",
                "action": "ClassRelation",
            }

        # 5. Dependency (transient usage / parameter / invocation)
        if any(w in intent_lower for w in ["uses", "depends", "parameter", "temporary", "invokes", "calls", "transient", "dependency"]):
            return {
                "diagram": "Class",
                "type": "Dependency",
                "visual": "Dashed line with open arrowhead pointing to supplier: [Client] - - - > [Supplier]",
                "src_mult": "",
                "tgt_mult": "",
                "rationale": f"Usage dependency. '{src_obj.name}' calls or uses '{tgt_obj.name}' as a parameter or transient helper without holding a persistent member field.",
                "action": "ClassRelation",
            }

        # 6. Default: Association (persistent structural link)
        return {
            "diagram": "Class",
            "type": "Association",
            "visual": "Solid line: [Source] ---------- [Target]",
            "src_mult": "0..1",
            "tgt_mult": "*",
            "rationale": f"Structural association. '{src_obj.name}' holds a persistent reference to '{tgt_obj.name}'.",
            "action": "ClassRelation",
        }

    # Case B: Use Case Diagram
    if isinstance(src_obj, (ActorNode, UseCaseNode)) and isinstance(tgt_obj, (ActorNode, UseCaseNode)):
        if isinstance(src_obj, ActorNode) or isinstance(tgt_obj, ActorNode):
            return {
                "diagram": "UseCase",
                "type": "Association",
                "visual": "Solid line without arrowheads: [Actor] ---------- (Use Case)",
                "src_mult": "",
                "tgt_mult": "",
                "rationale": f"Actor '{src_obj.name}' participates in or initiates Use Case '{tgt_obj.name}'.",
                "action": "UCRelation",
            }

        if any(w in intent_lower for w in ["mandatory", "always", "include", "includes", "required", "sub-routine", "step"]):
            return {
                "diagram": "UseCase",
                "type": "Include",
                "visual": "Dashed arrow with <<include>>: (Base) - - <<include>> - -> (Included)",
                "src_mult": "",
                "tgt_mult": "",
                "rationale": f"Use Case '{src_obj.name}' unconditionally includes the execution of '{tgt_obj.name}'.",
                "action": "UCRelation",
            }
        elif any(w in intent_lower for w in ["optional", "conditional", "extend", "extends", "exception", "hook", "special case"]):
            return {
                "diagram": "UseCase",
                "type": "Extend",
                "visual": "Dashed arrow with <<extend>>: (Extension) - - <<extend>> - -> (Base)",
                "src_mult": "",
                "tgt_mult": "",
                "rationale": f"Extension Use Case '{src_obj.name}' conditionally augments Base Use Case '{tgt_obj.name}'.",
                "action": "UCRelation",
            }
        else:
            return {
                "diagram": "UseCase",
                "type": "Include",
                "visual": "Dashed arrow with <<include>>: (Base) - - <<include>> - -> (Included)",
                "src_mult": "",
                "tgt_mult": "",
                "rationale": f"Sub-routine execution from '{src_obj.name}' to '{tgt_obj.name}'.",
                "action": "UCRelation",
            }

    # Case C: ER Diagram
    if isinstance(src_obj, EntityNode) and isinstance(tgt_obj, EntityNode):
        if any(w in intent_lower for w in ["m:n", "many-to-many", "m..n", "junction", "cross table", "tags", "roles"]):
            return {
                "diagram": "ERD",
                "type": "M:N",
                "visual": "Crow's foot many-to-many relationship: [Entity1] }|----------|{ [Entity2]",
                "src_mult": "M",
                "tgt_mult": "N",
                "rationale": f"Many-to-Many relationship between table '{src_obj.name}' and table '{tgt_obj.name}'.",
                "action": "ERRelation",
            }
        elif any(w in intent_lower for w in ["1:1", "one-to-one", "1..1", "unique profile"]):
            return {
                "diagram": "ERD",
                "type": "1:1",
                "visual": "One-to-one relationship: [Entity1] ||----------|| [Entity2]",
                "src_mult": "1",
                "tgt_mult": "1",
                "rationale": f"One-to-One relationship between table '{src_obj.name}' and table '{tgt_obj.name}'.",
                "action": "ERRelation",
            }
        else:
            return {
                "diagram": "ERD",
                "type": "1:N",
                "visual": "One-to-many relationship: [Entity1] ||----------<{ [Entity2]",
                "src_mult": "1",
                "tgt_mult": "N",
                "rationale": f"One-to-Many relationship from parent table '{src_obj.name}' to child table '{tgt_obj.name}'. Target requires FK.",
                "action": "ERRelation",
            }

    # Case D: State Machine Diagram
    if isinstance(src_obj, StateNode) and isinstance(tgt_obj, StateNode):
        return {
            "diagram": "StateMachine",
            "type": "Transition",
            "visual": "Directed arrow: [State1] ----------> [State2]",
            "src_mult": "",
            "tgt_mult": "",
            "rationale": f"State transition from '{src_obj.name}' to '{tgt_obj.name}'.",
            "action": "Transition",
        }

    raise ValueError(f"Cannot relate elements of different or unknown diagram types: '{getattr(src_obj, 'name', src_obj)}' and '{getattr(tgt_obj, 'name', tgt_obj)}'")


def suggest_relation(source: str, target: str, description: str) -> str:
    """Analyze the semantic intent between two elements and recommend the exact OMG UML/ERD relation.

    Explains OMG arrowhead notation, lifecycle semantics, recommended multiplicities,
    and provides the exact tool command.

    Args:
        source: Name or ID of the source element.
        target: Name or ID of the target element.
        description: Plain text describing how they relate (e.g. 'Order exclusively owns OrderItems',
                     'UserRepository implements IRepository', 'Customer inherits from User').

    Returns:
        Structured recommendation with relation type, OMG visual notation, and execution command.
    """
    try:
        src = state.find_node_by_name(source) or state.find_node_by_id(source)
        if not src:
            return f"ERROR: Source element '{source}' not found."

        tgt = state.find_node_by_name(target) or state.find_node_by_id(target)
        if not tgt:
            return f"ERROR: Target element '{target}' not found."

        rec = _resolve_semantic_relation(src, tgt, description)

        lines = [
            f"=== OMG Architecture Relation Recommendation ===",
            f"Source: {src.name}  -->  Target: {tgt.name}",
            f"Diagram Domain: {rec['diagram']}",
            f"Recommended Relation Type: {rec['type']}",
            f"OMG Visual Notation: {rec['visual']}",
            f"Semantic Rationale: {rec['rationale']}",
        ]
        if rec['src_mult'] or rec['tgt_mult']:
            lines.append(f"Recommended Multiplicities: Source [{rec['src_mult']}], Target [{rec['tgt_mult']}]")

        lines.append(f"\nTo apply this relationship, call:")
        if rec['diagram'] == "Class":
            lines.append(f"  smart_add_relation('{src.name}', '{tgt.name}', '{rec['type']}', mult_source='{rec['src_mult']}', mult_target='{rec['tgt_mult']}')")
        elif rec['diagram'] == "UseCase":
            lines.append(f"  add_uc_relation('{src.name}', '{tgt.name}', '{rec['type']}')")
        elif rec['diagram'] == "ERD":
            lines.append(f"  add_er_relation('{src.name}', '{tgt.name}', '{rec['type']}')")
        elif rec['diagram'] == "StateMachine":
            lines.append(f"  add_state_transition('{src.name}', '{tgt.name}', trigger='{description}')")

        return "\n".join(lines)
    except Exception as e:
        return f"ERROR: Failed to analyze relation: {str(e)}"


def smart_add_relation(
    source: str,
    target: str,
    intent: str,
    mult_source: str = "",
    mult_target: str = "",
) -> str:
    """Intelligently deduce and create the appropriate architectural relationship between two nodes.

    Uses the Semantic Relationship Engine to determine the exact OMG UML/ERD relation
    type, validates architectural rules, and updates the model.

    Args:
        source: Name or ID of the source element.
        target: Name or ID of the target element.
        intent: Description of intent or explicit relation type (e.g. 'owns exclusively', 'implements',
                'is a', 'temporary helper', '1:N', 'Include', 'Composition').
        mult_source: Optional source multiplicity override (e.g., '1', '0..1', '*').
        mult_target: Optional target multiplicity override (e.g., '1', '1..*', '*').

    Returns:
        Confirmation message with chosen relation type, OMG visual notation, and relation ID.
    """
    try:
        src = state.find_node_by_name(source) or state.find_node_by_id(source)
        if not src:
            return f"ERROR: Source element '{source}' not found."

        tgt = state.find_node_by_name(target) or state.find_node_by_id(target)
        if not tgt:
            return f"ERROR: Target element '{target}' not found."

        rec = _resolve_semantic_relation(src, tgt, intent)
        rel_type = rec["type"]
        s_mult = mult_source.strip() if mult_source else rec["src_mult"]
        t_mult = mult_target.strip() if mult_target else rec["tgt_mult"]

        if rec["diagram"] == "Class":
            norm_type = _normalize_class_rel_type(rel_type)
            if norm_type == "Generalization":
                if state.would_cause_inheritance_cycle(src.id, tgt.id):
                    return (
                        f"ERROR: UML Rule Violation: Cyclic inheritance detected! "
                        f"Class '{src.name}' cannot inherit from '{tgt.name}' because an inheritance loop would be formed."
                    )
            rel = ClassRelation(
                source_id=src.id,
                target_id=tgt.id,
                type=norm_type,
                source_multiplicity=s_mult,
                target_multiplicity=t_mult,
            )
            state.add_relation(rel)
            mult_str = f" [{s_mult}..{t_mult}]" if (s_mult or t_mult) else ""
            return (
                f"Smart Relation Applied [{norm_type}]: '{src.name}' -> '{tgt.name}'{mult_str} (ID: {rel.id})\n"
                f"OMG Visual: {rec['visual']}\n"
                f"Semantics: {rec['rationale']}"
            )

        elif rec["diagram"] == "UseCase":
            norm_type = _normalize_uc_rel_type(rel_type)
            if norm_type in ("Include", "Extend"):
                if not isinstance(src, UseCaseNode):
                    return f"ERROR: UML 2.5 Rule Violation: '{norm_type}' source must be a Use Case."
                if not isinstance(tgt, UseCaseNode):
                    return f"ERROR: UML 2.5 Rule Violation: '{norm_type}' target must be a Use Case."
            rel = UCRelation(
                source_id=src.id,
                target_id=tgt.id,
                type=norm_type,
            )
            state.add_relation(rel)
            return (
                f"Smart Relation Applied [{norm_type}]: '{src.name}' -> '{tgt.name}' (ID: {rel.id})\n"
                f"OMG Visual: {rec['visual']}\n"
                f"Semantics: {rec['rationale']}"
            )

        elif rec["diagram"] == "ERD":
            norm_type = _normalize_er_rel_type(rel_type)
            if norm_type == "1:N":
                has_fk = any(c.is_foreign_key for c in tgt.columns)
                if not has_fk:
                    return (
                        f"ERROR: ERD Rule Violation: Relation 1:N from '{src.name}' to '{tgt.name}' requires target "
                        f"entity '{tgt.name}' to have at least one column marked as Foreign Key (is_fk=True)."
                    )
            rel = ERRelation(
                source_id=src.id,
                target_id=tgt.id,
                type=norm_type,
            )
            state.add_relation(rel)
            return (
                f"Smart Relation Applied [{norm_type}]: '{src.name}' -> '{tgt.name}' (ID: {rel.id})\n"
                f"Visual: {rec['visual']}\n"
                f"Semantics: {rec['rationale']}"
            )

        elif rec["diagram"] == "StateMachine":
            tr = TransitionModel(
                source_id=src.id,
                target_id=tgt.id,
                trigger_event=intent,
            )
            state.add_relation(tr)
            return (
                f"Smart Transition Applied: '{src.name}' -> '{tgt.name}' (ID: {tr.id})\n"
                f"Trigger: {intent}"
            )

        return f"ERROR: Unknown diagram category for smart relation."
    except Exception as e:
        return f"ERROR: Failed to add smart relation: {str(e)}"


# --- ER Diagram Tools ---

def add_er_entity(name: str, description: str = "") -> str:
    """Create an ER Entity (Database Table) in the diagram.

    Args:
        name: Name of the entity/table (e.g. 'users', 'orders', 'order_items').
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message with Entity ID or error.
    """
    try:
        clean_name = name.strip()
        if not clean_name:
            return "ERROR: Entity name cannot be empty."

        existing = state.find_entity(clean_name)
        if existing:
            if description:
                existing.description = description
            return f"Entity '{clean_name}' already exists with ID: {existing.id}."

        new_entity = EntityModel(name=clean_name, description=description)
        state.add_node(new_entity)
        return f"Created ER Entity '{clean_name}' (ID: {new_entity.id})."
    except Exception as e:
        return f"ERROR: Failed to create entity: {str(e)}"


def add_er_column(
    entity_name: str,
    name: str,
    type: str = "VARCHAR",
    length: Optional[int] = None,
    is_nullable: bool = True,
    is_pk: bool = False,
    is_fk: bool = False,
    is_unique: bool = False,
    description: str = "",
) -> str:
    """Add a column/field to an existing ER Entity.

    Args:
        entity_name: Name or ID of the target ER Entity.
        name: Column name (e.g. 'user_id', 'email', 'price').
        type: Column data type. Standard VP ERD types: 'bigint', 'binary', 'bit', 'blob', 'char', 'clob', 'date', 'decimal', 'double', 'float', 'integer', 'numeric', 'real', 'smallint', 'time', 'timestamp', 'tinyint', 'varbinary', 'varchar'. Also supports 'int8', 'int4', 'int2', 'bool', 'uuid'.
        length: Optional column length / precision (e.g. 255).
        is_nullable: Whether column allows NULL (automatically False if is_pk is True).
        is_pk: True if column is part of the Primary Key.
        is_fk: True if column is a Foreign Key.
        is_unique: True if column has a Unique constraint.
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message with column flags or error.
    """
    try:
        ent = state.find_entity(entity_name)
        if not ent:
            available = [e.name for e in state.entities.values()]
            return f"ERROR: Entity '{entity_name}' not found. Available: {available}"

        col_name = name.strip()
        if not col_name:
            return "ERROR: Column name cannot be empty."

        eff_is_pk = bool(is_pk)
        eff_is_fk = bool(is_fk)

        # Rule 1: Enforce exactly one Primary Key per entity. Prevent duplicate PKs (e.g. ID1 + ID2)
        existing_pks = [c for c in ent.columns if c.is_pk]
        if eff_is_pk and existing_pks:
            return (
                f"ERROR: ERD Rule Violation: Entity '{ent.name}' already has a Primary Key ('{existing_pks[0].name}'). "
                f"An entity can only have ONE Primary Key column. Cannot add '{col_name}' as a second PK."
            )

        # Rule 2: Auto-detect Foreign Key by convention if column ends with '_id' or 'id' (and is not PK)
        if not eff_is_pk and (col_name.lower().endswith("_id") or (col_name.lower().endswith("id") and len(col_name) > 2)) and not eff_is_fk:
            eff_is_fk = True

        # Rule 3: Suppress redundant UNIQUE constraint on PK (PK is inherently unique by standard)
        eff_is_unique = False if eff_is_pk else bool(is_unique)
        eff_is_nullable = False if eff_is_pk else bool(is_nullable)

        col = ColumnModel(
            name=col_name,
            type=type.strip(),
            length=length,
            is_nullable=eff_is_nullable,
            is_primary_key=eff_is_pk,
            is_foreign_key=eff_is_fk,
            is_unique=eff_is_unique,
            description=description,
        )
        ent.columns.append(col)

        flags = []
        if col.is_primary_key:
            flags.append("PK")
        if col.is_foreign_key:
            flags.append("FK")
        if col.is_unique and not col.is_primary_key:
            flags.append("UNIQUE")
        if not col.is_nullable:
            flags.append("NOT NULL")
        flags_str = f" [{', '.join(flags)}]" if flags else ""

        type_repr = f"{col.type}({col.length})" if col.length else col.type
        return f"Added column '{col_name}: {type_repr}'{flags_str} to Entity '{ent.name}'."
    except Exception as e:
        return f"ERROR: Failed to add column: {str(e)}"


def add_er_relation(src_name: str, tgt_name: str, type: str) -> str:
    """Create an ER cardinality relationship between two entities.

    Enforces ERD integrity rules:
    - For 1:N relations, the child/target entity MUST have at least one Foreign Key column defined.

    Args:
        src_name: Name or ID of the source entity (Parent in 1:N).
        tgt_name: Name or ID of the target entity (Child in 1:N).
        type: Cardinality ('1:1', '1:N', 'M:N').

    Returns:
        Confirmation message or error feedback.
    """
    try:
        src = state.find_entity(src_name)
        if not src:
            available = [e.name for e in state.entities.values()]
            return f"ERROR: Source entity '{src_name}' not found. Available: {available}"

        tgt = state.find_entity(tgt_name)
        if not tgt:
            available = [e.name for e in state.entities.values()]
            return f"ERROR: Target entity '{tgt_name}' not found. Available: {available}"

        norm_type = _normalize_er_rel_type(type)

        # Rules Engine: 1:N requires FK in target entity; N:1 requires FK in source entity
        if norm_type == "1:N":
            if not state.validate_er_1_to_n(tgt.id):
                return (
                    f"ERROR: ERD Rule Violation: Relation 1:N from '{src.name}' to '{tgt.name}' "
                    f"requires target entity '{tgt.name}' to have at least one column marked as Foreign Key (is_fk=True). "
                    f"Please add a foreign key column to '{tgt.name}' first using add_er_column()."
                )
        elif norm_type == "N:1":
            if not state.validate_er_1_to_n(src.id):
                return (
                    f"ERROR: ERD Rule Violation: Relation N:1 from '{src.name}' to '{tgt.name}' "
                    f"requires source entity '{src.name}' to have at least one column marked as Foreign Key (is_fk=True). "
                    f"Please add a foreign key column to '{src.name}' first using add_er_column()."
                )

        rel = ERRelation(source_id=src.id, target_id=tgt.id, type=norm_type)
        state.add_relation(rel)
        return f"Created ER relation [{norm_type}]: '{src.name}' -> '{tgt.name}' (ID: {rel.id})."
    except Exception as e:
        return f"ERROR: Failed to create ER relation: {str(e)}"


# --- Use Case Diagram Tools ---

def add_actor(name: str, description: str = "") -> str:
    """Create a UML Actor in the Use Case diagram.

    Args:
        name: Name of the actor (e.g. 'Customer', 'Admin', 'PaymentGateway').
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message with Actor ID or error.
    """
    try:
        clean_name = name.strip()
        if not clean_name:
            return "ERROR: Actor name cannot be empty."

        existing = state.find_actor(clean_name)
        if existing:
            if description:
                existing.description = description
            return f"Actor '{clean_name}' already exists with ID: {existing.id}."

        actor = ActorModel(name=clean_name, description=description)
        state.add_node(actor)
        return f"Created Actor '{clean_name}' (ID: {actor.id})."
    except Exception as e:
        return f"ERROR: Failed to create actor: {str(e)}"


def add_use_case(name: str, description: str = "") -> str:
    """Create a UML Use Case in the diagram.

    Args:
        name: Name of the use case (e.g. 'Login', 'PlaceOrder', 'GenerateInvoice').
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message with Use Case ID or error.
    """
    try:
        clean_name = name.strip()
        if not clean_name:
            return "ERROR: Use Case name cannot be empty."

        existing = state.find_use_case(clean_name)
        if existing:
            if description:
                existing.description = description
            return f"Use Case '{clean_name}' already exists with ID: {existing.id}."

        uc = UseCaseModel(name=clean_name, description=description)
        state.add_node(uc)
        return f"Created Use Case '{clean_name}' (ID: {uc.id})."
    except Exception as e:
        return f"ERROR: Failed to create use case: {str(e)}"


def add_uc_relation(src_name: str, tgt_name: str, type: str) -> str:
    """Create a relationship in the Use Case diagram with UML 2.5 integrity checks.

    Rules:
    - 'Include' and 'Extend' are ONLY allowed between two Use Cases (not Actors).
    - 'Association' is used to connect an Actor with a Use Case.

    Args:
        src_name: Name or ID of source (Actor or UseCase).
        tgt_name: Name or ID of target (Actor or UseCase).
        type: Relation type ('Association', 'Include', 'Extend').

    Returns:
        Confirmation message or error feedback.
    """
    try:
        norm_type = _normalize_uc_rel_type(type)

        if norm_type in ("Include", "Extend"):
            src_uc = state.find_use_case(src_name)
            if not src_uc:
                return (
                    f"ERROR: UML 2.5 Rule Violation: '{norm_type}' relationship source must be a Use Case. "
                    f"'{src_name}' was not found in Use Cases."
                )
            tgt_uc = state.find_use_case(tgt_name)
            if not tgt_uc:
                return (
                    f"ERROR: UML 2.5 Rule Violation: '{norm_type}' relationship target must be a Use Case. "
                    f"'{tgt_name}' was not found in Use Cases."
                )
            if src_uc.id == tgt_uc.id:
                return f"ERROR: UML 2.5 Rule Violation: Use Case '{src_uc.name}' cannot '{norm_type}' itself."

            rel = UCRelation(source_id=src_uc.id, target_id=tgt_uc.id, type=norm_type)
            state.add_relation(rel)
            return f"Created Use Case relation [{norm_type}]: '{src_uc.name}' -> '{tgt_uc.name}' (ID: {rel.id})."
        else:
            src_node = state.find_uc_node(src_name)
            if not src_node:
                return f"ERROR: Source node '{src_name}' not found in Actors or Use Cases."
            tgt_node = state.find_uc_node(tgt_name)
            if not tgt_node:
                return f"ERROR: Target node '{tgt_name}' not found in Actors or Use Cases."

            rel = UCRelation(source_id=src_node.id, target_id=tgt_node.id, type=norm_type)
            state.add_relation(rel)
            return f"Created Use Case relation [Association]: '{src_node.name}' -> '{tgt_node.name}' (ID: {rel.id})."
    except Exception as e:
        return f"ERROR: Failed to create use case relation: {str(e)}"


# --- State Machine Diagram Tools ---

def add_state(
    name: str,
    type: str = "State",
    entry: str = "",
    do: str = "",
    exit: str = "",
    description: str = "",
) -> str:
    """Create a state vertex in the UML State Machine diagram with optional internal behaviors.

    Args:
        name: Name of the state (e.g. 'InitialState', 'Draft', 'Processing', 'Finished').
        type: Vertex type:
              - 'Initial': Initial pseudo-state (start of the machine)
              - 'State': Normal operational state
              - 'Final': Final state (termination of the machine)
        entry: Optional behavior executed on state entry (e.g. 'init_timers()').
        do: Optional ongoing activity executed while in state (e.g. 'process_payments()').
        exit: Optional behavior executed on state exit (e.g. 'cleanup()').
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message with State ID or error.
    """
    try:
        clean_name = name.strip()
        if not clean_name:
            return "ERROR: State name cannot be empty."

        norm_type = _normalize_state_type(type)
        existing = state.find_state(clean_name)
        if existing:
            if entry:
                existing.entry_action = entry
            if do:
                existing.do_activity = do
            if exit:
                existing.exit_action = exit
            if description:
                existing.description = description
            return f"Updated State '{clean_name}' (ID: {existing.id}) with behaviors/documentation."

        st = StateModel(
            name=clean_name,
            type=norm_type,
            entry_action=entry,
            do_activity=do,
            exit_action=exit,
            description=description,
        )
        state.add_node(st)
        return f"Created State [{norm_type}] '{clean_name}' (ID: {st.id})."
    except Exception as e:
        return f"ERROR: Failed to create state: {str(e)}"


def add_state_behavior(
    state_name: str,
    entry: str = "",
    do: str = "",
    exit: str = "",
    description: str = "",
) -> str:
    """Add or update internal actions (entry, doActivity, exit) or documentation for an existing state.

    Args:
        state_name: Name or ID of the state vertex.
        entry: Optional entry behavior action.
        do: Optional ongoing doActivity behavior.
        exit: Optional exit behavior action.
        description: Optional documentation description for Open Specification.

    Returns:
        Confirmation message or error feedback.
    """
    try:
        st = state.set_state_behavior(
            state_ref=state_name,
            entry=entry,
            do=do,
            exit=exit,
            description=description,
        )
        behaviors = []
        if st.entry_action:
            behaviors.append(f"entry / {st.entry_action}")
        if st.do_activity:
            behaviors.append(f"do / {st.do_activity}")
        if st.exit_action:
            behaviors.append(f"exit / {st.exit_action}")
        b_str = f" [{', '.join(behaviors)}]" if behaviors else ""
        return f"Updated behaviors for State '{st.name}' (ID: {st.id}){b_str}."
    except Exception as e:
        return f"ERROR: Failed to set state behavior: {str(e)}"


def set_element_documentation(element_name: str, documentation: str) -> str:
    """Set or update rich documentation description for any model element (visible via Open Specification).

    Args:
        element_name: Name or ID of the Class, Package, Entity, UseCase, Actor, or State.
        documentation: Rich description text for the element specification.

    Returns:
        Confirmation message or error feedback.
    """
    try:
        node = state.update_element_description(element_name, documentation)
        if not node:
            return f"ERROR: Element '{element_name}' not found."
        return f"Updated documentation for {type(node).__name__} '{getattr(node, 'name', element_name)}' (ID: {node.id})."
    except Exception as e:
        return f"ERROR: Failed to update documentation: {str(e)}"


def add_state_transition(
    src_name: str,
    tgt_name: str,
    trigger: str = "",
    guard: str = "",
) -> str:
    """Create a transition between two states in the State Machine with trigger and guard condition.

    Args:
        src_name: Name or ID of the source state vertex.
        tgt_name: Name or ID of the target state vertex.
        trigger: Optional event/signal triggering this transition (e.g. 'paySuccess', 'cancelOrder').
        guard: Optional guard condition expression (e.g. 'balance >= total', '[isValid]').

    Returns:
        Confirmation message with Transition ID or error.
    """
    try:
        src = state.find_state(src_name)
        if not src:
            available = [s.name for s in state.states.values()]
            return f"ERROR: Source state '{src_name}' not found. Available: {available}"

        tgt = state.find_state(tgt_name)
        if not tgt:
            available = [s.name for s in state.states.values()]
            return f"ERROR: Target state '{tgt_name}' not found. Available: {available}"

        if src.type == "Final":
            return f"ERROR: UML 2.5 Rule Violation: Final state '{src.name}' cannot have outgoing transitions."

        tr = TransitionModel(
            source_id=src.id,
            target_id=tgt.id,
            type="Transition",
            trigger_event=(trigger or "").strip(),
            guard_condition=(guard or "").strip(),
        )
        state.add_relation(tr)

        details = []
        if tr.trigger_event:
            details.append(f"trigger: '{tr.trigger_event}'")
        if tr.guard_condition:
            details.append(f"guard: [{tr.guard_condition}]")
        detail_str = f" ({', '.join(details)})" if details else ""
        return f"Created State Transition: '{src.name}' -> '{tgt.name}'{detail_str} (ID: {tr.id})."
    except Exception as e:
        return f"ERROR: Failed to create transition: {str(e)}"


# --- Universal Annotation & Boundary Tools ---

def add_note(text: str, target: Optional[str] = None) -> str:
    """Create an architectural Note (yellow sticky comment) on diagrams.

    Notes can attach remarks, business rules, or explanations. If 'target' is specified,
    an Anchor connector (dashed line) is drawn connecting the Note to the target element.

    Args:
        text: Comment/note body text.
        target: Optional name or ID of the model element to annotate (Class, Entity, UseCase, State).

    Returns:
        Confirmation message with Note ID and target attachment status.
    """
    try:
        clean_text = text.strip()
        if not clean_text:
            return "ERROR: Note text cannot be empty."

        clean_target = target.strip() if target else None
        note = state.add_note(text=clean_text, target=clean_target)
        tgt_info = f" attached to '{clean_target}' via Anchor" if clean_target else ""
        return f"Created Note (ID: {note.id}){tgt_info}."
    except Exception as e:
        return f"ERROR: Failed to create note: {str(e)}"


def set_system_boundary(name: str = "System", use_cases: Optional[str] = None) -> str:
    """Define or update the System Boundary enclosing Use Cases in the Use Case diagram.

    The System Boundary forms a container box grouping system use cases and separating them
    from external actors.

    Args:
        name: Title of the system boundary (e.g. 'E-Commerce Platform', 'Billing System').
        use_cases: Optional comma-separated list of use case names to enclose.
                   If omitted, encloses all existing use cases in the diagram.

    Returns:
        Confirmation message with system boundary name and enclosed use cases count.
    """
    try:
        clean_name = name.strip() or "System"
        uc_list: Optional[list[str]] = None
        if use_cases:
            uc_list = [u.strip() for u in use_cases.split(",") if u.strip()]
        boundary = state.set_system_boundary(clean_name, uc_list)
        count = len(boundary.use_case_ids)
        return f"Defined System Boundary '{boundary.name}' enclosing {count} Use Cases (ID: {boundary.id})."
    except Exception as e:
        return f"ERROR: Failed to set system boundary: {str(e)}"


# --- Export and Summary Tools ---

def _notify_vp_live_sync(filepath: str) -> Optional[str]:
    """Attempt to notify the running Visual Paradigm Live Sync plugin to auto-import the XMI."""
    import json
    import os
    import urllib.parse
    import urllib.request

    try:
        abs_path = os.path.abspath(filepath)
        url = f"http://127.0.0.1:19842/import?file={urllib.parse.quote(abs_path)}"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("success"):
                    return f"Live Sync: Automatically sent to active Visual Paradigm session ({os.path.basename(abs_path)})."
    except Exception:
        pass
    return None


def sync_with_visual_paradigm(filepath: Optional[str] = None) -> str:
    """Send an exported XMI model directly to a running Visual Paradigm instance via the Live Sync plugin.

    Args:
        filepath: Optional path to the .xmi file. If not specified, uses the last exported file or project name.

    Returns:
        Status message confirming import in Visual Paradigm or connection instructions if VP is closed.
    """
    import os

    target_path = filepath
    if not target_path:
        target_path = f"{state.name}.xmi"

    if not os.path.exists(target_path):
        res = export_xmi(target_path)
        if res.startswith("ERROR"):
            return res

    sync_notice = _notify_vp_live_sync(target_path)
    if sync_notice:
        return f"SUCCESS: {sync_notice}"
    return (
        f"Visual Paradigm Live Sync server not detected at http://127.0.0.1:19842.\n"
        f"File '{os.path.abspath(target_path)}' is ready on disk.\n"
        f"To import manually in Visual Paradigm: Project > Import > XMI...\n"
        f"Or activate the plugin in Visual Paradigm (MCP menu) for automatic live sync."
    )


def export_diagram_image(
    diagram_name: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """Export the currently active or specified diagram from Visual Paradigm as a high-resolution PNG image.

    Enables multimodal AI agents (and users) to visually inspect the actual rendered diagram
    layout, labels, connector routing, and completeness by opening the exported PNG with `view_file`.

    Args:
        diagram_name: Optional name of the diagram to export (e.g. 'Class Diagram', 'ER Diagram', 'Use Case Diagram').
                      If omitted, exports the active / opened diagram in Visual Paradigm.
        output_path: Optional file path where the PNG will be saved (e.g. './diagram.png').
                     If omitted, automatically generates a PNG in the current working directory.

    Returns:
        Status message with the absolute path of the generated PNG image and instructions to inspect it via `view_file`.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    target_file = output_path
    if not target_file:
        clean_dname = (diagram_name or "active_diagram").strip().replace(" ", "_").lower()
        target_file = os.path.abspath(f"{state.name}_{clean_dname}.png")
    else:
        target_file = os.path.abspath(target_file)

    query_params = [f"file={urllib.parse.quote(target_file)}"]
    if diagram_name and diagram_name.strip():
        query_params.append(f"diagram={urllib.parse.quote(diagram_name.strip())}")

    url = f"http://127.0.0.1:19842/export_image?{'&'.join(query_params)}"
    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success"):
                actual_img = data.get("image_path", target_file)
                diag_title = data.get("diagram", diagram_name or "Active Diagram")
                return (
                    f"SUCCESS: Exported diagram '{diag_title}' to image: {actual_img}\n"
                    f"Visual Inspection (Agent Vision): Call `view_file` on '{actual_img}' to visually "
                    f"inspect the diagram layout, verify package bounding boxes, connector routing, and readability."
                )
            else:
                return f"ERROR: Visual Paradigm image export failed: {data.get('error', 'Unknown error')}"
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            err_data = json.loads(body)
            err_msg = err_data.get("error", body)
        except Exception:
            err_msg = str(e)
        return f"ERROR: Visual Paradigm Live Sync export failed (HTTP {e.code}): {err_msg}"
    except urllib.error.URLError as e:
        return (
            f"ERROR: Cannot connect to Visual Paradigm Live Sync plugin at http://127.0.0.1:19842.\n"
            f"Please ensure Visual Paradigm 18.1 is running and the MCP plugin is enabled (click 'Connect' on the Plugin ribbon).\n"
            f"Details: {str(e)}"
        )
    except Exception as e:
        return f"ERROR: Failed to export diagram image: {str(e)}"


def export_xmi(filepath: str) -> str:
    """Export the architecture to a complete OMG XMI 2.1 file with Visual Paradigm diagram layout.

    Generates the UML Metamodel and the Visual Layout Layer (Shapes, Coordinates,
    Connectors, Waypoints) so that all diagrams are immediately drawn on the canvas
    when imported into Visual Paradigm via 'Project > Import > XMI...'.

    Args:
        filepath: Destination file path (e.g. './architecture.xmi' or 'C:/models/project.xmi').

    Returns:
        Status summary with file path and diagram statistics.
    """
    try:
        clean_path = filepath.strip()
        if not clean_path.lower().endswith(".xmi"):
            clean_path = f"{clean_path}.xmi"

        builder = XMIBuilder(state)
        abs_path = builder.export(clean_path)

        stats = (
            f"Classes: {len(state.classes)} (Relations: {len(state.class_relations)}) | "
            f"Entities: {len(state.entities)} (Relations: {len(state.er_relations)}) | "
            f"Use Cases: {len(state.use_cases)}, Actors: {len(state.actors)} (Relations: {len(state.uc_relations)}) | "
            f"States: {len(state.states)} (Transitions: {len(state.transitions)})"
        )

        sync_notice = _notify_vp_live_sync(abs_path)
        sync_suffix = f"\n{sync_notice}" if sync_notice else "\nReady for Visual Paradigm: Project > Import > XMI..."

        return (
            f"Successfully exported XMI 2.1 with Visual Layout Engine to: {abs_path}\n"
            f"Diagram Statistics: {stats}"
            f"{sync_suffix}"
        )
    except Exception as e:
        return f"ERROR: Failed to export XMI: {str(e)}"


def read_requirements_file(filepath: str) -> str:
    """Read a technical requirements document (.docx, .txt, .md, .json) directly.

    Eliminates the need for running terminal commands or installing python packages.
    Parses sections, text, headings, and tables from Word documents (.docx) and plain text.

    Args:
        filepath: Path to the requirements file (e.g. 'C:/specs/tz.docx' or './requirements.md').

    Returns:
        Structured text content of the requirements document in clean Markdown.
    """
    try:
        content = RequirementsDocReader.read_document(filepath)
        return (
            f"Successfully read requirements document '{filepath}' ({len(content)} characters):\n\n"
            f"{content}"
        )
    except Exception as e:
        return f"ERROR: Failed to read requirements document: {str(e)}"


# ---------------------------------------------------------
# Modular Diagram Population Helpers
# ---------------------------------------------------------

def _build_classes_from_spec(spec: dict, log: list[str]) -> None:
    # 1. Packages
    for p in spec.get("packages", []):
        if isinstance(p, dict) and "name" in p:
            add_package(p["name"], p.get("parent"))
            log.append(f"  + Package: {p['name']}")

    # 2. Classes & Interfaces
    for c in spec.get("classes", []):
        if not isinstance(c, dict) or "name" not in c:
            continue
        elem_type = "Interface" if (c.get("is_interface") or c.get("element_type", "").lower() == "interface") else "Class"
        add_class(
            name=c["name"],
            is_abstract=bool(c.get("is_abstract", False)),
            element_type=elem_type,
            package=c.get("package"),
            description=c.get("description", ""),
        )
        for a in c.get("attributes", []):
            if isinstance(a, dict) and "name" in a:
                add_class_attribute(
                    class_name=c["name"],
                    name=a["name"],
                    type=a.get("type", "string"),
                    visibility=a.get("visibility", "public"),
                    multiplicity=a.get("multiplicity", ""),
                    description=a.get("description", ""),
                )
        for m in c.get("methods", []):
            if isinstance(m, dict) and "name" in m:
                add_class_method(
                    class_name=c["name"],
                    name=m["name"],
                    return_type=m.get("return_type", "void"),
                    params=m.get("params") or m.get("parameters"),
                    description=m.get("description", ""),
                )
        log.append(f"  + Class: {c['name']}")

    # 3. Class Relations
    for r in spec.get("class_relations", []):
        if not isinstance(r, dict) or "source" not in r or "target" not in r:
            continue
        src_n = r["source"]
        tgt_n = r["target"]
        if "hint" in r or "relationship_hint" in r:
            smart_add_relation(src_n, tgt_n, r.get("hint") or r.get("relationship_hint"))
        else:
            add_class_relation(
                src_name=src_n,
                tgt_name=tgt_n,
                type=r.get("type", "Association"),
                src_mult=r.get("source_multiplicity", "") or r.get("src_mult", ""),
                tgt_mult=r.get("target_multiplicity", "") or r.get("tgt_mult", ""),
            )


def _build_erd_from_spec(spec: dict, log: list[str]) -> None:
    # 1. ER Entities
    for e in spec.get("entities", []):
        if not isinstance(e, dict) or "name" not in e:
            continue
        add_er_entity(name=e["name"], description=e.get("description", ""))
        for col in e.get("columns", []):
            if isinstance(col, dict) and "name" in col:
                cname = col["name"].strip()
                col_is_pk = bool(col.get("is_pk", False))
                col_is_fk = bool(col.get("is_fk", False))
                if not col_is_pk and (cname.lower().endswith("_id") or (cname.lower().endswith("id") and len(cname) > 2)) and not col_is_fk:
                    col_is_fk = True

                add_er_column(
                    entity_name=e["name"],
                    name=cname,
                    type=col.get("type", "VARCHAR"),
                    length=col.get("length"),
                    is_nullable=bool(col.get("is_nullable", True)),
                    is_pk=col_is_pk,
                    is_fk=col_is_fk,
                    is_unique=bool(col.get("is_unique", False)),
                    description=col.get("description", ""),
                )
        log.append(f"  + Entity: {e['name']} ({len(e.get('columns', []))} columns)")

    # 2. ER Relations
    for er in spec.get("er_relations", []):
        if isinstance(er, dict) and "source" in er and "target" in er:
            add_er_relation(src_name=er["source"], tgt_name=er["target"], type=er.get("type", "1:N"))


def _build_use_cases_from_spec(spec: dict, log: list[str]) -> None:
    # 1. Actors
    for a in spec.get("actors", []):
        if isinstance(a, dict) and "name" in a:
            add_actor(a["name"], a.get("description", ""))

    # 2. Use Cases
    for uc in spec.get("use_cases", []):
        if isinstance(uc, dict) and "name" in uc:
            add_use_case(uc["name"], uc.get("description", ""))

    # 3. System Boundary
    sb = spec.get("system_boundary")
    if isinstance(sb, dict) and "use_cases" in sb:
        ucs = ",".join(sb["use_cases"]) if isinstance(sb["use_cases"], list) else str(sb["use_cases"])
        set_system_boundary(name=sb.get("name", "System Boundary"), use_cases=ucs)

    # 4. Use Case Relations
    for ucr in spec.get("uc_relations", []):
        if isinstance(ucr, dict) and "source" in ucr and "target" in ucr:
            add_uc_relation(src_name=ucr["source"], tgt_name=ucr["target"], type=ucr.get("type", "Association"))


def _build_states_from_spec(spec: dict, log: list[str]) -> None:
    # 1. States
    for s in spec.get("states", []):
        if isinstance(s, dict) and "name" in s:
            add_state(
                name=s["name"],
                type=s.get("type", "State"),
                entry=s.get("entry", ""),
                do=s.get("do", ""),
                exit=s.get("exit", ""),
                description=s.get("description", ""),
            )

    # 2. State Transitions
    for t in spec.get("transitions", []):
        if isinstance(t, dict) and "source" in t and "target" in t:
            add_state_transition(
                src_name=t["source"],
                tgt_name=t["target"],
                trigger=t.get("trigger", ""),
                guard=t.get("guard", ""),
            )


def _build_notes_from_spec(spec: dict, log: list[str]) -> None:
    for n in spec.get("notes", []):
        if isinstance(n, dict) and "text" in n:
            add_note(text=n["text"], target=n.get("attached_to"))


# ---------------------------------------------------------
# Specialized Deep Diagram Builders (Progressive Modeling)
# ---------------------------------------------------------

def build_class_diagram(
    spec: dict,
    append: bool = True,
    diagram_name: str = "Class Diagram",
    filepath: Optional[str] = None,
) -> str:
    """Build a comprehensive, production-grade UML Class Diagram with high detail.

    Focuses 100% of LLM reasoning on object-oriented domain modeling:
    nested packages, rich classes/interfaces, typed attributes, method signatures,
    full relation types (Generalization, Realization, Composition, Aggregation, Association), and notes.

    Args:
        spec: Dictionary specification containing:
            - "project_name": Optional[str]
            - "packages": list[dict] (e.g. [{"name": "Domain", "parent": None}])
            - "classes": list[dict] with name, attributes, methods, is_abstract, is_interface, package
            - "class_relations": list[dict] with source, target, type, source_multiplicity, target_multiplicity
            - "notes": list[dict] with text, attached_to
        append: If True (default), appends this diagram to the active project without wiping
                previously generated diagrams (e.g. Use Case or ERD). If False, resets project.
        diagram_name: Title of this diagram tab in Visual Paradigm (default: 'Class Diagram').
        filepath: Optional output .xmi path.

    Returns:
        Structured execution summary with export path and element counts.
    """
    try:
        if not isinstance(spec, dict):
            return "ERROR: 'spec' must be a dictionary."

        proj_name = spec.get("project_name", state.name or "ArchitectureProject")
        if not append:
            init_project(proj_name)
        elif not state.name or state.name == "ProjectModel":
            state.name = proj_name

        state.set_diagram_name("ClassDiagram", diagram_name)
        log = [f"=== Building Class Diagram: '{diagram_name}' (Project: {state.name}, append={append}) ==="]

        _build_classes_from_spec(spec, log)
        _build_notes_from_spec(spec, log)

        out_path = filepath or spec.get("filepath") or f"{state.name}.xmi"
        export_result = export_xmi(out_path)
        log.append(f"\n{export_result}")
        return "\n".join(log)
    except Exception as e:
        return f"ERROR: Failed during build_class_diagram: {str(e)}"


def build_erd_diagram(
    spec: dict,
    append: bool = True,
    diagram_name: str = "ER Diagram",
    filepath: Optional[str] = None,
) -> str:
    """Build an exhaustive, production-grade Physical Entity-Relationship Diagram (ERD).

    Focuses 100% of LLM reasoning on relational database modeling:
    normalized tables (3NF), columns with strict Visual Paradigm data types (UUID, BIGINT, VARCHAR, TIMESTAMP),
    Primary Keys (PK), Foreign Keys (FK), Unique constraints, nullability, and Crow's Foot relations (1:1, 1:N, M:N).

    Args:
        spec: Dictionary specification containing:
            - "project_name": Optional[str]
            - "entities": list[dict] with name, columns (type, length, is_pk, is_fk, is_unique, is_nullable)
            - "er_relations": list[dict] with source, target, type ("1:1", "1:N", "M:N")
            - "notes": list[dict] with text, attached_to
        append: If True (default), appends this ERD to the active project without wiping
                previously generated diagrams. If False, resets project.
        diagram_name: Title of this ERD tab in Visual Paradigm (default: 'ER Diagram').
        filepath: Optional output .xmi path.

    Returns:
        Structured execution summary with export path and element counts.
    """
    try:
        if not isinstance(spec, dict):
            return "ERROR: 'spec' must be a dictionary."

        proj_name = spec.get("project_name", state.name or "ArchitectureProject")
        if not append:
            init_project(proj_name)
        elif not state.name or state.name == "ProjectModel":
            state.name = proj_name

        state.set_diagram_name("ERDiagram", diagram_name)
        log = [f"=== Building ER Diagram: '{diagram_name}' (Project: {state.name}, append={append}) ==="]

        _build_erd_from_spec(spec, log)
        _build_notes_from_spec(spec, log)

        out_path = filepath or spec.get("filepath") or f"{state.name}.xmi"
        export_result = export_xmi(out_path)
        log.append(f"\n{export_result}")
        return "\n".join(log)
    except Exception as e:
        return f"ERROR: Failed during build_erd_diagram: {str(e)}"


def build_use_case_diagram(
    spec: dict,
    append: bool = True,
    diagram_name: str = "Use Case Diagram",
    filepath: Optional[str] = None,
) -> str:
    """Build an exhaustive, production-grade UML Use Case Diagram from business requirements.

    Focuses 100% of LLM reasoning on functional requirements and system boundaries:
    primary and secondary Actors, external systems, detailed Use Cases, System Boundary containment,
    and standardized UML 2.5 relationships («Include», «Extend», Actor Associations).

    Args:
        spec: Dictionary specification containing:
            - "project_name": Optional[str]
            - "actors": list[dict] with name, description
            - "use_cases": list[dict] with name, description
            - "system_boundary": Optional[dict] with name, use_cases
            - "uc_relations": list[dict] with source, target, type ("Association", "Include", "Extend")
            - "notes": list[dict] with text, attached_to
        append: If True (default), appends this Use Case diagram to the active project. If False, resets project.
        diagram_name: Title of this Use Case tab in Visual Paradigm (default: 'Use Case Diagram').
        filepath: Optional output .xmi path.

    Returns:
        Structured execution summary with export path and element counts.
    """
    try:
        if not isinstance(spec, dict):
            return "ERROR: 'spec' must be a dictionary."

        proj_name = spec.get("project_name", state.name or "ArchitectureProject")
        if not append:
            init_project(proj_name)
        elif not state.name or state.name == "ProjectModel":
            state.name = proj_name

        state.set_diagram_name("UseCaseDiagram", diagram_name)
        log = [f"=== Building Use Case Diagram: '{diagram_name}' (Project: {state.name}, append={append}) ==="]

        _build_use_cases_from_spec(spec, log)
        _build_notes_from_spec(spec, log)

        out_path = filepath or spec.get("filepath") or f"{state.name}.xmi"
        export_result = export_xmi(out_path)
        log.append(f"\n{export_result}")
        return "\n".join(log)
    except Exception as e:
        return f"ERROR: Failed during build_use_case_diagram: {str(e)}"


def build_state_diagram(
    spec: dict,
    append: bool = True,
    diagram_name: str = "State Machine Diagram",
    filepath: Optional[str] = None,
) -> str:
    """Build an exhaustive UML State Machine Diagram modeling the lifecycle of a domain aggregate.

    Focuses 100% of LLM reasoning on state transitions, lifecycle pipelines,
    internal activities (entry, do, exit), event triggers, and boolean guard conditions [guard].

    Args:
        spec: Dictionary specification containing:
            - "project_name": Optional[str]
            - "states": list[dict] with name, type ("Initial", "State", "Final"), entry, do, exit, description
            - "transitions": list[dict] with source, target, trigger, guard
            - "notes": list[dict] with text, attached_to
        append: If True (default), appends this State Machine to the active project. If False, resets project.
        diagram_name: Title of this State Machine tab in Visual Paradigm (default: 'State Machine Diagram').
        filepath: Optional output .xmi path.

    Returns:
        Structured execution summary with export path and element counts.
    """
    try:
        if not isinstance(spec, dict):
            return "ERROR: 'spec' must be a dictionary."

        proj_name = spec.get("project_name", state.name or "ArchitectureProject")
        if not append:
            init_project(proj_name)
        elif not state.name or state.name == "ProjectModel":
            state.name = proj_name

        state.set_diagram_name("StateDiagram", diagram_name)
        log = [f"=== Building State Machine Diagram: '{diagram_name}' (Project: {state.name}, append={append}) ==="]

        _build_states_from_spec(spec, log)
        _build_notes_from_spec(spec, log)

        out_path = filepath or spec.get("filepath") or f"{state.name}.xmi"
        export_result = export_xmi(out_path)
        log.append(f"\n{export_result}")
        return "\n".join(log)
    except Exception as e:
        return f"ERROR: Failed during build_state_diagram: {str(e)}"


def batch_build_diagrams(
    spec: dict,
    append: bool = False,
    filepath: Optional[str] = None,
) -> str:
    """Build multiple architecture diagrams in a single call, and export to XMI with Live Sync.

    Args:
        spec: Dictionary specification containing all diagram elements.
        append: If True, preserves existing project elements. If False (default), resets project.
        filepath: Optional output file path.

    Returns:
        Structured execution summary with export path and element counts.
    """
    try:
        if not isinstance(spec, dict):
            return "ERROR: 'spec' must be a dictionary."

        proj_name = spec.get("project_name", state.name or "ArchitectureProject")
        if not append:
            init_project(proj_name)
        elif not state.name or state.name == "ProjectModel":
            state.name = proj_name

        log = [f"=== Batch Building Project: {state.name} (append={append}) ==="]

        _build_classes_from_spec(spec, log)
        _build_erd_from_spec(spec, log)
        _build_use_cases_from_spec(spec, log)
        _build_states_from_spec(spec, log)
        _build_notes_from_spec(spec, log)

        out_path = filepath or spec.get("filepath") or f"{state.name}.xmi"
        export_result = export_xmi(out_path)
        log.append(f"\n{export_result}")
        return "\n".join(log)
    except Exception as e:
        return f"ERROR: Failed during batch_build_diagrams: {str(e)}"


def get_project_summary() -> str:
    """Return a detailed text overview of the current project state across all 4 diagrams.

    Useful for LLM self-reflection and validation before continuing or exporting.

    Returns:
        Structured breakdown of all packages, classes, entities, use cases, and state machine nodes.
    """
    lines = [f"=== Project: {state.name} ==="]

    if state.packages:
        lines.append(f"\n0. UML Packages ({len(state.packages)}):")
        for p in state.packages.values():
            parent_info = f" (parent: {state.packages[p.parent_package_id].name})" if (p.parent_package_id and p.parent_package_id in state.packages) else ""
            contained_classes = [state.classes[cid].name for cid in p.class_ids if cid in state.classes]
            c_str = f" | Contained classes: [{', '.join(contained_classes)}]" if contained_classes else ""
            lines.append(f"  Package: {p.name}{parent_info}{c_str}")

    lines.append(f"\n1. UML Classes ({len(state.classes)}):")
    for c in state.classes.values():
        pkg_info = f" [in Package: {state.packages[c.package_id].name}]" if (c.package_id and c.package_id in state.packages) else ""
        lines.append(f"  {c.element_type}: {c.name}{pkg_info} (abstract={c.is_abstract})")
        for a in c.attributes:
            lines.append(f"    - {a.visibility} {a.name}: {a.type}")
        for m in c.methods:
            p_str = ", ".join(f"{p.name}: {p.type}" for p in m.params)
            lines.append(f"    - +{m.name}({p_str}): {m.return_type}")
    for cr in state.class_relations:
        s = state.find_class(cr.source_id)
        t = state.find_class(cr.target_id)
        m_str = f" [{cr.source_multiplicity}..{cr.target_multiplicity}]" if cr.source_multiplicity or cr.target_multiplicity else ""
        lines.append(f"  Relation [{cr.type}{m_str}]: {s.name if s else cr.source_id} -> {t.name if t else cr.target_id}")

    lines.append(f"\n2. ER Entities ({len(state.entities)}):")
    for e in state.entities.values():
        lines.append(f"  Entity: {e.name}")
        for col in e.columns:
            flags = []
            if col.is_primary_key:
                flags.append("PK")
            if col.is_foreign_key:
                flags.append("FK")
            if not col.is_nullable:
                flags.append("NOT NULL")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            t_str = f"{col.type}({col.length})" if col.length else col.type
            lines.append(f"    - {col.name}: {t_str}{flag_str}")
    for er in state.er_relations:
        s = state.find_entity(er.source_id)
        t = state.find_entity(er.target_id)
        lines.append(f"  Relation [{er.type}]: {s.name if s else er.source_id} -> {t.name if t else er.target_id}")

    lines.append(f"\n3. Use Case Diagram (Actors: {len(state.actors)}, UseCases: {len(state.use_cases)}):")
    if state.system_boundary:
        lines.append(f"  System Boundary: '{state.system_boundary.name}' (enclosing {len(state.system_boundary.use_case_ids)} use cases)")
    for a in state.actors.values():
        lines.append(f"  Actor: {a.name}")
    for uc in state.use_cases.values():
        lines.append(f"  UseCase: {uc.name}")
    for ucr in state.uc_relations:
        s = state.find_uc_node(ucr.source_id)
        t = state.find_uc_node(ucr.target_id)
        lines.append(f"  Relation [{ucr.type}]: {s.name if s else ucr.source_id} -> {t.name if t else ucr.target_id}")

    lines.append(f"\n4. State Machine (States: {len(state.states)}, Transitions: {len(state.transitions)}):")
    for st in state.states.values():
        lines.append(f"  State [{st.type}]: {st.name}")
    for tr in state.transitions:
        s = state.find_state(tr.source_id)
        t = state.find_state(tr.target_id)
        details = []
        if tr.trigger_event:
            details.append(f"trigger: {tr.trigger_event}")
        if tr.guard_condition:
            details.append(f"guard: [{tr.guard_condition}]")
        trig = f" ({', '.join(details)})" if details else ""
        lines.append(f"  Transition: {s.name if s else tr.source_id} -> {t.name if t else tr.target_id}{trig}")

    if state.notes:
        lines.append(f"\n5. Notes & Annotations ({len(state.notes)}):")
        for n in state.notes.values():
            tgt_node = state.find_node_by_id(n.target_id) if n.target_id else None
            tgt_str = f" [attached to '{tgt_node.name}']" if tgt_node else ""
            lines.append(f"  Note: \"{n.text}\"{tgt_str}")

    return "\n".join(lines)


def register_all_tools(mcp: Any) -> None:
    """Register all architecture tools with the provided FastMCP or MCPServer instance."""
    tools = [
        init_project,
        add_package,
        move_class_to_package,
        add_class,
        add_class_attribute,
        add_class_method,
        add_class_relation,
        suggest_relation,
        smart_add_relation,
        add_er_entity,
        add_er_column,
        add_er_relation,
        add_actor,
        add_use_case,
        add_uc_relation,
        set_system_boundary,
        add_state,
        add_state_behavior,
        add_state_transition,
        set_element_documentation,
        add_note,
        export_xmi,
        read_requirements_file,
        build_class_diagram,
        build_erd_diagram,
        build_use_case_diagram,
        build_state_diagram,
        batch_build_diagrams,
        sync_with_visual_paradigm,
        export_diagram_image,
        get_project_summary,
    ]
    for tool_fn in tools:
        mcp.tool()(tool_fn)
