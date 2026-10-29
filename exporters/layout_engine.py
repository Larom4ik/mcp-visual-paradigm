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
try:
    from core.models import (
        ActivityNode,
        ActivityPartitionNode,
        ActorNode,
        ArtifactNode,
        BaseNode,
        ClassNode,
        DeployNode,
        EntityNode,
        PackageNode,
        RelationModel,
        StateNode,
        UseCaseNode,
    )
    from core.state import ProjectState
except ImportError:
    from ..core.models import (
        ActivityNode,
        ActivityPartitionNode,
        ActorNode,
        ArtifactNode,
        BaseNode,
        ClassNode,
        DeployNode,
        EntityNode,
        PackageNode,
        RelationModel,
        StateNode,
        UseCaseNode,
    )
    from ..core.state import ProjectState


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
        """Compute shape dimensions based on class name, attributes, and full method signatures."""
        attr_count = len(getattr(node, "attributes", []))
        method_count = len(getattr(node, "methods", []))

        lines: list[str] = [getattr(node, "name", "")]
        if getattr(node, "element_type", "") == "Interface":
            lines.append("«Interface»")
        for attr in getattr(node, "attributes", []):
            lines.append(f"+ {attr.name}: {attr.type}")
        for m in getattr(node, "methods", []):
            param_str = ", ".join(f"{p.name}: {p.type}" for p in getattr(m, "params", []))
            lines.append(f"+ {m.name}({param_str}): {getattr(m, 'return_type', 'void')}")

        max_len = max(len(line) for line in lines) if lines else 10
        calc_width = max(200, int(max_len * 8.5) + 36)
        calc_height = max(80, 42 + 20 * attr_count + 20 * method_count)
        return calc_width, calc_height

    @staticmethod
    def calculate_entity_dimension(node: EntityNode) -> tuple[int, int]:
        """Compute shape dimensions for ERD entities based on column names, data types, lengths, and constraints."""
        col_count = len(getattr(node, "columns", []))
        lines: list[str] = [getattr(node, "name", "")]
        for col in getattr(node, "columns", []):
            type_str = col.type
            if getattr(col, "length", None):
                type_str += f"({col.length})"
            pk_suffix = " [PK]" if getattr(col, "is_pk", False) else ""
            fk_suffix = " [FK]" if getattr(col, "is_fk", False) else ""
            lines.append(f"+ {col.name}: {type_str}{pk_suffix}{fk_suffix}")

        max_len = max(len(line) for line in lines) if lines else 10
        calc_width = max(220, int(max_len * 8.8) + 40)
        calc_height = max(90, 48 + 20 * col_count)
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
    """Places classes in distinct vertical layers based on inheritance and containment hierarchy,
    with 2D multi-row grid wrapping for packages."""

    def __init__(
        self,
        start_x: int = 60,
        start_y: int = 60,
        gap_x: int = 60,
        gap_y: int = 100,
        max_packages_per_row: int = 2,
        max_row_width: int = 2400,
    ):
        self.start_x = start_x
        self.start_y = start_y
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.max_packages_per_row = max_packages_per_row
        self.max_row_width = max_row_width

    def _layout_package_subtree(
        self, pkg_id: str, state: ProjectState
    ) -> tuple[dict[str, NodePlacement], int, int]:
        """Recursively computes local placements (relative to 0,0) and bounding dimensions (w, h) for a package."""
        pkg = state.packages[pkg_id]
        local_placements: dict[str, NodePlacement] = {}

        # 1. Layout direct classes inside this package
        pkg_classes = [state.classes[cid] for cid in pkg.class_ids if cid in state.classes]
        classes_max_x = 0
        classes_max_y = 0

        if pkg_classes:
            cols = max(2, int(math.ceil(math.sqrt(len(pkg_classes))))) if len(pkg_classes) > 1 else 1
            num_rows = int(math.ceil(len(pkg_classes) / cols))
            dims = [BoundingBoxCalculator.calculate_class_dimension(c) for c in pkg_classes]

            col_widths = [0] * cols
            row_heights = [0] * num_rows
            for i, (w, h) in enumerate(dims):
                c = i % cols
                r = i // cols
                col_widths[c] = max(col_widths[c], w)
                row_heights[r] = max(row_heights[r], h)

            start_cls_x = BoundingBoxCalculator.PADDING_X
            start_cls_y = BoundingBoxCalculator.HEADER_OFFSET + BoundingBoxCalculator.PADDING_Y

            col_offsets = [0] * cols
            acc_x = start_cls_x
            for c in range(cols):
                col_offsets[c] = acc_x
                acc_x += col_widths[c] + 40

            row_offsets = [0] * num_rows
            acc_y = start_cls_y
            for r in range(num_rows):
                row_offsets[r] = acc_y
                acc_y += row_heights[r] + 30

            for i, cls_node in enumerate(pkg_classes):
                col = i % cols
                row = i // cols
                w, h = dims[i]
                pos_x = col_offsets[col]
                pos_y = row_offsets[row]

                local_placements[cls_node.id] = NodePlacement(
                    node_id=cls_node.id,
                    shape_id=f"shape_{cls_node.id}",
                    x=pos_x,
                    y=pos_y,
                    width=w,
                    height=h,
                    parent_shape_id=f"shape_{pkg.id}",
                )
                classes_max_x = max(classes_max_x, pos_x + w)
                classes_max_y = max(classes_max_y, pos_y + h)
        else:
            classes_max_y = BoundingBoxCalculator.HEADER_OFFSET

        # 2. Layout nested child packages recursively
        child_pkgs = [state.packages[pid] for pid in pkg.child_package_ids if pid in state.packages]
        if child_pkgs:
            sub_start_y = (classes_max_y + 40) if pkg_classes else (BoundingBoxCalculator.HEADER_OFFSET + BoundingBoxCalculator.PADDING_Y)
            sub_col_x = BoundingBoxCalculator.PADDING_X
            sub_row_y = sub_start_y
            sub_row_max_h = 0
            sub_cols = 2 if len(child_pkgs) >= 2 else 1
            sub_col_idx = 0

            for cpkg in child_pkgs:
                c_placements, cw, ch = self._layout_package_subtree(cpkg.id, state)
                if sub_col_idx >= sub_cols and sub_col_idx > 0:
                    sub_col_x = BoundingBoxCalculator.PADDING_X
                    sub_row_y += sub_row_max_h + 40
                    sub_row_max_h = 0
                    sub_col_idx = 0

                # Shift child package placements by (sub_col_x, sub_row_y)
                for nid, p in c_placements.items():
                    p.x += sub_col_x
                    p.y += sub_row_y
                    local_placements[nid] = p

                sub_row_max_h = max(sub_row_max_h, ch)
                sub_col_x += cw + 40
                sub_col_idx += 1

        # 3. Calculate bounding box of this package
        if local_placements:
            min_x = min(p.x for p in local_placements.values())
            min_y = min(p.y for p in local_placements.values())
            max_x = max(p.x + p.width for p in local_placements.values())
            max_y = max(p.y + p.height for p in local_placements.values())
            pw = max(240, (max_x - min_x) + 2 * BoundingBoxCalculator.PADDING_X)
            ph = max(140, (max_y - min_y) + BoundingBoxCalculator.HEADER_OFFSET + 2 * BoundingBoxCalculator.PADDING_Y)
        else:
            pw, ph = 240, 140

        parent_sid = f"shape_{pkg.parent_package_id}" if pkg.parent_package_id else None
        local_placements[pkg.id] = NodePlacement(
            node_id=pkg.id,
            shape_id=f"shape_{pkg.id}",
            x=0,
            y=0,
            width=pw,
            height=ph,
            parent_shape_id=parent_sid,
        )
        return local_placements, pw, ph

    def layout(self, state: ProjectState) -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}
        if not state.classes and not state.packages:
            return placements

        # A. Layout packages in 2D multi-row grid
        root_packages = [
            p for p in state.packages.values()
            if not p.parent_package_id or p.parent_package_id not in state.packages
        ]

        canvas_x = self.start_x
        canvas_y = self.start_y
        row_max_h = 0
        items_in_row = 0

        for rpkg in root_packages:
            r_placements, rw, rh = self._layout_package_subtree(rpkg.id, state)

            # Check if we should wrap to the next row
            if items_in_row > 0 and (items_in_row >= self.max_packages_per_row or (canvas_x + rw > self.max_row_width)):
                canvas_x = self.start_x
                canvas_y += row_max_h + self.gap_y
                row_max_h = 0
                items_in_row = 0

            # Translate all subtree nodes from local (0, 0) to (canvas_x, canvas_y)
            for nid, placement in r_placements.items():
                placement.x += canvas_x
                placement.y += canvas_y
                placements[nid] = placement

            row_max_h = max(row_max_h, rh)
            canvas_x += rw + self.gap_x
            items_in_row += 1

        # B. Layout top-level classes (not in any package) using Hierarchical DAG (Layered)
        top_classes = [
            c for c in state.classes.values()
            if not c.package_id or c.package_id not in state.packages
        ]
        if top_classes:
            base_y = (canvas_y + row_max_h + self.gap_y) if root_packages else self.start_y
            top_placements = self._layout_dag_classes(top_classes, state, base_y=base_y)
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
    """Arranges Use Case diagrams in 3 clear functional columns from left to right with dynamic spacing."""

    def __init__(self, col1_x: int = 80, col2_x: int = 340, col3_x: int = 760, start_y: int = 60, gap_y: int = 50):
        self.col1_x = col1_x
        self.col2_x = col2_x
        self.col3_x = col3_x
        self.start_y = start_y
        self.gap_y = gap_y

    @staticmethod
    def calculate_uc_dimension(name: str) -> tuple[int, int]:
        """Calculate optimal width and height for a Use Case oval so multi-line text fits neatly."""
        clean_len = len(name)
        # Cap width between 230 and 290 px so ovals don't become massive flattened bars
        w = max(230, min(290, 8 * clean_len + 30))
        # Visual Paradigm wraps text: multi-line needs proportional height
        if clean_len > 55:
            h = 90
        elif clean_len > 32:
            h = 80
        else:
            h = 65
        return w, h

    def layout(self, state: ProjectState) -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}

        # 1. Actors: Distinguish secondary/external actors from primary business actors
        primary_actors: list[ActorNode] = []
        secondary_actors: list[ActorNode] = []

        for act in state.actors.values():
            n = act.name.lower()
            if any(k in n for k in ("service", "сервис", "external", "внешн")):
                secondary_actors.append(act)
            else:
                primary_actors.append(act)

        # 2. Distinguish Core Use Cases from Sub-UseCases (Include/Extend targets)
        sub_uc_ids: set[str] = set()
        sub_to_core_map: dict[str, list[str]] = {}
        for rel in state.uc_relations:
            if rel.type in ("Include", "Extend"):
                sub_uc_ids.add(rel.target_id)
                sub_to_core_map.setdefault(rel.target_id, []).append(rel.source_id)

        # Map each core use case to the primary actors that connect to it
        uc_to_actor_ranks: dict[str, list[int]] = {}
        primary_actor_ids = {act.id: idx for idx, act in enumerate(primary_actors)}
        for rel in state.uc_relations:
            if rel.source_id in primary_actor_ids and rel.target_id in state.use_cases:
                uc_to_actor_ranks.setdefault(rel.target_id, []).append(primary_actor_ids[rel.source_id])
            elif rel.target_id in primary_actor_ids and rel.source_id in state.use_cases:
                uc_to_actor_ranks.setdefault(rel.source_id, []).append(primary_actor_ids[rel.target_id])

        # Core cases: sort primarily by connected actor vertical rank to ensure parallel horizontal connections
        uc_keys_list = list(state.use_cases.keys())

        def _core_sort_key(uc: UseCaseNode) -> tuple[float, int]:
            ranks = uc_to_actor_ranks.get(uc.id, [])
            avg_rank = (sum(ranks) / len(ranks)) if ranks else 999.0
            return (avg_rank, uc_keys_list.index(uc.id) if uc.id in uc_keys_list else 0)

        raw_core_cases = [uc for uc in state.use_cases.values() if uc.id not in sub_uc_ids]
        core_cases = sorted(raw_core_cases, key=_core_sort_key)
        core_id_to_order = {uc.id: idx for idx, uc in enumerate(core_cases)}

        # Sub cases: sort by parent core case vertical order so include/extend arrows flow horizontally
        def _sub_sort_key(uc: UseCaseNode) -> tuple[float, int]:
            parents = sub_to_core_map.get(uc.id, [])
            parent_ranks = [core_id_to_order[p] for p in parents if p in core_id_to_order]
            avg_parent_rank = (sum(parent_ranks) / len(parent_ranks)) if parent_ranks else 999.0
            return (avg_parent_rank, uc_keys_list.index(uc.id) if uc.id in uc_keys_list else 0)

        raw_sub_cases = [uc for uc in state.use_cases.values() if uc.id in sub_uc_ids]
        sub_cases = sorted(raw_sub_cases, key=_sub_sort_key)

        # Place Column 2: Core Business Use Cases
        y_col2 = self.start_y
        max_col2_w = 0
        for uc in core_cases:
            w, h = self.calculate_uc_dimension(uc.name)
            max_col2_w = max(max_col2_w, w)
            placements[uc.id] = NodePlacement(
                node_id=uc.id,
                shape_id=f"shape_{uc.id}",
                x=self.col2_x,
                y=y_col2,
                width=w,
                height=h,
            )
            y_col2 += h + self.gap_y

        total_col2_h = max(200, y_col2 - self.start_y)

        # Place Column 3: Included/Extended Sub-UseCases (placed with dynamic gap after Col 2)
        effective_col3_x = max(self.col3_x, self.col2_x + max_col2_w + 140)
        y_col3 = self.start_y
        for uc in sub_cases:
            w, h = self.calculate_uc_dimension(uc.name)
            placements[uc.id] = NodePlacement(
                node_id=uc.id,
                shape_id=f"shape_{uc.id}",
                x=effective_col3_x,
                y=y_col3,
                width=w,
                height=h,
            )
            y_col3 += h + self.gap_y

        for act in secondary_actors:
            placements[act.id] = NodePlacement(
                node_id=act.id,
                shape_id=f"shape_{act.id}",
                x=effective_col3_x + 50,
                y=y_col3,
                width=80,
                height=80,
            )
            y_col3 += 80 + self.gap_y

        # Place Column 1: Primary Actors
        # Distribute primary actors vertically to balance across the height of Core Use Cases
        num_actors = len(primary_actors)
        if num_actors == 1:
            actor_y_positions = [self.start_y + max(0, (total_col2_h - 80) // 2)]
        elif num_actors > 1:
            step = max(110, (total_col2_h - 80) // (num_actors - 1))
            actor_y_positions = [self.start_y + i * step for i in range(num_actors)]
        else:
            actor_y_positions = []

        for i, act in enumerate(primary_actors):
            placements[act.id] = NodePlacement(
                node_id=act.id,
                shape_id=f"shape_{act.id}",
                x=self.col1_x,
                y=actor_y_positions[i],
                width=80,
                height=80,
            )

        return placements


# ---------------------------------------------------------
# 3. ER Diagram Layout (FK Dependency Directed Flow)
# ---------------------------------------------------------

class ERDClusterLayout:
    """Arranges Database Entities by dependency order into a globally balanced 2D grid: root tables on top, child tables below."""

    def __init__(
        self,
        start_x: int = 60,
        start_y: int = 60,
        gap_x: int = 90,
        gap_y: int = 110,
        max_cols: Optional[int] = None,
    ):
        self.start_x = start_x
        self.start_y = start_y
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.max_cols = max_cols

    def layout(self, state: ProjectState) -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}
        if not state.entities:
            return placements

        # 1. Topological partitioning by dependency depth
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

        ordered_entities = layer0 + layer1 + layer_junction
        total_n = len(ordered_entities)

        # 2. Determine optimal column count based on total entity count
        if total_n <= 3:
            cols = total_n
        elif total_n == 4:
            cols = 2
        elif total_n in (5, 6):
            cols = 3
        elif total_n in (7, 8):
            cols = 4
        elif total_n == 9:
            cols = 3
        elif total_n in (10, 11, 12):
            cols = 4
        elif total_n in (13, 14, 15):
            cols = 5 if total_n == 15 else 4
        elif total_n == 16:
            cols = 4
        else:
            cols = max(3, min(6, int(math.ceil(math.sqrt(total_n * 1.25)))))

        if self.max_cols and cols > self.max_cols:
            cols = self.max_cols

        # 3. Calculate balanced row capacities so rows differ by at most 1 item
        num_rows = max(1, int(math.ceil(total_n / cols)))
        base_per_row = total_n // num_rows
        remainder = total_n % num_rows
        row_sizes = [base_per_row + (1 if r < remainder else 0) for r in range(num_rows)]

        row_entities: list[list[EntityNode]] = []
        idx = 0
        for sz in row_sizes:
            row_entities.append(ordered_entities[idx : idx + sz])
            idx += sz

        # 4. Place each row on the canvas, aligning dependent tables under parents
        curr_y = self.start_y
        entity_centers: dict[str, float] = {}

        for r_idx, row in enumerate(row_entities):
            if not row:
                continue

            # In rows 1+, sort entities so they sit close to their referenced parent tables
            if r_idx > 0 and entity_centers:
                def _affinity_key(ent: EntityNode) -> float:
                    parent_xs: list[float] = []
                    for rel in state.er_relations:
                        if rel.source_id == ent.id and rel.target_id in entity_centers:
                            parent_xs.append(entity_centers[rel.target_id])
                        elif rel.target_id == ent.id and rel.source_id in entity_centers:
                            parent_xs.append(entity_centers[rel.source_id])
                    if not parent_xs:
                        for c in ent.columns:
                            if c.is_fk and c.name.lower().endswith(("_id", "id")):
                                base_name = c.name.lower()[:-3] if c.name.lower().endswith("_id") else c.name.lower()[:-2]
                                for p_id, p_x in entity_centers.items():
                                    p_ent = state.entities.get(p_id)
                                    if p_ent and base_name in p_ent.name.lower():
                                        parent_xs.append(p_x)
                    return (sum(parent_xs) / len(parent_xs)) if parent_xs else 9999.0

                row = sorted(row, key=_affinity_key)

            curr_x = self.start_x
            row_max_h = 80
            for ent in row:
                w, h = BoundingBoxCalculator.calculate_entity_dimension(ent)
                row_max_h = max(row_max_h, h)
                placement = NodePlacement(
                    node_id=ent.id,
                    shape_id=f"shape_{ent.id}",
                    x=curr_x,
                    y=curr_y,
                    width=w,
                    height=h,
                )
                placements[ent.id] = placement
                entity_centers[ent.id] = curr_x + w / 2.0
                curr_x += w + self.gap_x

            curr_y += row_max_h + self.gap_y

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
            if st.type in ("Initial", "Final"):
                w = 28
                h = 28
            else:
                lines = [st.name]
                if getattr(st, "entry_action", ""):
                    lines.append(f"entry / {st.entry_action}")
                if getattr(st, "do_activity", ""):
                    lines.append(f"do / {st.do_activity}")
                if getattr(st, "exit_action", ""):
                    lines.append(f"exit / {st.exit_action}")
                max_len = max(len(line) for line in lines)
                w = max(150, int(max_len * 8.5) + 36)
                behavior_count = len(lines) - 1
                h = max(60, 42 + 20 * behavior_count)

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
# 5. Activity Diagram Flow & Swimlane Layout Engine
# ---------------------------------------------------------

class ActivityFlowLayout:
    """Calculates top-to-bottom DAG execution flow with Decision/Fork branching and Swimlanes."""

    def __init__(self, start_x: int = 350, start_y: int = 60, gap_y: int = 60, col_gap_x: int = 80) -> None:
        self.start_x = start_x
        self.start_y = start_y
        self.gap_y = gap_y
        self.col_gap_x = col_gap_x

    def layout(self, state: "ProjectState") -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}
        if not state.activity_nodes:
            return placements

        # Check if partitions (swimlanes) are defined
        if state.activity_partitions:
            lane_x = self.start_x
            lane_width = 320
            header_h = 36

            for part_id, part in state.activity_partitions.items():
                lane_nodes = [
                    state.activity_nodes[nid]
                    for nid in part.activity_node_ids
                    if nid in state.activity_nodes
                ]
                for n in state.activity_nodes.values():
                    if n.partition_id == part_id and n not in lane_nodes:
                        lane_nodes.append(n)

                curr_y = self.start_y + header_h + 30
                for node in lane_nodes:
                    w, h = self._calculate_node_dimension(node)
                    x = lane_x + (lane_width - w) // 2
                    placements[node.id] = NodePlacement(
                        node_id=node.id,
                        shape_id=f"shape_{node.id}",
                        x=x,
                        y=curr_y,
                        width=w,
                        height=h,
                        parent_shape_id=f"shape_{part_id}",
                    )
                    curr_y += h + self.gap_y

                total_lane_h = max(400, curr_y - self.start_y + 40)
                placements[part_id] = NodePlacement(
                    node_id=part_id,
                    shape_id=f"shape_{part_id}",
                    x=lane_x,
                    y=self.start_y,
                    width=lane_width,
                    height=total_lane_h,
                )
                lane_x += lane_width + 15
            return placements

        # Single pipeline / directed graph flow
        initial_nodes = [n for n in state.activity_nodes.values() if n.type == "Initial"]
        final_nodes = [n for n in state.activity_nodes.values() if n.type in ("Final", "FlowFinal")]
        intermediate_nodes = [n for n in state.activity_nodes.values() if n.type not in ("Initial", "Final", "FlowFinal")]

        # Topological depth assignment
        depth_map: dict[str, int] = {}
        for init in initial_nodes:
            depth_map[init.id] = 0

        changed = True
        iterations = 0
        while changed and iterations < 50:
            changed = False
            iterations += 1
            for flow in state.activity_flows:
                if flow.source_id in depth_map:
                    new_depth = depth_map[flow.source_id] + 1
                    if flow.target_id not in depth_map or depth_map[flow.target_id] < new_depth:
                        depth_map[flow.target_id] = new_depth
                        changed = True

        for node in intermediate_nodes:
            if node.id not in depth_map:
                depth_map[node.id] = 1

        max_depth = max(depth_map.values(), default=0)
        for f in final_nodes:
            if f.id not in depth_map or depth_map[f.id] <= max_depth:
                depth_map[f.id] = max_depth + 1

        layers: dict[int, list[ActivityNode]] = {}
        for nid, depth in depth_map.items():
            node = state.activity_nodes.get(nid)
            if node:
                layers.setdefault(depth, []).append(node)

        curr_y = self.start_y
        for depth in sorted(layers.keys()):
            layer_nodes = layers[depth]
            total_layer_w = sum(self._calculate_node_dimension(n)[0] for n in layer_nodes) + (len(layer_nodes) - 1) * self.col_gap_x
            start_x = max(60, self.start_x - total_layer_w // 2)

            node_x = start_x
            max_h = 0
            for node in layer_nodes:
                w, h = self._calculate_node_dimension(node)
                placements[node.id] = NodePlacement(
                    node_id=node.id,
                    shape_id=f"shape_{node.id}",
                    x=node_x,
                    y=curr_y,
                    width=w,
                    height=h,
                )
                node_x += w + self.col_gap_x
                if h > max_h:
                    max_h = h

            curr_y += max_h + self.gap_y

        return placements

    def _calculate_node_dimension(self, node: ActivityNode) -> tuple[int, int]:
        if node.type == "Initial":
            return 24, 24
        elif node.type in ("Final", "FlowFinal"):
            return 24, 24
        elif node.type in ("Decision", "Merge"):
            return 40, 40
        elif node.type in ("Fork", "Join"):
            return 90, 8
        else:
            w = max(160, int(len(node.name) * 8.5) + 36)
            return w, 50


# ---------------------------------------------------------
# 6. Deployment Diagram Topology Layout Engine
# ---------------------------------------------------------

class DeploymentTopologyLayout:
    """Calculates tiered layout for nodes, devices, and deployed artifacts in a Deployment Diagram."""

    def __init__(self, start_x: int = 60, start_y: int = 80, tier_gap_x: int = 120, node_gap_y: int = 60) -> None:
        self.start_x = start_x
        self.start_y = start_y
        self.tier_gap_x = tier_gap_x
        self.node_gap_y = node_gap_y

    def layout(self, state: "ProjectState") -> dict[str, NodePlacement]:
        placements: dict[str, NodePlacement] = {}
        if not state.deployment_nodes:
            return placements

        # Categorize nodes into 4 architectural tiers:
        # 0: Client / Edge
        # 1: Reverse Proxy / Gateway
        # 2: Application / Services
        # 3: Database / Storage
        tiers: dict[int, list[DeployNode]] = {0: [], 1: [], 2: [], 3: []}

        for node in state.deployment_nodes.values():
            name_lower = node.name.lower()
            if any(k in name_lower for k in ("client", "browser", "mobile", "frontend", "desktop", "user pc")):
                tiers[0].append(node)
            elif any(k in name_lower for k in ("gateway", "proxy", "nginx", "balancer", "ingress", "edge", "router")):
                tiers[1].append(node)
            elif any(k in name_lower for k in ("db", "database", "postgres", "sql", "mysql", "redis", "mongo", "storage", "s3", "kafka")):
                tiers[3].append(node)
            else:
                tiers[2].append(node)

        curr_x = self.start_x
        active_tiers = [t for t in sorted(tiers.keys()) if tiers[t]]

        for tier_idx in active_tiers:
            nodes_in_tier = tiers[tier_idx]
            curr_y = self.start_y
            max_tier_w = 320

            for node in nodes_in_tier:
                # Find artifacts deployed on this node
                node_artifacts = [
                    art for art in state.deployment_artifacts.values()
                    if art.deployed_on_node_id == node.id or art.id in node.deployed_artifact_ids
                ]

                node_w = max(300, max((len(a.name) * 8 + 40 for a in node_artifacts), default=280))
                if len(node.name) * 9 > node_w:
                    node_w = int(len(node.name) * 9) + 40

                node_h = max(200, 90 + len(node_artifacts) * 55)

                placements[node.id] = NodePlacement(
                    node_id=node.id,
                    shape_id=f"shape_{node.id}",
                    x=curr_x,
                    y=curr_y,
                    width=node_w,
                    height=node_h,
                )

                # Place deployed artifacts visually inside the node
                art_y = curr_y + 55
                for art in node_artifacts:
                    art_w = max(180, int(len(art.name) * 8.5) + 30)
                    art_h = 42
                    art_x = curr_x + (node_w - art_w) // 2
                    placements[art.id] = NodePlacement(
                        node_id=art.id,
                        shape_id=f"shape_{art.id}",
                        x=art_x,
                        y=art_y,
                        width=art_w,
                        height=art_h,
                        parent_shape_id=f"shape_{node.id}",
                    )
                    art_y += art_h + 12

                curr_y += node_h + self.node_gap_y
                if node_w > max_tier_w:
                    max_tier_w = node_w

            curr_x += max_tier_w + self.tier_gap_x

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
