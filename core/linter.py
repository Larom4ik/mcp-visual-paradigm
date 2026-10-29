"""Architectural Linter and Diagnostic Engine for UML and ERD diagrams in Visual Paradigm."""

from dataclasses import dataclass, field
from typing import Any, List, Optional
try:
    from core.sanitizer import (
        sanitize_activity_flow,
        sanitize_class_relation,
        sanitize_deployment_relation,
        sanitize_use_case_relation,
    )
except ImportError:
    from .sanitizer import (
        sanitize_activity_flow,
        sanitize_class_relation,
        sanitize_deployment_relation,
        sanitize_use_case_relation,
    )


@dataclass
class LintIssue:
    code: str
    severity: str  # "ERROR", "WARNING", "INFO"
    diagram_type: str
    element: str
    message: str
    auto_fixed: bool = False
    fix_description: str = ""


@dataclass
class LintReport:
    issues: List[LintIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "ERROR" and not i.auto_fixed for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR" and not i.auto_fixed)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING" and not i.auto_fixed)

    @property
    def fixed_count(self) -> int:
        return sum(1 for i in self.issues if i.auto_fixed)

    def format_report(self) -> str:
        lines = ["=== Architectural Quality & Lint Report ==="]
        if not self.issues:
            lines.append("No architectural issues detected. Diagrams conform to canonical UML/ERD standards.")
            return "\n".join(lines)

        lines.append(
            f"Summary: Errors: {self.error_count} | Warnings: {self.warning_count} | Auto-Repaired: {self.fixed_count}\n"
        )
        for issue in self.issues:
            status = "[AUTO-REPAIRED]" if issue.auto_fixed else f"[{issue.severity}]"
            fix_str = f" -> {issue.fix_description}" if issue.fix_description else ""
            lines.append(f"{status} {issue.code} ({issue.diagram_type}) on '{issue.element}': {issue.message}{fix_str}")

        return "\n".join(lines)


class ArchitectureLinter:
    """Diagnoses and auto-repairs architectural defects, anti-patterns, and topology flaws."""

    def __init__(self, state: Any) -> None:
        self.state = state

    def lint(self, auto_fix: bool = True) -> LintReport:
        report = LintReport()

        self._lint_activity_diagram(report, auto_fix)
        self._lint_class_diagram(report, auto_fix)
        self._lint_use_case_diagram(report, auto_fix)
        self._lint_deployment_diagram(report, auto_fix)
        self._lint_erd_diagram(report, auto_fix)

        return report

    def _lint_activity_diagram(self, report: LintReport, auto_fix: bool) -> None:
        nodes = self.state.activity_nodes
        flows = self.state.activity_flows
        if not nodes:
            return

        # 1. Initial Node check
        initial_nodes = [n for n in nodes.values() if n.type == "Initial"]
        if not initial_nodes:
            issue = LintIssue(
                code="ACT-001",
                severity="WARNING",
                diagram_type="ActivityDiagram",
                element="Activity",
                message="Workflow is missing an InitialNode.",
            )
            if auto_fix:
                try:
                    from core.models import ActivityNode, ActivityFlow
                    init_node = ActivityNode(name="Start", type="Initial")
                    self.state.add_node(init_node)
                    # Connect to first non-initial action if exists
                    actions = [n for n in nodes.values() if n.type == "Action"]
                    if actions:
                        flow = ActivityFlow(source_id=init_node.id, target_id=actions[0].id, type="ControlFlow")
                        self.state.add_relation(flow)
                    issue.auto_fixed = True
                    issue.fix_description = f"Created InitialNode '{init_node.name}' (ID: {init_node.id})."
                except Exception:
                    pass
            report.issues.append(issue)

        # 2. Final Node check
        final_nodes = [n for n in nodes.values() if n.type in ("Final", "FlowFinal")]
        if not final_nodes:
            issue = LintIssue(
                code="ACT-002",
                severity="WARNING",
                diagram_type="ActivityDiagram",
                element="Activity",
                message="Workflow is missing an ActivityFinalNode or FlowFinalNode.",
            )
            if auto_fix:
                try:
                    from core.models import ActivityNode, ActivityFlow
                    final_node = ActivityNode(name="End", type="Final")
                    self.state.add_node(final_node)
                    # Find actions with no outgoing flows
                    sources = {f.source_id for f in self.state.activity_flows}
                    dangling_actions = [n for n in nodes.values() if n.type == "Action" and n.id not in sources]
                    for d_act in dangling_actions:
                        flow = ActivityFlow(source_id=d_act.id, target_id=final_node.id, type="ControlFlow")
                        self.state.add_relation(flow)
                    issue.auto_fixed = True
                    issue.fix_description = f"Created ActivityFinalNode '{final_node.name}' (ID: {final_node.id}) and connected dangling flows."
                except Exception:
                    pass
            report.issues.append(issue)

        # 3. Decision Node branches and guard conditions
        for node in nodes.values():
            if node.type == "Decision":
                outgoing = [f for f in flows if f.source_id == node.id]
                if len(outgoing) < 2:
                    report.issues.append(
                        LintIssue(
                            code="ACT-004",
                            severity="WARNING",
                            diagram_type="ActivityDiagram",
                            element=node.name,
                            message=f"DecisionNode '{node.name}' has only {len(outgoing)} outgoing branch; should have at least 2 alternate branches.",
                        )
                    )
                for f in outgoing:
                    g = getattr(f, "guard", "") or getattr(f, "guard_condition", "")
                    if not g:
                        issue = LintIssue(
                            code="ACT-005",
                            severity="WARNING",
                            diagram_type="ActivityDiagram",
                            element=f.id,
                            message=f"Outgoing branch from Decision '{node.name}' is missing a guard condition [condition].",
                        )
                        if auto_fix:
                            f.guard = "[else]"
                            f.guard_condition = "[else]"
                            issue.auto_fixed = True
                            issue.fix_description = "Defaulted guard condition to '[else]'."
                        report.issues.append(issue)
                    elif not (g.startswith("[") and g.endswith("]")):
                        if auto_fix:
                            f.guard = f"[{g.strip()}]"
                            f.guard_condition = f.guard
                            report.issues.append(
                                LintIssue(
                                    code="ACT-005",
                                    severity="INFO",
                                    diagram_type="ActivityDiagram",
                                    element=f.id,
                                    message=f"Guard '{g}' was normalized to '[{g.strip()}]'.",
                                    auto_fixed=True,
                                    fix_description="Formatted brackets around guard condition.",
                                )
                            )

        # 4. Swimlane assignment
        if self.state.activity_partitions:
            first_part_id = next(iter(self.state.activity_partitions.keys()))
            for node in nodes.values():
                if node.type in ("Action", "Decision") and not node.partition_id:
                    issue = LintIssue(
                        code="ACT-006",
                        severity="WARNING",
                        diagram_type="ActivityDiagram",
                        element=node.name,
                        message=f"Action '{node.name}' is not assigned to any Swimlane / Partition.",
                    )
                    if auto_fix:
                        node.partition_id = first_part_id
                        self.state.activity_partitions[first_part_id].activity_node_ids.append(node.id)
                        issue.auto_fixed = True
                        issue.fix_description = f"Assigned to Swimlane '{self.state.activity_partitions[first_part_id].name}'."
                    report.issues.append(issue)

        # 5. Sanitize all flow labels
        for f in flows:
            src_node = self.state.find_activity_node(f.source_id)
            src_type = src_node.type if src_node else "Action"
            c_name, c_guard = sanitize_activity_flow(
                source_type=src_type,
                flow_type=f.type,
                name=f.name,
                guard=getattr(f, "guard", ""),
            )
            if f.name != c_name or getattr(f, "guard", "") != c_guard:
                f.name = c_name
                f.guard = c_guard
                f.guard_condition = c_guard

    def _lint_class_diagram(self, report: LintReport, auto_fix: bool) -> None:
        classes = self.state.classes
        relations = self.state.class_relations
        if not classes:
            return

        # 1. God Class Anti-Pattern check
        for c in classes.values():
            direct_conns = sum(1 for r in relations if r.source_id == c.id or r.target_id == c.id)
            if direct_conns >= 10:
                report.issues.append(
                    LintIssue(
                        code="CLS-001",
                        severity="WARNING",
                        diagram_type="ClassDiagram",
                        element=c.name,
                        message=f"Class '{c.name}' participates in {direct_conns} relations (God Object anti-pattern). Consider extracting interfaces or subpackages.",
                    )
                )

        # 2. Composition and Aggregation multiplicities & clean labels
        for r in relations:
            c_name, s_m, t_m = sanitize_class_relation(
                rel_type=r.type,
                name=r.name,
                source_mult=r.source_multiplicity,
                target_mult=r.target_multiplicity,
            )
            if r.type == "Composition" and (not r.source_multiplicity or not r.target_multiplicity):
                issue = LintIssue(
                    code="CLS-002",
                    severity="WARNING",
                    diagram_type="ClassDiagram",
                    element=f"{r.source_id}->{r.target_id}",
                    message="Composition relation missing explicit multiplicities.",
                )
                if auto_fix:
                    r.source_multiplicity = s_m
                    r.target_multiplicity = t_m
                    r.name = ""
                    issue.auto_fixed = True
                    issue.fix_description = f"Set multiplicities to '{s_m}' -> '{t_m}' and cleared label."
                report.issues.append(issue)
            else:
                # Apply sanitized label
                r.name = c_name
                r.source_multiplicity = s_m
                r.target_multiplicity = t_m

    def _lint_use_case_diagram(self, report: LintReport, auto_fix: bool) -> None:
        actors = self.state.actors
        use_cases = self.state.use_cases
        relations = self.state.uc_relations
        if not use_cases and not actors:
            return

        for r in relations:
            src_actor = self.state.find_actor(r.source_id)
            tgt_actor = self.state.find_actor(r.target_id)

            # Actor to Actor association is invalid
            if src_actor and tgt_actor and r.type in ("Association", "Include", "Extend"):
                report.issues.append(
                    LintIssue(
                        code="UC-001",
                        severity="ERROR",
                        diagram_type="UseCaseDiagram",
                        element=f"{src_actor.name} <-> {tgt_actor.name}",
                        message=f"Direct '{r.type}' connection between Actors '{src_actor.name}' and '{tgt_actor.name}' is invalid in UML. Use Generalization if inheritance is intended.",
                    )
                )

            # Actor with Include/Extend
            if (src_actor or tgt_actor) and r.type in ("Include", "Extend"):
                actor_name = src_actor.name if src_actor else tgt_actor.name
                report.issues.append(
                    LintIssue(
                        code="UC-002",
                        severity="ERROR",
                        diagram_type="UseCaseDiagram",
                        element=actor_name,
                        message=f"Actor '{actor_name}' cannot participate in '{r.type}' relationship (valid only between Use Cases).",
                    )
                )

            # Sanitize labels: Actor-to-UC lines are always clean unnamed lines
            r.name = sanitize_use_case_relation(r.type, r.name)

        # Isolated use cases check
        connected_ucs = {r.source_id for r in relations} | {r.target_id for r in relations}
        for uc in use_cases.values():
            if uc.id not in connected_ucs:
                report.issues.append(
                    LintIssue(
                        code="UC-003",
                        severity="WARNING",
                        diagram_type="UseCaseDiagram",
                        element=uc.name,
                        message=f"UseCase '{uc.name}' is isolated and has no connections to any Actor or Include/Extend relations.",
                    )
                )

    def _lint_deployment_diagram(self, report: LintReport, auto_fix: bool) -> None:
        nodes = self.state.deployment_nodes
        artifacts = self.state.deployment_artifacts
        relations = self.state.deployment_relations
        if not nodes and not artifacts:
            return

        # 1. Floating artifacts
        for art in artifacts.values():
            if not art.deployed_on_node_id or art.deployed_on_node_id not in nodes:
                issue = LintIssue(
                    code="DEP-001",
                    severity="WARNING",
                    diagram_type="DeploymentDiagram",
                    element=art.name,
                    message=f"Artifact '{art.name}' is not deployed on any host node or execution environment.",
                )
                if auto_fix and nodes:
                    first_node = next(iter(nodes.values()))
                    art.deployed_on_node_id = first_node.id
                    if art.id not in first_node.deployed_artifact_ids:
                        first_node.deployed_artifact_ids.append(art.id)
                    issue.auto_fixed = True
                    issue.fix_description = f"Assigned deployment to host node '{first_node.name}'."
                report.issues.append(issue)

        # 2. Sanitize communication paths and protocol labels
        for r in relations:
            c_name, c_proto = sanitize_deployment_relation(r.type, r.name, getattr(r, "protocol", ""))
            r.name = c_name
            r.protocol = c_proto

    def _lint_erd_diagram(self, report: LintReport, auto_fix: bool) -> None:
        entities = self.state.entities
        relations = self.state.er_relations
        if not entities:
            return

        for ent in entities.values():
            pk_cols = [c for c in ent.columns if c.is_primary_key]
            if not pk_cols:
                report.issues.append(
                    LintIssue(
                        code="ERD-001",
                        severity="WARNING",
                        diagram_type="ERDiagram",
                        element=ent.name,
                        message=f"Entity '{ent.name}' has no Primary Key defined.",
                    )
                )
            for c in pk_cols:
                if getattr(c, "is_unique", False):
                    issue = LintIssue(
                        code="ERD-002",
                        severity="INFO",
                        diagram_type="ERDiagram",
                        element=f"{ent.name}.{c.name}",
                        message=f"Primary key column '{c.name}' has redundant is_unique=True.",
                    )
                    if auto_fix:
                        c.is_unique = False
                        issue.auto_fixed = True
                        issue.fix_description = "Removed redundant unique flag to keep [PK] clean."
                    report.issues.append(issue)
