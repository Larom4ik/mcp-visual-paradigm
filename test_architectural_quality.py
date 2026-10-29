"""Test suite for the 4-Level Architectural Quality System, Linter, and Blueprints."""

import os
import unittest
import xml.etree.ElementTree as ET

from core.blueprints import get_architecture_blueprint
from core.linter import ArchitectureLinter, LintIssue, LintReport
from core.models import (
    ActivityFlow,
    ActivityNode,
    ActivityPartitionNode,
    ActorNode,
    ArtifactNode,
    ClassNode,
    ClassRelation,
    ColumnModel,
    DeployNode,
    DeploymentRelation,
    EntityNode,
    ERRelation,
    UCRelation,
    UseCaseNode,
)
from core.sanitizer import (
    is_stop_word_label,
    sanitize_activity_flow,
    sanitize_class_relation,
    sanitize_deployment_relation,
    sanitize_use_case_relation,
)
from core.state import ProjectState
from exporters.xmi_builder import XMIBuilder, export_to_xmi


class TestLabelSanitizer(unittest.TestCase):
    """Unit tests for Level 1 label sanitization and clutter reduction."""

    def test_is_stop_word_label(self):
        self.assertTrue(is_stop_word_label("has"))
        self.assertTrue(is_stop_word_label("contains"))
        self.assertTrue(is_stop_word_label("MANAGES"))
        self.assertTrue(is_stop_word_label("содержит"))
        self.assertTrue(is_stop_word_label("имеет"))
        self.assertTrue(is_stop_word_label("Composition"))
        self.assertTrue(is_stop_word_label("Aggregation"))
        self.assertFalse(is_stop_word_label("orders_placed"))
        self.assertTrue(is_stop_word_label(""))

    def test_sanitize_class_relation(self):
        # Fluff verb on Composition should be stripped and multiplicities ensured
        label, s_mult, t_mult = sanitize_class_relation("Composition", "contains")
        self.assertEqual(label, "")
        self.assertEqual(s_mult, "1")
        self.assertEqual(t_mult, "1..*")

        # Default type as label should be stripped
        label, s_mult, t_mult = sanitize_class_relation("Association", "Association")
        self.assertEqual(label, "")

        # Meaningful semantic role name should be preserved
        label, s_mult, t_mult = sanitize_class_relation("Association", "assignedSupervisor")
        self.assertEqual(label, "assignedSupervisor")

    def test_sanitize_use_case_relation(self):
        # Fluff verb on UC Association stripped
        label = sanitize_use_case_relation("Association", "triggers")
        self.assertEqual(label, "")

        # Include and Extend stereotypes normalized
        label = sanitize_use_case_relation("Include", "include")
        self.assertEqual(label, "«Include»")

        label = sanitize_use_case_relation("Extend", "")
        self.assertEqual(label, "«Extend»")

    def test_sanitize_activity_flow(self):
        # Guard without brackets is bracketed for Decision output
        name, guard = sanitize_activity_flow("Decision", "ControlFlow", "flow1", "valid")
        self.assertEqual(guard, "[valid]")

        # Guard already bracketed remains intact
        name, guard = sanitize_activity_flow("Action", "ControlFlow", "", "[approved]")
        self.assertEqual(guard, "[approved]")

        # Fluff flow name stripped
        name, guard = sanitize_activity_flow("Action", "ControlFlow", "processes", "")
        self.assertEqual(name, "")

    def test_sanitize_deployment_relation(self):
        # Protocol with port normalized
        name, proto = sanitize_deployment_relation("CommunicationPath", "manages", "https")
        self.assertEqual(proto, "HTTPS (Port 443)")

        # Deployment dependency has deploy stereotype
        name, proto = sanitize_deployment_relation("Deployment", "", "")
        self.assertEqual(name, "«deploy»")


class TestArchitectureLinter(unittest.TestCase):
    """Unit tests for Level 2 Architecture Linter rules and auto-repair."""

    def setUp(self):
        self.state = ProjectState("TestArchitecturalLinter")
        self.state.clear("TestArchitecturalLinter")

    def test_activity_linter_initial_and_final_auto_fix(self):
        # Add actions without initial or final nodes
        a1 = ActivityNode(id="act_1", name="Submit Order", type="Action")
        a2 = ActivityNode(id="act_2", name="Validate Payment", type="Action")
        self.state.add_node(a1)
        self.state.add_node(a2)
        self.state.add_relation(ActivityFlow(id="fl_1", source_id="act_1", target_id="act_2"))

        # Lint without auto_fix
        linter = ArchitectureLinter(self.state)
        report = linter.lint(auto_fix=False)

        codes = [i.code for i in report.issues]
        self.assertIn("ACT-001", codes)  # Missing InitialNode
        self.assertIn("ACT-002", codes)  # Missing FinalNode

        # Lint with auto_fix
        report_fixed = linter.lint(auto_fix=True)
        fixed_codes = [i.code for i in report_fixed.issues if i.auto_fixed]
        self.assertIn("ACT-001", fixed_codes)
        self.assertIn("ACT-002", fixed_codes)

        # Check that InitialNode and ActivityFinalNode exist in state
        types = [n.type for n in self.state.activity_nodes.values()]
        self.assertIn("Initial", types)
        self.assertIn("Final", types)

    def test_activity_guard_unbracketed_auto_fix(self):
        d1 = ActivityNode(id="dec_1", name="Is Valid?", type="Decision")
        a1 = ActivityNode(id="act_success", name="Process", type="Action")
        a2 = ActivityNode(id="act_fail", name="Reject", type="Action")
        self.state.add_node(d1)
        self.state.add_node(a1)
        self.state.add_node(a2)

        flow1 = ActivityFlow(id="fl_1", source_id="dec_1", target_id="act_success", guard="valid")
        flow2 = ActivityFlow(id="fl_2", source_id="dec_1", target_id="act_fail", guard="invalid")
        self.state.add_relation(flow1)
        self.state.add_relation(flow2)

        linter = ArchitectureLinter(self.state)
        report = linter.lint(auto_fix=True)

        fixed_codes = [i.code for i in report.issues if i.auto_fixed]
        self.assertIn("ACT-005", fixed_codes)
        self.assertEqual(flow1.guard, "[valid]")
        self.assertEqual(flow2.guard, "[invalid]")

    def test_class_cycle_inheritance(self):
        c1 = ClassNode(id="cls_1", name="ServiceA")
        c2 = ClassNode(id="cls_2", name="ServiceB")
        self.state.add_node(c1)
        self.state.add_node(c2)

        self.state.add_relation(ClassRelation(id="r1", source_id="cls_1", target_id="cls_2", type="Generalization"))
        with self.assertRaises(Exception):
            ClassRelation(id="r2", source_id="cls_2", target_id="cls_1", type="Generalization")

    def test_use_case_actor_to_actor_error(self):
        a1 = ActorNode(id="act_1", name="Customer")
        a2 = ActorNode(id="act_2", name="Admin")
        self.state.add_node(a1)
        self.state.add_node(a2)

        # Actor to Actor association is invalid in UML
        self.state.add_relation(UCRelation(id="ucr_1", source_id="act_1", target_id="act_2", type="Association"))

        linter = ArchitectureLinter(self.state)
        report = linter.lint(auto_fix=False)
        codes = [i.code for i in report.issues]
        self.assertIn("UC-001", codes)

    def test_deployment_floating_artifact(self):
        art = ArtifactNode(id="art_1", name="order-service.jar", deployed_on_node_id=None)
        self.state.add_node(art)

        linter = ArchitectureLinter(self.state)
        report = linter.lint(auto_fix=False)
        codes = [i.code for i in report.issues]
        self.assertIn("DEP-001", codes)

    def test_erd_missing_primary_key(self):
        ent = EntityNode(id="ent_orders", name="orders")
        ent.columns.append(ColumnModel(name="total_price", type="DECIMAL(10,2)"))
        self.state.add_node(ent)

        linter = ArchitectureLinter(self.state)
        report = linter.lint(auto_fix=False)
        codes = [i.code for i in report.issues]
        self.assertIn("ERD-001", codes)


class TestArchitectureBlueprints(unittest.TestCase):
    """Unit tests for Golden Blueprint templates."""

    def test_blueprints_retrieval(self):
        for dtype in ["class", "activity", "deployment", "erd", "use_case", "state"]:
            bp = get_architecture_blueprint(dtype)
            self.assertIsInstance(bp, dict)
            self.assertIn("diagram_name", bp)

    def test_unknown_blueprint_fallback(self):
        bp = get_architecture_blueprint("unknown_diagram")
        self.assertIsInstance(bp, dict)
        self.assertEqual(bp.get("diagram_name"), "Domain Model (DDD Pattern)")


class TestFullXMIExportQuality(unittest.TestCase):
    """Integration test verifying XMI builder runs linter auto-fix and outputs clean XML."""

    def test_xmi_export_with_linter_and_clean_connectors(self):
        state = ProjectState("ECommercePlatform")
        state.clear("ECommercePlatform")

        # Class with composition and fluff label
        c_order = ClassNode(id="c_order", name="Order")
        c_item = ClassNode(id="c_item", name="OrderItem")
        state.add_node(c_order)
        state.add_node(c_item)
        state.add_relation(
            ClassRelation(
                id="cr_1",
                source_id="c_order",
                target_id="c_item",
                type="Composition",
                name="contains",  # Fluff verb, must be stripped
                source_multiplicity="1",
                target_multiplicity="1..*",
            )
        )

        # Activity workflow with unbracketed guard and missing start/end
        act_part = ActivityPartitionNode(id="part_1", name="OrderService")
        state.add_node(act_part)

        act1 = ActivityNode(id="act_create", name="Create Order", type="Action", partition_id="part_1")
        act_dec = ActivityNode(id="act_dec", name="Stock Available?", type="Decision", partition_id="part_1")
        state.add_node(act1)
        state.add_node(act_dec)

        state.add_relation(ActivityFlow(id="fl_step", source_id="act_create", target_id="act_dec"))
        state.add_relation(
            ActivityFlow(
                id="fl_yes",
                source_id="act_dec",
                target_id="act_create",
                guard="yes",  # Unbracketed, linter must repair to [yes]
            )
        )

        # Export to XMI
        out_file = "e:/mcp-visual-paradigm/test_quality_output.xmi"
        if os.path.exists(out_file):
            os.remove(out_file)

        export_to_xmi(state, out_file)
        self.assertTrue(os.path.exists(out_file))

        # Parse generated XML
        tree = ET.parse(out_file)
        root = tree.getroot()

        # Verify auto-created Initial and Final nodes exist
        act_nodes = [e for e in root.iter() if e.attrib.get("{http://schema.omg.org/spec/XMI/2.1}type") in ("uml:InitialNode", "uml:ActivityFinalNode")]
        self.assertTrue(len(act_nodes) >= 2)

        # Verify connector caption for composition does not have "contains"
        xml_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        self.assertNotIn('caption="contains"', xml_str)

        # Cleanup
        if os.path.exists(out_file):
            os.remove(out_file)


if __name__ == "__main__":
    unittest.main()
