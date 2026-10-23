"""Singleton in-memory project state manager with thread-safe operations and UML/ERD integrity rules."""

import threading
from typing import Optional, Union
from core.models import (
    ActorNode,
    BaseNode,
    ClassNode,
    EntityNode,
    RelationModel,
    StateNode,
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
            self.classes: dict[str, ClassNode] = {}
            self.entities: dict[str, EntityNode] = {}
            self.actors: dict[str, ActorNode] = {}
            self.use_cases: dict[str, UseCaseNode] = {}
            self.states: dict[str, StateNode] = {}
            self.relations: list[RelationModel] = []
            self._initialized = True

    def clear(self, name: str = "ProjectModel") -> None:
        """Reset all storage collections and update project name."""
        with self._lock:
            self.name = name
            self.classes.clear()
            self.entities.clear()
            self.actors.clear()
            self.use_cases.clear()
            self.states.clear()
            self.relations.clear()

    # ---------------------------------------------------------
    # Core State Modification Methods
    # ---------------------------------------------------------

    def add_node(self, node: BaseNode) -> None:
        """Add any BaseNode subtype into the appropriate dictionary collection."""
        with self._lock:
            if isinstance(node, ClassNode):
                self.classes[node.id] = node
            elif isinstance(node, EntityNode):
                self.entities[node.id] = node
            elif isinstance(node, ActorNode):
                self.actors[node.id] = node
            elif isinstance(node, UseCaseNode):
                self.use_cases[node.id] = node
            elif isinstance(node, StateNode):
                self.states[node.id] = node

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
            return None

    def find_node_by_name(self, name: str) -> Optional[BaseNode]:
        """Find any node by exact or case-insensitive name across all collections."""
        with self._lock:
            # 1. Exact match
            for collection in (self.classes, self.entities, self.actors, self.use_cases, self.states):
                for item in collection.values():
                    if item.name == name:
                        return item
            # 2. Case-insensitive match
            name_lower = name.lower()
            for collection in (self.classes, self.entities, self.actors, self.use_cases, self.states):
                for item in collection.values():
                    if item.name.lower() == name_lower:
                        return item
            return None

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
        items = [r for r in self.relations if r.type in ("1:1", "1:N", "M:N")]
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


# Global Singleton Instance
state = ProjectState()
