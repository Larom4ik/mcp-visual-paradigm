"""Canonical Architectural Blueprints (Golden Reference Templates) for all UML and ERD diagrams."""

from typing import Any, Dict


def get_class_diagram_blueprint() -> Dict[str, Any]:
    """Return a canonical DDD (Domain-Driven Design) Class Diagram blueprint."""
    return {
        "project_name": "EnterpriseDomainModel",
        "diagram_name": "Domain Model (DDD Pattern)",
        "packages": [
            {"name": "Domain", "parent": None},
            {"name": "Services", "parent": None},
            {"name": "Contracts", "parent": None},
        ],
        "classes": [
            {
                "name": "Order",
                "package": "Domain",
                "attributes": [
                    {"name": "id", "type": "UUID", "visibility": "public"},
                    {"name": "orderNumber", "type": "string", "visibility": "private"},
                    {"name": "totalAmount", "type": "Decimal", "visibility": "private"},
                    {"name": "createdAt", "type": "DateTime", "visibility": "protected"},
                ],
                "methods": [
                    {
                        "name": "calculateTotal",
                        "return_type": "Decimal",
                        "params": [],
                        "description": "Recalculates total sum based on item prices and applicable discounts.",
                    },
                    {
                        "name": "addItem",
                        "return_type": "void",
                        "params": [
                            {"name": "item", "type": "OrderItem"},
                        ],
                    },
                ],
            },
            {
                "name": "OrderItem",
                "package": "Domain",
                "attributes": [
                    {"name": "id", "type": "UUID", "visibility": "public"},
                    {"name": "productName", "type": "string", "visibility": "private"},
                    {"name": "quantity", "type": "int", "visibility": "public"},
                    {"name": "unitPrice", "type": "Decimal", "visibility": "public"},
                ],
                "methods": [
                    {"name": "getSubtotal", "return_type": "Decimal", "params": []},
                ],
            },
            {
                "name": "Customer",
                "package": "Domain",
                "attributes": [
                    {"name": "id", "type": "UUID", "visibility": "public"},
                    {"name": "fullName", "type": "string", "visibility": "public"},
                    {"name": "email", "type": "string", "visibility": "private"},
                    {"name": "loyaltyTier", "type": "string", "visibility": "public"},
                ],
                "methods": [
                    {"name": "upgradeTier", "return_type": "void", "params": []},
                ],
            },
            {
                "name": "IOrderRepository",
                "package": "Contracts",
                "is_interface": True,
                "methods": [
                    {"name": "findById", "return_type": "Order", "params": [{"name": "id", "type": "UUID"}]},
                    {"name": "save", "return_type": "void", "params": [{"name": "order", "type": "Order"}]},
                ],
            },
            {
                "name": "OrderApplicationService",
                "package": "Services",
                "methods": [
                    {
                        "name": "placeOrder",
                        "return_type": "UUID",
                        "params": [
                            {"name": "customerId", "type": "UUID"},
                            {"name": "items", "type": "List[OrderItem]"},
                        ],
                    },
                ],
            },
        ],
        "class_relations": [
            # 1. Composition: Order strictly owns OrderItems (1 to 1..*)
            {
                "source": "Order",
                "target": "OrderItem",
                "type": "Composition",
                "source_multiplicity": "1",
                "target_multiplicity": "1..*",
                "description": "Order aggregate root composes order item details.",
            },
            # 2. Aggregation: Customer has Orders (1 to 0..*)
            {
                "source": "Customer",
                "target": "Order",
                "type": "Aggregation",
                "source_multiplicity": "1",
                "target_multiplicity": "0..*",
                "description": "Customer maintains reference to order history.",
            },
            # 3. Dependency: Service calls repository contract
            {
                "source": "OrderApplicationService",
                "target": "IOrderRepository",
                "type": "Dependency",
                "description": "Application service depends on repository abstraction (DIP).",
            },
        ],
        "notes": [
            {
                "text": "Composition guarantees that OrderItems are cascade-deleted if the parent Order is purged.",
                "attached_to": "Order",
            }
        ],
    }


def get_activity_diagram_blueprint() -> Dict[str, Any]:
    """Return a canonical Multi-Lane Activity Diagram blueprint."""
    return {
        "project_name": "OrderFulfillmentProcess",
        "diagram_name": "Checkout & Fulfillment Workflow",
        "activity_partitions": [
            {"name": "Customer"},
            {"name": "OrderService"},
            {"name": "PaymentGateway"},
            {"name": "WarehouseService"},
        ],
        "activity_nodes": [
            {"name": "Start", "type": "Initial", "partition": "Customer"},
            {"name": "SelectItemsAndAddress", "type": "Action", "partition": "Customer"},
            {"name": "ValidateCartAndStock", "type": "Action", "partition": "OrderService"},
            {"name": "InventoryDecision", "type": "Decision", "partition": "OrderService"},
            {"name": "NotifyOutOfStock", "type": "Action", "partition": "OrderService"},
            {"name": "OutFinal", "type": "FlowFinal", "partition": "Customer"},
            {"name": "RequestPaymentAuth", "type": "Action", "partition": "PaymentGateway"},
            {"name": "ForkPostPayment", "type": "Fork", "partition": "OrderService"},
            {"name": "SendConfirmationEmail", "type": "Action", "partition": "OrderService"},
            {"name": "AssembleAndPackGoods", "type": "Action", "partition": "WarehouseService"},
            {"name": "JoinFulfillment", "type": "Join", "partition": "OrderService"},
            {"name": "DispatchDelivery", "type": "Action", "partition": "WarehouseService"},
            {"name": "End", "type": "Final", "partition": "Customer"},
        ],
        "control_flows": [
            {"source": "Start", "target": "SelectItemsAndAddress"},
            {"source": "SelectItemsAndAddress", "target": "ValidateCartAndStock"},
            {"source": "ValidateCartAndStock", "target": "InventoryDecision"},
            # Alternate branches from Decision MUST have guard conditions
            {"source": "InventoryDecision", "target": "RequestPaymentAuth", "guard": "[items in stock]"},
            {"source": "InventoryDecision", "target": "NotifyOutOfStock", "guard": "[out of stock]"},
            {"source": "NotifyOutOfStock", "target": "OutFinal"},
            # Parallel Fork & Join synchronization
            {"source": "RequestPaymentAuth", "target": "ForkPostPayment"},
            {"source": "ForkPostPayment", "target": "SendConfirmationEmail"},
            {"source": "ForkPostPayment", "target": "AssembleAndPackGoods"},
            {"source": "SendConfirmationEmail", "target": "JoinFulfillment"},
            {"source": "AssembleAndPackGoods", "target": "JoinFulfillment"},
            {"source": "JoinFulfillment", "target": "DispatchDelivery"},
            {"source": "DispatchDelivery", "target": "End"},
        ],
        "notes": [
            {
                "text": "Parallel tasks are split via ForkNode and synchronized via JoinNode before dispatch.",
                "attached_to": "ForkPostPayment",
            }
        ],
    }


def get_deployment_diagram_blueprint() -> Dict[str, Any]:
    """Return a canonical 4-Tier Cloud Infrastructure Deployment blueprint."""
    return {
        "project_name": "CloudInfrastructureTopology",
        "diagram_name": "Production 4-Tier Topology",
        "deployment_nodes": [
            {
                "name": "Client Workstation",
                "node_type": "Device",
                "description": "End-user physical desktop or mobile device running modern web browser.",
            },
            {
                "name": "API Gateway / Ingress Host",
                "node_type": "Node",
                "description": "DMZ reverse proxy and SSL termination server.",
            },
            {
                "name": "Application Cluster Host",
                "node_type": "Node",
                "description": "High-availability compute cluster running containerized microservices.",
            },
            {
                "name": "Docker Container Host",
                "node_type": "ExecutionEnvironment",
                "parent_node": "Application Cluster Host",
                "description": "Container runtime host environment.",
            },
            {
                "name": "Database Cluster Host",
                "node_type": "Node",
                "description": "Isolated database server with encrypted NVMe storage.",
            },
            {
                "name": "PostgreSQL 16 Engine",
                "node_type": "ExecutionEnvironment",
                "parent_node": "Database Cluster Host",
                "description": "Relational RDBMS database engine.",
            },
        ],
        "artifacts": [
            {
                "name": "react_portal_bundle.js",
                "deployed_on": "Client Workstation",
                "file_name": "bundle.min.js",
            },
            {
                "name": "gateway_proxy.conf",
                "deployed_on": "API Gateway / Ingress Host",
                "file_name": "nginx.conf",
            },
            {
                "name": "order_service.jar",
                "deployed_on": "Docker Container Host",
                "file_name": "order-api-v2.jar",
            },
            {
                "name": "enterprise_schema.sql",
                "deployed_on": "PostgreSQL 16 Engine",
                "file_name": "schema_v1.sql",
            },
        ],
        "communication_paths": [
            {
                "source": "Client Workstation",
                "target": "API Gateway / Ingress Host",
                "protocol": "HTTPS (Port 443)",
            },
            {
                "source": "API Gateway / Ingress Host",
                "target": "Application Cluster Host",
                "protocol": "gRPC (Port 50051)",
            },
            {
                "source": "Application Cluster Host",
                "target": "Database Cluster Host",
                "protocol": "TCP/IP (Port 5432)",
            },
        ],
        "deployment_links": [
            {"artifact": "order_service.jar", "node": "Docker Container Host"},
        ],
    }


def get_use_case_diagram_blueprint() -> Dict[str, Any]:
    """Return a canonical UML Use Case Diagram blueprint."""
    return {
        "project_name": "ECommerceUseCases",
        "diagram_name": "E-Commerce System Boundary & Use Cases",
        "actors": [
            {"name": "Customer", "description": "Primary actor initiating purchases."},
            {"name": "StoreAdmin", "description": "Secondary actor overseeing inventory and orders."},
            {"name": "PaymentGateway", "description": "External payment service provider."},
        ],
        "use_cases": [
            {"name": "BrowseCatalog"},
            {"name": "PlaceOrder"},
            {"name": "AuthenticateUser"},
            {"name": "TwoFactorVerification"},
            {"name": "ApplyDiscountCoupon"},
            {"name": "ManageInventory"},
        ],
        "system_boundary": {
            "name": "Storefront Web Platform",
            "use_cases": [
                "BrowseCatalog",
                "PlaceOrder",
                "AuthenticateUser",
                "TwoFactorVerification",
                "ApplyDiscountCoupon",
                "ManageInventory",
            ],
        },
        "uc_relations": [
            {"source": "Customer", "target": "BrowseCatalog", "type": "Association"},
            {"source": "Customer", "target": "PlaceOrder", "type": "Association"},
            {"source": "PlaceOrder", "target": "AuthenticateUser", "type": "Include"},
            {"source": "AuthenticateUser", "target": "TwoFactorVerification", "type": "Extend"},
            {"source": "PlaceOrder", "target": "ApplyDiscountCoupon", "type": "Extend"},
            {"source": "StoreAdmin", "target": "ManageInventory", "type": "Association"},
        ],
    }


def get_erd_diagram_blueprint() -> Dict[str, Any]:
    """Return a canonical 3NF Physical Relational ERD blueprint."""
    return {
        "project_name": "EnterpriseRelationalSchema",
        "diagram_name": "Physical Schema (3NF)",
        "entities": [
            {
                "name": "customers",
                "columns": [
                    {"name": "id", "type": "UUID", "is_pk": True},
                    {"name": "email", "type": "VARCHAR", "length": 255, "is_nullable": False},
                    {"name": "full_name", "type": "VARCHAR", "length": 150, "is_nullable": False},
                    {"name": "created_at", "type": "TIMESTAMP", "is_nullable": False},
                ],
            },
            {
                "name": "orders",
                "columns": [
                    {"name": "id", "type": "UUID", "is_pk": True},
                    {"name": "customer_id", "type": "UUID", "is_fk": True, "is_nullable": False},
                    {"name": "order_number", "type": "VARCHAR", "length": 64, "is_nullable": False},
                    {"name": "total_amount", "type": "NUMERIC", "length": 12, "is_nullable": False},
                    {"name": "status", "type": "VARCHAR", "length": 32, "is_nullable": False},
                ],
            },
            {
                "name": "order_items",
                "columns": [
                    {"name": "id", "type": "UUID", "is_pk": True},
                    {"name": "order_id", "type": "UUID", "is_fk": True, "is_nullable": False},
                    {"name": "product_name", "type": "VARCHAR", "length": 255, "is_nullable": False},
                    {"name": "quantity", "type": "INTEGER", "is_nullable": False},
                    {"name": "unit_price", "type": "NUMERIC", "length": 10, "is_nullable": False},
                ],
            },
        ],
        "er_relations": [
            {"source": "customers", "target": "orders", "type": "1:N"},
            {"source": "orders", "target": "order_items", "type": "1:N"},
        ],
    }


def get_state_diagram_blueprint() -> Dict[str, Any]:
    """Return a canonical State Machine Diagram blueprint."""
    return {
        "project_name": "OrderLifecycleStateMachine",
        "diagram_name": "Order Lifecycle State Machine",
        "states": [
            {"name": "Initial", "type": "Initial"},
            {"name": "Draft", "type": "State", "entry": "initOrder()", "exit": "validateDraft()"},
            {"name": "PendingPayment", "type": "State", "entry": "lockInventory()"},
            {"name": "Processing", "type": "State", "do": "sendToWarehouse()"},
            {"name": "Shipped", "type": "State", "entry": "generateTrackingNumber()"},
            {"name": "Completed", "type": "Final"},
            {"name": "Cancelled", "type": "Final"},
        ],
        "transitions": [
            {"source": "Initial", "target": "Draft", "trigger": "createOrder"},
            {"source": "Draft", "target": "PendingPayment", "trigger": "checkout"},
            {"source": "PendingPayment", "target": "Processing", "trigger": "paymentSuccess", "guard": "[balance >= total]"},
            {"source": "PendingPayment", "target": "Cancelled", "trigger": "paymentFailed", "guard": "[card declined]"},
            {"source": "Processing", "target": "Shipped", "trigger": "dispatch", "guard": "[items packed]"},
            {"source": "Shipped", "target": "Completed", "trigger": "delivered"},
        ],
    }


def get_architecture_blueprint(diagram_type: str) -> Dict[str, Any]:
    """Retrieve the canonical golden specification blueprint for the requested diagram type."""
    norm = diagram_type.strip().lower().replace("_", "").replace(" ", "").replace("-", "")
    if "class" in norm:
        return get_class_diagram_blueprint()
    if "activity" in norm:
        return get_activity_diagram_blueprint()
    if "deploy" in norm:
        return get_deployment_diagram_blueprint()
    if "usecase" in norm or "uc" in norm:
        return get_use_case_diagram_blueprint()
    if "erd" in norm or "entity" in norm or "database" in norm:
        return get_erd_diagram_blueprint()
    if "state" in norm or "sm" in norm:
        return get_state_diagram_blueprint()

    # Default to class diagram blueprint
    return get_class_diagram_blueprint()
