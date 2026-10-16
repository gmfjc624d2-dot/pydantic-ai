"""Decode OTLP/HTTP trace payloads captured by `otlp_sink.py` (run with a venv that has logfire/OTel).

Usage: python decode_otlp.py SINK_DIR  -> writes SINK_DIR/decoded.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest


def _value(v: Any) -> Any:
    kind = v.WhichOneof('value')
    x = getattr(v, kind)
    return [_value(i) for i in x.values] if kind == 'array_value' else x


def main() -> None:
    sink = Path(sys.argv[1])
    decoded = []
    for body in sorted(sink.glob('*_v1_traces.bin')):
        request = ExportTraceServiceRequest.FromString(body.read_bytes())
        for resource_spans in request.resource_spans:
            span_attribute_keys: dict[str, list[str]] = {}
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    span_attribute_keys.setdefault(span.name, sorted({a.key for a in span.attributes}))
            decoded.append(
                {
                    'file': body.name,
                    'resource_attributes': {
                        a.key: str(_value(a.value))[:80] for a in resource_spans.resource.attributes
                    },
                    'span_attribute_keys_by_span_name': span_attribute_keys,
                }
            )
    (sink / 'decoded.json').write_text(json.dumps(decoded, indent=2) + '\n')


if __name__ == '__main__':
    main()
