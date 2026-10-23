"""Smart Layout Engine for UML and ERD diagrams in Visual Paradigm.

Features:
1. Dynamic Bounding Box calculation for nested packages (Package in Package -> Class).
2. Hierarchical DAG Layout for Class Diagrams (Sugiyama-style layer assignment).
3. 3-Tier Columnar Layout for Use Case Diagrams (Actors -> Core Cases -> Sub-cases/Secondary Actors).
4. Foreign-Key Dependency Layout for ER Diagrams.
5. Linear Pipeline Flow Layout for State Machine Diagrams with looped back-transitions.
"""

import math
from typing import Optional
from core.models import (
    ActorNode,
    BaseNode,
    ClassNode,
    EntityNode,
    PackageNode,
    RelationModel,
    StateNode,
    UseCaseNode,
)
from core.state import ProjectState


class NodePlacement:
    """Calculated layout coordinates and dimensions for a diagram shape."""

    def __init__(
        self,
        node_id: str,
        shape_id: str,
        x: int,
        y: int,
        width: int = 160,
        height: int = 90,
        parent_shape_id: Optional[str] = None,
    ):
        self.node_id = node_id
        self.shape_id = shape_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.parent_shape_id = parent_shape_id

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    @property
    def geometry_str(self) -> str:
        return f"{self.x},{self.y},{self.width},{self.height}"


class BoundingBoxCalculator:
    """Calculates dynamic dimensions for classes, entities, and nested packages bottom-up."""

    HEADER_OFFSET = 36  # Visual Paradigm package tab/header height
    PADDING_X = 30      # Inner horizontal padding
    PADDING_Y = 25      # Inner vertical padding

    @staticmethod
    def calculate_class_dimension(node: ClassNode) -> tuple[int, int]:
        """Compute shape dimensions based on name length and member count."""
        attr_count = len(getattr(node, "attributes", []))
        method_count = len(getattr(node, "methods", []))
        name_len = len(getattr(node, "name", ""))
        calc_width = max(170, 12 * name_len + 30)
        calc_height = max(80, 40 + 18 * attr_count + 18 * method_count)
        return calc_width, calc_height

    @staticmethod
    def calculate_entity_dimension(node: EntityNode) -> tuple[int, int]:
        """Compute shape dimensions for ERD entities based on column count."""
        col_count = len(getattr(node, "columns", []))
        name_len = len(getattr(node, "name", ""))
        calc_width = max(170, 12 * name_len + 30)
        calc_height = max(80, 42 + 18 * col_count)
        return calc_width, calc_height

    @classmethod
    def calculate_package_bounding_box(
        cls,
        pkg: PackageNode,
        state: ProjectState,
        child_placements: dict[str, NodePlacement],
    ) -> tuple[int, int, int, int]:
        """Calculate (x, y, w, h) enclosing all child classes and nested packages with padding."""
        direct_children: list[NodePlacement] = []

        # 1. Collect direct class placements
        for cid in pkg.class_ids:
            if cid in child_placements:
                direct_children.append(child_placements[cid])

        # 2. Collect nested package placements (already calculated recursively)
        for sub_id in pkg.child_package_ids:
            if sub_id in child_placements:
                direct_children.append(child_placements[sub_id])

        if not direct_children:
            # Empty package default size
            return 50, 50, 220, 140

        min_x = min(p.x for p in direct_children)
        min_y = min(p.y for p in direct_children)
        max_x = max(p.x + p.width for p in direct_children)
        max_y = max(p.y + p.height for p in direct_children)

        x = max(20, min_x - cls.PADDING_X)
        y = max(20, min_y - cls.HEADER_OFFSET - cls.PADDING_Y)
        w = (max_x - min_x) + 2 * cls.PADDING_X
        h = (max_y - min_y) + cls.HEADER_OFFSET + 2 * cls.PADDING_Y
        return x, y, w, h


# ---------------------------------------------------------
# 1. Hierarchical Class Diagram Layout (Sugiyama / Layered DAG)
# ---------------------------------------------------------

class HierarchicalClassLayout:
    """Places classes in distinct vertical layers based on inheritance and containment hierarchy."""

    def __init__(self, start_x: int = 60, start_y: int = 60, gap_x: int = 60, gap_y: int = 100):
        self.start_x = start_x
        self.start_y = start_y
        self.gap_x = gap_x
        self.gap_y = gap_y

    def layout(self, state: ProjectState) -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}
        if not state.classes and not state.packages:
            return placements

        # A. First layout classes inside packages
        # To handle nested packages, process from leaf packages up to root packages
        package_depth: dict[str, int] = {}

        def get_depth(pid: str) -> int:
            if pid not in package_depth:
                pkg = state.packages.get(pid)
                if not pkg or not pkg.parent_package_id:
                    package_depth[pid] = 0
                else:
                    package_depth[pid] = 1 + get_depth(pkg.parent_package_id)
            return package_depth[pid]

        sorted_packages = sorted(state.packages.values(), key=lambda p: get_depth(p.id), reverse=True)

        current_pkg_x = self.start_x
        current_pkg_y = self.start_y

        # Layout leaf packages first
        for pkg in sorted_packages:
            # Layout classes inside this package
            pkg_classes = [state.classes[cid] for cid in pkg.class_ids if cid in state.classes]
            cols = max(2, int(math.ceil(math.sqrt(len(pkg_classes))))) if pkg_classes else 2

            local_x = current_pkg_x + BoundingBoxCalculator.PADDING_X
            local_y = current_pkg_y + BoundingBoxCalculator.HEADER_OFFSET + BoundingBoxCalculator.PADDING_Y

            for i, cls_node in enumerate(pkg_classes):
                col = i % cols
                row = i // cols
                w, h = BoundingBoxCalculator.calculate_class_dimension(cls_node)
                pos_x = local_x + col * (w + 40)
                pos_y = local_y + row * (h + 30)

                placements[cls_node.id] = NodePlacement(
                    node_id=cls_node.id,
                    shape_id=f"shape_{cls_node.id}",
                    x=pos_x,
                    y=pos_y,
                    width=w,
                    height=h,
                    parent_shape_id=f"shape_{pkg.id}",
                )

            # Compute bounding box of this package
            px, py, pw, ph = BoundingBoxCalculator.calculate_package_bounding_box(pkg, state, placements)
            parent_sid = f"shape_{pkg.parent_package_id}" if pkg.parent_package_id else None
            placements[pkg.id] = NodePlacement(
                node_id=pkg.id,
                shape_id=f"shape_{pkg.id}",
                x=px,
                y=py,
                width=pw,
                height=ph,
                parent_shape_id=parent_sid,
            )
            current_pkg_x += pw + self.gap_x

        # B. Layout top-level classes (not in any package) using Hierarchical DAG (Layered)
        top_classes = [c for c in state.classes.values() if not c.package_id]
        if top_classes:
            top_placements = self._layout_dag_classes(top_classes, state, base_y=current_pkg_y if not state.packages else (max(p.y + p.height for p in placements.values()) + self.gap_y))
            placements.update(top_placements)

        return placements

    def _layout_dag_classes(
        self,
        classes: list[ClassNode],
        state: ProjectState,
        base_y: int,
    ) -> dict[str, NodePlacement]:
        """Compute DAG hierarchical layers: root interfaces/base classes on top, subclasses below."""
        class_ids = {c.id for c in classes}
        in_degree: dict[str, int] = {c.id: 0 for c in classes}
        children_map: dict[str, list[str]] = {c.id: [] for c in classes}

        for rel in state.class_relations:
            if rel.type in ("Generalization", "Realization"):
                # source inherits from target, so target is parent (higher level)
                if rel.source_id in class_ids and rel.target_id in class_ids:
                    in_degree[rel.source_id] += 1
                    children_map[rel.target_id].append(rel.source_id)

        # Level assignment (Longest path from roots)
        levels: dict[str, int] = {}
        roots = [cid for cid, deg in in_degree.items() if deg == 0]
        if not roots:
            roots = list(class_ids)

        queue = [(cid, 0) for cid in roots]
        for cid, lvl in queue:
            levels[cid] = max(levels.get(cid, 0), lvl)
            for child_id in children_map.get(cid, []):
                queue.append((child_id, lvl + 1))

        # Group by level
        level_groups: dict[int, list[str]] = {}
        for cid in class_ids:
            lvl = levels.get(cid, 0)
            level_groups.setdefault(lvl, []).append(cid)

        placements: dict[str, NodePlacement] = {}
        curr_y = base_y

        for lvl in sorted(level_groups.keys()):
            cids_in_level = level_groups[lvl]
            curr_x = self.start_x
            max_level_h = 80

            for cid in cids_in_level:
                cls_node = state.classes[cid]
                w, h = BoundingBoxCalculator.calculate_class_dimension(cls_node)
                max_level_h = max(max_level_h, h)

                placements[cid] = NodePlacement(
                    node_id=cid,
                    shape_id=f"shape_{cid}",
                    x=curr_x,
                    y=curr_y,
                    width=w,
                    height=h,
                )
                curr_x += w + self.gap_x

            curr_y += max_level_h + self.gap_y

        return placements


# ---------------------------------------------------------
# 2. Use Case Diagram Layout (3-Tier Columnar Architecture)
# ---------------------------------------------------------

class UseCaseTierLayout:
    """Arranges Use Case diagrams in 3 clear functional columns from left to right."""

    def __init__(self, col1_x: int = 60, col2_x: int = 360, col3_x: int = 680, start_y: int = 60, gap_y: int = 130):
        self.col1_x = col1_x
        self.col2_x = col2_x
        self.col3_x = col3_x
        self.start_y = start_y
        self.gap_y = gap_y

    def layout(self, state: ProjectState) -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}

        # 1. Primary Actors (associated with UseCases) -> Column 1
        # Secondary Actors or sub-cases -> Column 3
        primary_actors: list[ActorNode] = []
        secondary_actors: list[ActorNode] = []

        for act in state.actors.values():
            if "admin" in act.name.lower() or "service" in act.name.lower() or "system" in act.name.lower():
                secondary_actors.append(act)
            else:
                primary_actors.append(act)

        # 2. Distinguish Core Use Cases from Sub-UseCases (Include/Extend targets)
        sub_uc_ids: set[str] = set()
        for rel in state.uc_relations:
            if rel.type in ("Include", "Extend"):
                sub_uc_ids.add(rel.target_id)

        core_cases = [uc for uc in state.use_cases.values() if uc.id not in sub_uc_ids]
        sub_cases = [uc for uc in state.use_cases.values() if uc.id in sub_uc_ids]

        # Place Column 1: Primary Actors
        y_col1 = self.start_y
        for act in primary_actors:
            placements[act.id] = NodePlacement(
                node_id=act.id,
                shape_id=f"shape_{act.id}",
                x=self.col1_x,
                y=y_col1,
                width=80,
                height=80,
            )
            y_col1 += 80 + self.gap_y

        # Place Column 2: Core Business Use Cases
        y_col2 = self.start_y
        for uc in core_cases:
            w = max(170, 10 * len(uc.name) + 30)
            placements[uc.id] = NodePlacement(
                node_id=uc.id,
                shape_id=f"shape_{uc.id}",
                x=self.col2_x,
                y=y_col2,
                width=w,
                height=70,
            )
            y_col2 += 70 + 70

        # Place Column 3: Included/Extended Use Cases and Secondary Actors
        y_col3 = self.start_y
        for uc in sub_cases:
            w = max(170, 10 * len(uc.name) + 30)
            placements[uc.id] = NodePlacement(
                node_id=uc.id,
                shape_id=f"shape_{uc.id}",
                x=self.col3_x,
                y=y_col3,
                width=w,
                height=70,
            )
            y_col3 += 70 + 70

        for act in secondary_actors:
            placements[act.id] = NodePlacement(
                node_id=act.id,
                shape_id=f"shape_{act.id}",
                x=self.col3_x + 50,
                y=y_col3,
                width=80,
                height=80,
            )
            y_col3 += 80 + self.gap_y

        return placements


# ---------------------------------------------------------
# 3. ER Diagram Layout (FK Dependency Directed Flow)
# ---------------------------------------------------------

class ERDClusterLayout:
    """Arranges Database Entities by dependency order: root tables on top/left, child tables below."""

    def __init__(self, start_x: int = 60, start_y: int = 60, gap_x: int = 70, gap_y: int = 90):
        self.start_x = start_x
        self.start_y = start_y
        self.gap_x = gap_x
        self.gap_y = gap_y

    def layout(self, state: ProjectState) -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}
        if not state.entities:
            return placements

        # Topological sorting: entities without FKs first (Layer 0), entities with FKs next
        layer0: list[EntityNode] = []
        layer1: list[EntityNode] = []
        layer_junction: list[EntityNode] = []

        for ent in state.entities.values():
            fk_count = sum(1 for c in ent.columns if c.is_fk)
            if fk_count >= 2:
                layer_junction.append(ent)  # Many-to-Many junction table
            elif fk_count == 1:
                layer1.append(ent)          # Dependent child table
            else:
                layer0.append(ent)          # Independent parent table

        layers = [layer0, layer1, layer_junction]
        curr_y = self.start_y

        for lyr in layers:
            if not lyr:
                continue
            curr_x = self.start_x
            max_h = 80
            for ent in lyr:
                w, h = BoundingBoxCalculator.calculate_entity_dimension(ent)
                max_h = max(max_h, h)
                placements[ent.id] = NodePlacement(
                    node_id=ent.id,
                    shape_id=f"shape_{ent.id}",
                    x=curr_x,
                    y=curr_y,
                    width=w,
                    height=h,
                )
                curr_x += w + self.gap_x
            curr_y += max_h + self.gap_y

        return placements


# ---------------------------------------------------------
# 4. State Machine Diagram Layout (Horizontal Pipeline)
# ---------------------------------------------------------

class StateMachineFlowLayout:
    """Arranges states horizontally along the lifecycle pipeline with loopback offsets."""

    def __init__(self, start_x: int = 60, start_y: int = 150, gap_x: int = 150):
        self.start_x = start_x
        self.start_y = start_y
        self.gap_x = gap_x

    def layout(self, state: ProjectState) -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}
        if not state.states:
            return placements

        # Order: Initial -> intermediate states ordered by transition flow -> Final
        initial_states = [s for s in state.states.values() if s.type == "Initial"]
        final_states = [s for s in state.states.values() if s.type == "Final"]
        normal_states = [s for s in state.states.values() if s.type not in ("Initial", "Final")]

        # Sort intermediate states by transition chain
        ordered_states: list[StateNode] = []
        visited = set()

        curr_targets = [s.id for s in initial_states]
        while curr_targets:
            next_targets = []
            for tid in curr_targets:
                for tr in state.transitions:
                    if tr.source_id == tid and tr.target_id not in visited:
                        t_node = state.states.get(tr.target_id)
                        if t_node and t_node.type not in ("Initial", "Final"):
                            ordered_states.append(t_node)
                            visited.add(t_node.id)
                            next_targets.append(t_node.id)
            curr_targets = next_targets

        for s in normal_states:
            if s.id not in visited:
                ordered_states.append(s)

        full_pipeline = initial_states + ordered_states + final_states
        curr_x = self.start_x

        for st in full_pipeline:
            w = 28 if st.type in ("Initial", "Final") else max(140, 12 * len(st.name) + 20)
            h = 28 if st.type in ("Initial", "Final") else 60
            y_offset = (60 - h) // 2

            placements[st.id] = NodePlacement(
                node_id=st.id,
                shape_id=f"shape_{st.id}",
                x=curr_x,
                y=self.start_y + y_offset,
                width=w,
                height=h,
            )
            curr_x += w + self.gap_x

        return placements


# ---------------------------------------------------------
# Waypoint & Edge Routing Engine
# ---------------------------------------------------------

class WaypointRoutingEngine:
    """Calculates clean connection boundary points and loopback offsets for connectors."""

    @staticmethod
    def calculate_waypoints(
        src: NodePlacement,
        tgt: NodePlacement,
        is_loopback: bool = False,
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        """Calculate start and end boundary connection points between two shapes."""
        # Loopback transition: route over the top
        if is_loopback:
            wp1 = (src.center_x, src.y)
            wp2 = (tgt.center_x, tgt.y)
            return wp1, wp2

        # Horizontal alignment (left-to-right flow)
        if tgt.x >= src.x + src.width:
            wp1 = (src.x + src.width, src.center_y)
            wp2 = (tgt.x, tgt.center_y)
            return wp1, wp2

        # Right-to-left flow
        if src.x >= tgt.x + tgt.width:
            wp1 = (src.x, src.center_y)
            wp2 = (tgt.x + tgt.width, tgt.center_y)
            return wp1, wp2

        # Vertical alignment (bottom-to-top, e.g. Generalization)
        if src.y >= tgt.y + tgt.height:
            wp1 = (src.center_x, src.y)
            wp2 = (tgt.center_x, tgt.y + tgt.height)
            return wp1, wp2

        # Top-to-bottom
        if tgt.y >= src.y + src.height:
            wp1 = (src.center_x, src.y + src.height)
            wp2 = (tgt.center_x, tgt.y)
            return wp1, wp2

        # Default fallback
        return (src.center_x, src.center_y), (tgt.center_x, tgt.center_y)
