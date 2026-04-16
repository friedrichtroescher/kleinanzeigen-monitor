"""OpenTelemetry initialization for CronJob lifecycle."""
import logging
import os

from opentelemetry import trace, metrics

_tracer_provider = None
_meter_provider = None
_logger_provider = None

tracer = trace.get_tracer("kleinanzeigen-monitor")
meter = metrics.get_meter("kleinanzeigen-monitor")

listings_fetched = meter.create_counter("monitor.listings.fetched", description="Total listings fetched")
listings_new = meter.create_counter("monitor.listings.new", description="New listings evaluated")
listings_matched = meter.create_counter("monitor.listings.matched", description="Matched listings sent")
eval_errors = meter.create_counter("monitor.evaluations.errors", description="Evaluation errors")
scrape_rejections = meter.create_counter("monitor.scrape.rejections",
                                         description="Scraping rejected by Kleinanzeigen (403/429)")
run_duration = meter.create_histogram("monitor.run.duration_seconds", description="Total run duration", unit="s")
search_duration = meter.create_histogram("monitor.search.duration_seconds",
                                         description="Duration of a single search (fetch + evaluate)", unit="s")
prefilter_rejections = meter.create_counter("monitor.evaluations.prefilter_rejections",
                                            description="Listings rejected by the deep_eval prefilter")
detail_fetch_failures = meter.create_counter("monitor.listings.detail_fetch_failures",
                                             description="Detail page fetch failures during deep_eval")
listing_price = meter.create_histogram(
    "monitor.listings.price_euros",
    description="Listing prices in EUR per search",
    unit="EUR",
)


def init_telemetry() -> None:
    """Initialize OTEL if OTEL_EXPORTER_OTLP_ENDPOINT is set. No-op otherwise."""
    global _tracer_provider, _meter_provider, _logger_provider

    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    from opentelemetry import _logs
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    resource = Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "kleinanzeigen-monitor"),
        "service.namespace": "kleinanzeigen",
        "deployment.environment": os.environ.get("DEPLOYMENT_ENVIRONMENT", "production"),
    })

    # Traces
    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(_tracer_provider)

    # Metrics
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=60_000)
    _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(_meter_provider)

    # Logs
    _logger_provider = LoggerProvider(resource=resource)
    _logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    _logs.set_logger_provider(_logger_provider)
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=_logger_provider)
    logging.getLogger().addHandler(handler)

    # Auto-instrument requests library
    RequestsInstrumentor().instrument()


def shutdown_telemetry() -> None:
    """Force-flush and shutdown all providers. Without this the final batch is lost."""
    for provider in (_tracer_provider, _meter_provider, _logger_provider):
        if provider:
            provider.force_flush(timeout_millis=5000)
            provider.shutdown()
