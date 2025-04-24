import time
import uuid

from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry import baggage,context
from opentelemetry.baggage.propagation import W3CBaggagePropagator

# Emulating the HTTP headers coming through services via global variable
headers = {}

# The Span Processor is responsible for exporting traces
# to OpenTelemetry-compatible collector endpoint (Jaeger)
span_processor = BatchSpanProcessor(
    GrpcSpanExporter(
        endpoint="http://collector.opentelemetry:4317/v1/traces"
    )
    # # alternatively, you can use a HTTP exporter, using port 4318
    # HttpSpanExporter(
    #     endpoint="http://collector.opentelemetry:4318/v1/traces"
    # )
)



#### Service 1 Side ############################################
#### This is a code being executed in Service 1

resource_1 = Resource.create(attributes={
    SERVICE_NAME: "my-service-1"  # just some example of service name
})
# Preparing a tracer, the core component
tracerProvider = TracerProvider(resource=resource_1)
tracerProvider.add_span_processor(span_processor)
trace.set_tracer_provider(tracerProvider)
tracer_1 = trace.get_tracer("tracer_1.name")

def svc_1_do_work(tracer):
    """
    This is an example of workload happening in Service 1,
    we have a parent span, and two children spans,
    the second span has an exception
    """
    with tracer.start_as_current_span("span-1") as span:
        global headers  # will be modifying the global var
        # example of putting some events into the span's log
        span.add_event("parent: some work started")
        # generate a random request id, as an example of some app's specific data
        request_id = str(uuid.uuid4())
        # getting current context, it is crucial to have a traceparent header
        # (see https://www.w3.org/TR/trace-context/#traceparent-header)
        # the current span will be a parent for the entire trace
        ctx = context.get_current()
        # another portion of app's specific data,
        # we put it into the headers to transfer between services
        headers["client_id"] = 1234
        headers["request_id"] = request_id
        # we also put this data into the span attributes,
        # so we could have it in our traces, it will be delivered in Jaeger
        span.set_attribute("client_id", headers["client_id"])
        span.set_attribute("request_id", headers["request_id"])
        # inject context (i.e. traceparent header) into HTTP headers
        # that way, spans created in  different services will be kept
        # under one parent, i.e. belonging to a single trace
        TraceContextTextMapPropagator().inject(headers, ctx)
        # just emulate some very important work here
        print("doing some work...")
        time.sleep(0.2)
        # here is an example of nested span,
        # it also can have its own set of attributes and events
        with tracer.start_as_current_span("child-1") as child_1:
            child_1.add_event("child-1: started")
            print("doing some nested work...")
            time.sleep(0.1)
            child_1.add_event("child-1: finished")
        #  yet another nested span, this time it contains an example of an exception
        with tracer.start_as_current_span("child-2") as child_2:
            child_2.add_event("child-2: started")
            print("doing some nested work...")
            time.sleep(0.25)
            child_2.add_event("child-2: exception")
            child_2.record_exception(ZeroDivisionError(), {"line_no": 123})
            child_2.set_status(Status(StatusCode.ERROR, "An exception occurred"))

        span.add_event("parent: finished")

svc_1_do_work(tracer_1)





#### Service 2 Side ############################################
#### This is a code being executed in Service 2

resource_2 = Resource.create(attributes={
    SERVICE_NAME: "my-service-2"  # just some example of service name
})
# Preparing a tracer, the core component
tracerProvider._resource = resource_2  # a small hack, since the tracerProvider already declared above
# tracerProvider = TracerProvider(resource=resource_2)
# tracerProvider.add_span_processor(span_processor)
# trace.set_tracer_provider(tracerProvider)
tracer_2 = trace.get_tracer("tracer_2.name")

def svc_2_do_work(tracer):
    """
    This is an example of workload happening in Service 2,
    first, we restore the context from HTTP headers,
    here we also have a parent span, and two children spans
    """
    # restoring the context from HTTP headers,
    # the key component is the traceparent string
    ctx = TraceContextTextMapPropagator().extract(carrier=headers)
    # note, we provide the context here, it makes this span belonging
    # to the parent trace we started in Service 1
    with tracer.start_as_current_span("svc-2", context=ctx) as span:
        span.add_event("parent: some work started")
        # extracting app's specific data from headers and putting them
        # into a span attributes
        span.set_attribute("client_id", headers["client_id"])
        span.set_attribute("request_id", headers["request_id"])
        # emulating some work
        print("doing some work...")
        time.sleep(0.2)
        # again, example of nested spans containing their events
        with tracer.start_as_current_span("child-1") as child_1:
            child_1.add_event("child-1: started")
            print("doing some nested work...")
            time.sleep(0.1)
            child_1.add_event("child-1: finished")

        with tracer.start_as_current_span("child-2") as child_2:
            child_2.add_event("child-2: started")
            print("doing some nested work...")
            time.sleep(0.25)
            child_2.add_event("child-2: success")
            child_2.set_status(Status(StatusCode.OK))

        span.add_event("parent: finished")
        span.set_status(Status(StatusCode.OK))

svc_2_do_work(tracer_2)
