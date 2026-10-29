"""Singleton in-memory project state manager with thread-safe operations and UML/ERD integrity rules."""

import threading
from typing import Optional, Union
from core.models import (
    ActivityNode,
    ActivityPartitionNode,
    ActorNode,
    ArtifactNode,
    BaseNode,
    ClassNode,
    DeployNode,
    EntityNode,
    NoteNode,
    PackageNode,
    RelationModel,
    StateNode,
    SystemBoundaryNode,
    UseCaseNode,
)


class _RelationList(list):
    """List proxy that synchronizes appended items back to the ProjectState instance."""

    def __init__(self, items: list[RelationModel], state_instance: "ProjectState") -> None:
        super().__init__(items)
        self._state = state_instance

    def append(self, item: RelationModel) -> None:
        super().append(item)
        if self._state is not None and item not in self._state.relations:
            self._state.add_relation(item)

    def extend(self, items: list[RelationModel]) -> None:
        super().extend(items)
        if self._state is not None:
            for item in items:
                if item not in self._state.relations:
                    self._state.add_relation(item)



class ProjectState:
    """Thread-safe in-memory store for all architectural diagram models with graph validation."""

    _instance: Optional["ProjectState"] = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs) -> "ProjectState":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, name: str = "ProjectModel") -> None:
        with self._lock:
            if getattr(self, "_initialized", False):
                return
            self.name: str = name
            self.packages: dict[str, PackageNode] = {}
            self.classes: dict[str, ClassNode] = {}
            self.entities: dict[str, EntityNode] = {}
            self.actors: dict[str, ActorNode] = {}
            self.use_cases: dict[str, UseCaseNode] = {}
            self.states: dict[str, StateNode] = {}
            self.activity_nodes: dict[str, ActivityNode] = {}
            self.activity_partitions: dict[str, ActivityPartitionNode] = {}
            self.deployment_nodes: dict[str, DeployNode] = {}
            self.deployment_artifacts: dict[str, ArtifactNode] = {}
            self.notes: dict[str, NoteNode] = {}
            self.system_boundary: Optional[SystemBoundaryNode] = None
            self.diagram_names: dict[str, str] = {}
            self.relations: list[RelationModel] = []
            self._initialized = True

    def clear(self, name: str = "ProjectModel") -> None:
        """Reset all storage collections and update project name."""
        with self._lock:
            self.name = name
            self.packages.clear()
            self.classes.clear()
            self.entities.clear()
            self.actors.clear()
            self.use_cases.clear()
            self.states.clear()
            self.activity_nodes.clear()
            self.activity_partitions.clear()
            self.deployment_nodes.clear()
            self.deployment_artifacts.clear()
            self.notes.clear()
            self.system_boundary = None
            self.diagram_names.clear()
            self.relations.clear()

    def set_diagram_name(self, diag_type: str, name: str) -> None:
        """Set a custom title for a specific diagram type (e.g. 'ClassDiagram' -> 'Domain Model')."""
        with self._lock:
            if diag_type and name:
                self.diagram_names[diag_type] = name.strip()

    # ---------------------------------------------------------
    # Core State Modification Methods
    # ---------------------------------------------------------

    def add_node(self, node: BaseNode) -> None:
        """Add any BaseNode subtype into the appropriate dictionary collection."""
        with self._lock:
            if isinstance(node, PackageNode):
                self.packages[node.id] = node
            elif isinstance(node, ClassNode):
                self.classes[node.id] = node
            elif isinstance(node, EntityNode):
                self.entities[node.id] = node
            elif isinstance(node, ActorNode):
                self.actors[node.id] = node
            elif isinstance(node, UseCaseNode):
                self.use_cases[node.id] = node
            elif isinstance(node, StateNode):
                self.states[node.id] = node
            elif isinstance(node, ActivityNode):
                self.activity_nodes[node.id] = node
            elif isinstance(node, ActivityPartitionNode):
                self.activity_partitions[node.id] = node
            elif isinstance(node, DeployNode):
                self.deployment_nodes[node.id] = node
            elif isinstance(node, ArtifactNode):
                self.deployment_artifacts[node.id] = node
            elif isinstance(node, NoteNode):
                self.notes[node.id] = node
            elif isinstance(node, SystemBoundaryNode):
                self.system_boundary = node

    def add_relation(self, rel: RelationModel) -> None:
        """Add a relationship into the in-memory relations collection."""
        with self._lock:
            self.relations.append(rel)

    # ---------------------------------------------------------
    # Unified & Specialized Lookup Helpers
    # ---------------------------------------------------------

    def find_node_by_id(self, node_id: str) -> Optional[BaseNode]:
        """Find any node by its unique XMI ID."""
        with self._lock:
            if node_id in self.packages:
                return self.packages[node_id]
            if node_id in self.classes:
                return self.classes[node_id]
            if node_id in self.entities:
                return self.entities[node_id]
            if node_id in self.actors:
                return self.actors[node_id]
            if node_id in self.use_cases:
                return self.use_cases[node_id]
            if node_id in self.states:
                return self.states[node_id]
            if node_id in self.activity_nodes:
                return self.activity_nodes[node_id]
            if node_id in self.activity_partitions:
                return self.activity_partitions[node_id]
            if node_id in self.deployment_nodes:
                return self.deployment_nodes[node_id]
            if node_id in self.deployment_artifacts:
                return self.deployment_artifacts[node_id]
            if node_id in self.notes:
                return self.notes[node_id]
            if self.system_boundary and self.system_boundary.id == node_id:
                return self.system_boundary
            return None

    def find_node_by_name(self, name: str) -> Optional[BaseNode]:
        """Find any node by exact or case-insensitive name across all collections."""
        with self._lock:
            all_collections = (
                self.packages,
                self.classes,
                self.entities,
                self.actors,
                self.use_cases,
                self.states,
                self.activity_nodes,
                self.activity_partitions,
                self.deployment_nodes,
                self.deployment_artifacts,
                self.notes,
            )
            # 1. Exact match
            for collection in all_collections:
                for item in collection.values():
                    if item.name == name:
                        return item
            if self.system_boundary and self.system_boundary.name == name:
                return self.system_boundary
            # 2. Case-insensitive match
            name_lower = name.lower()
            for collection in all_collections:
                for item in collection.values():
                    if item.name.lower() == name_lower:
                        return item
            if self.system_boundary and self.system_boundary.name.lower() == name_lower:
                return self.system_boundary
            return None

    def find_package(self, identifier: str) -> Optional[PackageNode]:
        """Find a Package by ID or exact/case-insensitive Name."""
        with self._lock:
            if identifier in self.packages:
                return self.packages[identifier]
            for pkg in self.packages.values():
                if pkg.name == identifier:
                    return pkg
            norm = identifier.lower()
            for pkg in self.packages.values():
                if pkg.name.lower() == norm:
                    return pkg
            return None

    def create_package(self, name: str, parent_package: Optional[str] = None) -> PackageNode:
        """Create a package or return existing one, optionally nesting under a parent package."""
        with self._lock:
            existing = self.find_package(name)
            if existing is not None:
                pkg = existing
            else:
                pkg = PackageNode(name=name)
                self.packages[pkg.id] = pkg

            if parent_package:
                parent = self.find_package(parent_package)
                if parent is None:
                    parent = PackageNode(name=parent_package)
                    self.packages[parent.id] = parent
                if pkg.id not in parent.child_package_ids:
                    parent.child_package_ids.append(pkg.id)
                pkg.parent_package_id = parent.id

            return pkg

    def move_class_to_package(self, class_name: str, package_name: str) -> tuple[ClassNode, PackageNode]:
        """Move an existing class into a package, updating bidirectional containment."""
        with self._lock:
            cls_obj = self.find_class(class_name)
            if cls_obj is None:
                raise ValueError(f"Class '{class_name}' not found.")
            pkg_obj = self.find_package(package_name)
            if pkg_obj is None:
                pkg_obj = self.create_package(package_name)

            if cls_obj.package_id and cls_obj.package_id in self.packages:
                old_pkg = self.packages[cls_obj.package_id]
                if cls_obj.id in old_pkg.class_ids:
                    old_pkg.class_ids.remove(cls_obj.id)

            cls_obj.package_id = pkg_obj.id
            if cls_obj.id not in pkg_obj.class_ids:
                pkg_obj.class_ids.append(cls_obj.id)

            return cls_obj, pkg_obj

    def find_class(self, identifier: str) -> Optional[ClassNode]:
        """Find a Class by ID or exact/case-insensitive Name."""
        with self._lock:
            if identifier in self.classes:
                return self.classes[identifier]
            for cls in self.classes.values():
                if cls.name == identifier:
                    return cls
            norm = identifier.lower()
            for cls in self.classes.values():
                if cls.name.lower() == norm:
                    return cls
            return None

    def find_entity(self, identifier: str) -> Optional[EntityNode]:
        """Find an ER Entity by ID or exact/case-insensitive Name."""
        with self._lock:
            if identifier in self.entities:
                return self.entities[identifier]
            for ent in self.entities.values():
                if ent.name == identifier:
                    return ent
            norm = identifier.lower()
            for ent in self.entities.values():
                if ent.name.lower() == norm:
                    return ent
            return None

    def find_actor(self, identifier: str) -> Optional[ActorNode]:
        """Find an Actor by ID or Name."""
        with self._lock:
            if identifier in self.actors:
                return self.actors[identifier]
            for act in self.actors.values():
                if act.name == identifier or act.name.lower() == identifier.lower():
                    return act
            return None

    def find_use_case(self, identifier: str) -> Optional[UseCaseNode]:
        """Find a Use Case by ID or Name."""
        with self._lock:
            if identifier in self.use_cases:
                return self.use_cases[identifier]
            for uc in self.use_cases.values():
                if uc.name == identifier or uc.name.lower() == identifier.lower():
                    return uc
            return None

    def find_uc_node(self, identifier: str) -> Optional[Union[ActorNode, UseCaseNode]]:
        """Find either an Actor or a Use Case by ID or Name."""
        with self._lock:
            actor = self.find_actor(identifier)
            if actor:
                return actor
            return self.find_use_case(identifier)

    def find_state(self, identifier: str) -> Optional[StateNode]:
        """Find a State vertex by ID or Name."""
        with self._lock:
            if identifier in self.states:
                return self.states[identifier]
            for st in self.states.values():
                if st.name == identifier or st.name.lower() == identifier.lower():
                    return st
            return None

    def find_activity_node(self, identifier: str) -> Optional[ActivityNode]:
        """Find an ActivityNode by ID or Name."""
        with self._lock:
            if identifier in self.activity_nodes:
                return self.activity_nodes[identifier]
            for act in self.activity_nodes.values():
                if act.name == identifier or act.name.lower() == identifier.lower():
                    return act
            return None

    def find_activity_partition(self, identifier: str) -> Optional[ActivityPartitionNode]:
        """Find an ActivityPartitionNode (Swimlane) by ID or Name."""
        with self._lock:
            if identifier in self.activity_partitions:
                return self.activity_partitions[identifier]
            for part in self.activity_partitions.values():
                if part.name == identifier or part.name.lower() == identifier.lower():
                    return part
            return None

    def find_deploy_node(self, identifier: str) -> Optional[DeployNode]:
        """Find a DeployNode by ID or Name."""
        with self._lock:
            if identifier in self.deployment_nodes:
                return self.deployment_nodes[identifier]
            for dnode in self.deployment_nodes.values():
                if dnode.name == identifier or dnode.name.lower() == identifier.lower():
                    return dnode
            return None

    def find_artifact(self, identifier: str) -> Optional[ArtifactNode]:
        """Find an ArtifactNode by ID or Name."""
        with self._lock:
            if identifier in self.deployment_artifacts:
                return self.deployment_artifacts[identifier]
            for art in self.deployment_artifacts.values():
                if art.name == identifier or art.name.lower() == identifier.lower():
                    return art
            return None

    def set_state_behavior(
        self,
        state_ref: str,
        entry: str = "",
        do: str = "",
        exit: str = "",
        description: str = "",
    ) -> StateNode:
        """Set entry, doActivity, exit behaviors and description for a state vertex."""
        with self._lock:
            st = self.find_state(state_ref)
            if st is None:
                raise ValueError(f"State '{state_ref}' not found.")
            if entry:
                st.entry_action = entry
            if do:
                st.do_activity = do
            if exit:
                st.exit_action = exit
            if description:
                st.description = description
            return st

    def update_element_description(self, element_ref: str, description: str) -> Optional[BaseNode]:
        """Update documentation description for any architectural model element."""
        with self._lock:
            node = self.find_node_by_name(element_ref) or self.find_node_by_id(element_ref)
            if node:
                node.description = description
            return node

    # Categorized relations accessors
    @property
    def class_relations(self) -> list[RelationModel]:
        items = [
            r for r in self.relations
            if r.type in ("Association", "Generalization", "Composition", "Aggregation", "Dependency", "Realization")
            and r.source_id in self.classes
        ]
        return _RelationList(items, self)

    @property
    def er_relations(self) -> list[RelationModel]:
        items = [r for r in self.relations if r.type in ("1:1", "1:N", "N:1", "M:1", "M:N", "N:M")]
        return _RelationList(items, self)

    @property
    def uc_relations(self) -> list[RelationModel]:
        items = [
            r for r in self.relations
            if r.type in ("Include", "Extend")
            or (r.type == "Association" and (r.source_id in self.actors or r.source_id in self.use_cases))
        ]
        return _RelationList(items, self)

    @property
    def transitions(self) -> list[RelationModel]:
        items = [
            r for r in self.relations
            if r.type == "Transition" or (r.source_id in self.states and r.target_id in self.states)
        ]
        return _RelationList(items, self)

    @property
    def activity_flows(self) -> list[RelationModel]:
        items = [
            r for r in self.relations
            if r.type in ("ControlFlow", "ObjectFlow")
            or (r.source_id in self.activity_nodes and r.target_id in self.activity_nodes)
        ]
        return _RelationList(items, self)

    @property
    def deployment_relations(self) -> list[RelationModel]:
        items = [
            r for r in self.relations
            if r.type in ("CommunicationPath", "Deployment", "Manifestation")
            or (r.source_id in self.deployment_nodes or r.target_id in self.deployment_nodes
                or r.source_id in self.deployment_artifacts or r.target_id in self.deployment_artifacts)
        ]
        return _RelationList(items, self)

    # ---------------------------------------------------------
    # Rules Engine & Graph Validation Helpers
    # ---------------------------------------------------------

    def would_cause_inheritance_cycle(self, child_id: str, parent_id: str) -> bool:
        """Check if making parent_id the superclass of child_id introduces an inheritance loop."""
        with self._lock:
            if child_id == parent_id:
                return True

            visited = set()
            queue = [parent_id]

            while queue:
                curr = queue.pop(0)
                if curr == child_id:
                    return True
                if curr in visited:
                    continue
                visited.add(curr)

                for rel in self.class_relations:
                    if rel.type == "Generalization" and rel.source_id == curr:
                        queue.append(rel.target_id)

            return False

    def validate_er_1_to_n(self, target_entity_id: str) -> bool:
        """Verify that child entity in 1:N relationship has a foreign key column defined."""
        with self._lock:
            entity = self.entities.get(target_entity_id)
            if not entity:
                return False
            return entity.has_foreign_key()

    def add_note(self, text: str, target: Optional[str] = None) -> NoteNode:
        """Create a Note (yellow comment) and optionally connect it via Anchor to a target node."""
        with self._lock:
            tgt_id = None
            if target:
                tgt_node = self.find_node_by_name(target) or self.find_node_by_id(target)
                if tgt_node:
                    tgt_id = tgt_node.id
                else:
                    tgt_id = target

            note = NoteNode(text=text, target_id=tgt_id)
            self.notes[note.id] = note
            if tgt_id:
                anchor_rel = RelationModel(
                    source_id=note.id,
                    target_id=tgt_id,
                    type="Anchor",
                )
                self.relations.append(anchor_rel)
            return note

    def set_system_boundary(self, name: str, use_cases: Optional[list[str]] = None) -> SystemBoundaryNode:
        """Define or update the System Boundary enclosing Use Cases."""
        with self._lock:
            uc_ids: list[str] = []
            if use_cases:
                for uc_ref in use_cases:
                    uc_obj = self.find_uc_node(uc_ref)
                    if uc_obj:
                        uc_ids.append(uc_obj.id)
            else:
                uc_ids = list(self.use_cases.keys())

            boundary = SystemBoundaryNode(name=name, use_case_ids=uc_ids)
            self.system_boundary = boundary
            return boundary


# Global Singleton Instance
state = ProjectState()

