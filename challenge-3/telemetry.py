"""
Telemetry and Observability Module for Fraud Detection Workflow

This module provides comprehensive observability capabilities including:
- OpenTelemetry tracing and metrics
- Azure Application Insights integration
- Custom business events and metrics
- Cosmos DB operation instrumentation
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Import observability components from Agent Framework
from agent_framework.observability import (
    setup_observability,
    get_tracer,
    get_meter,
    OtelAttr,
    create_workflow_span,
    create_processing_span,
)
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import format_trace_id
from opentelemetry import trace, metrics

# Import Application Insights for custom events
from applicationinsights import TelemetryClient
from applicationinsights.channel import TelemetryChannel
import logging

# Load environment variables
load_dotenv(override=True)

class TelemetryManager:
    """Central telemetry management class for the fraud detection workflow."""
    
    def __init__(self):
        self.tracer = None
        self.meter = None
        self.telemetry_client = None
        self._initialized = False
        
        # Metrics
        self.transaction_counter = None
        self.risk_score_histogram = None
        self.compliance_decision_counter = None
    
    def initialize_observability(self):
        """Initialize observability with Azure Application Insights and local tracing."""
        
        if self._initialized:
            return
        
        # Get configuration from environment variables
        app_insights_connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
        otlp_endpoint = os.environ.get("OTLP_ENDPOINT")
        vs_code_extension_port = os.environ.get("VS_CODE_EXTENSION_PORT")
        
        # Setup observability with multiple exporters for comprehensive monitoring
        setup_observability(
            enable_sensitive_data=True,  # Enable for detailed financial transaction traces
            applicationinsights_connection_string=app_insights_connection_string,
            otlp_endpoint=otlp_endpoint,
            vs_code_extension_port=int(vs_code_extension_port) if vs_code_extension_port else None
        )
        
        # Initialize tracer and meter
        self.tracer = get_tracer("fraud_detection_workflow", "1.0.0")
        self.meter = get_meter("fraud_detection_metrics", "1.0.0")
        
        # Initialize Application Insights client
        if app_insights_connection_string:
            self.telemetry_client = TelemetryClient(app_insights_connection_string)
            self.telemetry_client.context.application.ver = "1.0.0"
            self.telemetry_client.context.device.id = "fraud_detection_workflow"
        
        # Initialize custom metrics
        self._initialize_metrics()
        
        print("🔍 Observability initialized for fraud detection workflow")
        print(f"📊 Application Insights: {'✓' if app_insights_connection_string else '✗'}")
        print(f"🔗 OTLP Endpoint: {'✓' if otlp_endpoint else '✗'}")
        print(f"🔧 VS Code Extension: {'✓' if vs_code_extension_port else '✗'}")
        
        self._initialized = True
    
    def _initialize_metrics(self):
        """Initialize custom metrics for business KPIs."""
        
        self.transaction_counter = self.meter.create_counter(
            name="fraud_detection.transactions.processed",
            description="Number of transactions processed",
            unit="1"
        )
        
        self.risk_score_histogram = self.meter.create_histogram(
            name="fraud_detection.risk_score.distribution",
            description="Distribution of risk scores",
            unit="1"
        )
        
        self.compliance_decision_counter = self.meter.create_counter(
            name="fraud_detection.compliance.decisions",
            description="Number of compliance decisions by type",
            unit="1"
        )
    
    def flush_telemetry(self):
        """Flush telemetry to ensure events are sent immediately."""
        if self.telemetry_client:
            self.telemetry_client.flush()
            print("📊 Telemetry flushed to Application Insights")
    
    def send_business_event(self, event_name: str, properties: Dict[str, Any]):
        """Send business event using both OpenTelemetry and Application Insights approaches."""
        
        # Method 1: OpenTelemetry Event (guaranteed to appear in traces)
        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(f"business_event.{event_name}", properties)
        
        # Method 2: OpenTelemetry Custom Span (appears as separate trace)
        with self.tracer.start_as_current_span(
            f"business_event.{event_name}",
            kind=SpanKind.INTERNAL,
            attributes={f"event.{k}": str(v) for k, v in properties.items()}
        ) as event_span:
            event_span.set_attribute("event.type", "business_metric")
            event_span.set_attribute("event.name", event_name)
            
        # Method 3: Traditional Application Insights (legacy support)
        if self.telemetry_client:
            try:
                self.telemetry_client.track_event(event_name, properties)
                self.telemetry_client.flush()  # Immediate flush
            except Exception as e:
                print(f"⚠️ Application Insights custom event failed: {e}")
        
        print(f"📊 Business event sent: {event_name} (multiple channels)")
    
    def record_transaction_processed(self, step: str, transaction_id: str):
        """Record that a transaction was processed."""
        if self.transaction_counter:
            self.transaction_counter.add(1, {
                "step": step,
                "transaction_id": transaction_id
            })
    
    def record_risk_score(self, risk_score: float, transaction_id: str, recommendation: str):
        """Record risk score distribution."""
        if self.risk_score_histogram:
            self.risk_score_histogram.record(risk_score, {
                "transaction_id": transaction_id,
                "recommendation": recommendation
            })
    
    def record_compliance_decision(self, decision: str, transaction_id: str, **kwargs):
        """Record compliance decision."""
        if self.compliance_decision_counter:
            attributes = {
                "decision": decision,
                "transaction_id": transaction_id
            }
            attributes.update(kwargs)
            self.compliance_decision_counter.add(1, attributes)
    
    def create_cosmos_span(self, operation: str, collection: str, **attributes):
        """Create a span for Cosmos DB operations."""
        return self.tracer.start_as_current_span(
            f"cosmos_db.{collection.lower()}.{operation}",
            attributes={
                "db.operation": operation,
                "db.collection.name": collection,
                **attributes
            }
        )
    
    def create_processing_span(self, executor_id: str, executor_type: str, message_type: str):
        """Create a processing span for executors."""
        return create_processing_span(
            executor_id=executor_id,
            executor_type=executor_type,
            message_type=message_type
        )
    
    def create_workflow_span(self, workflow_name: str, **attributes):
        """Create a workflow span."""
        return self.tracer.start_as_current_span(
            workflow_name,
            kind=SpanKind.CLIENT,
            attributes={
                "workflow.name": workflow_name,
                "workflow.version": "1.0.0",
                **attributes
            }
        )
    
    def get_current_trace_id(self) -> Optional[str]:
        """Get the current trace ID."""
        current_span = trace.get_current_span()
        if current_span:
            return format_trace_id(current_span.get_span_context().trace_id)
        return None


class CosmosDbInstrumentation:
    """Instrumentation wrapper for Cosmos DB operations."""
    
    def __init__(self, telemetry_manager: TelemetryManager):
        self.telemetry = telemetry_manager
    
    def instrument_transaction_get(self, func):
        """Decorator to instrument transaction retrieval."""
        def wrapper(transaction_id: str, *args, **kwargs):
            with self.telemetry.create_cosmos_span(
                "query", "Transactions", 
                **{"transaction.id": transaction_id}
            ) as span:
                try:
                    result = func(transaction_id, *args, **kwargs)
                    
                    if "error" not in result:
                        span.set_attribute("transaction.amount", result.get("amount", 0))
                        span.set_attribute("transaction.currency", result.get("currency", ""))
                        span.set_attribute("transaction.destination", result.get("destination_country", ""))
                        span.set_attribute("cosmos_db.success", True)
                    else:
                        span.set_attribute("cosmos_db.success", False)
                        span.set_attribute("cosmos_db.error", result["error"])
                    
                    return result
                    
                except Exception as e:
                    span.set_attribute("cosmos_db.success", False)
                    span.set_attribute("cosmos_db.error", str(e))
                    span.record_exception(e)
                    return {"error": str(e)}
        
        return wrapper
    
    def instrument_customer_get(self, func):
        """Decorator to instrument customer retrieval."""
        def wrapper(customer_id: str, *args, **kwargs):
            with self.telemetry.create_cosmos_span(
                "query", "Customers",
                **{"customer.id": customer_id}
            ) as span:
                try:
                    result = func(customer_id, *args, **kwargs)
                    
                    if "error" not in result:
                        span.set_attribute("customer.country", result.get("country", ""))
                        span.set_attribute("customer.account_age", result.get("account_age_days", 0))
                        span.set_attribute("customer.device_trust_score", result.get("device_trust_score", 0))
                        span.set_attribute("customer.past_fraud", result.get("past_fraud", False))
                        span.set_attribute("cosmos_db.success", True)
                    else:
                        span.set_attribute("cosmos_db.success", False)
                        span.set_attribute("cosmos_db.error", result["error"])
                    
                    return result
                    
                except Exception as e:
                    span.set_attribute("cosmos_db.success", False)
                    span.set_attribute("cosmos_db.error", str(e))
                    span.record_exception(e)
                    return {"error": str(e)}
        
        return wrapper
    
    def instrument_transaction_list(self, func):
        """Decorator to instrument transaction list retrieval."""
        def wrapper(customer_id: str, *args, **kwargs):
            with self.telemetry.create_cosmos_span(
                "query", "Transactions",
                **{"customer.id": customer_id}
            ) as span:
                try:
                    result = func(customer_id, *args, **kwargs)
                    
                    if isinstance(result, list) and not (len(result) == 1 and "error" in result[0]):
                        span.set_attribute("transaction.count", len(result))
                        span.set_attribute("cosmos_db.success", True)
                    else:
                        span.set_attribute("cosmos_db.success", False)
                        span.set_attribute("cosmos_db.error", "Failed to retrieve transactions")
                    
                    return result
                    
                except Exception as e:
                    span.set_attribute("cosmos_db.success", False)
                    span.set_attribute("cosmos_db.error", str(e))
                    span.record_exception(e)
                    return [{"error": str(e)}]
        
        return wrapper


# Global telemetry instance
telemetry_manager = TelemetryManager()

# Convenience functions for easy access
def initialize_telemetry():
    """Initialize the global telemetry manager."""
    telemetry_manager.initialize_observability()

def get_telemetry_manager() -> TelemetryManager:
    """Get the global telemetry manager instance."""
    return telemetry_manager

def send_business_event(event_name: str, properties: Dict[str, Any]):
    """Send a business event through the telemetry manager."""
    telemetry_manager.send_business_event(event_name, properties)

def flush_telemetry():
    """Flush telemetry data."""
    telemetry_manager.flush_telemetry()

def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID."""
    return telemetry_manager.get_current_trace_id()

# Export key functions and classes
__all__ = [
    'TelemetryManager',
    'CosmosDbInstrumentation',
    'telemetry_manager',
    'initialize_telemetry',
    'get_telemetry_manager',
    'send_business_event',
    'flush_telemetry',
    'get_current_trace_id'
]