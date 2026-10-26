"""Capture a small application adapter without any model, network or SDK install.

The default adapter deliberately drops a call. --fixed preserves it. Replace
the adapter function with your own explicitly selected conversion boundary.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from patchcourt.recorder import BoundaryRecorder


MESSAGES = [
    {"role": "system", "content": "Quote a courier shipment; preserve the customer's units."},
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "quote-01", "type": "function", "function": {"name": "quote_shipping",
         "arguments": '{"destination":"東京","weight_kg":2.75,"insured":true}'}}]},
    {"role": "tool", "tool_call_id": "quote-01", "content": '{"currency":"JPY","amount":1900}'},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixed", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new recording path; preserve previous captures")

    def adapter(messages):
        result = deepcopy(messages)
        if not args.fixed:
            result[1].pop("tool_calls")  # Deliberate example bug, not a new SDK discovery.
        return result

    recorder = BoundaryRecorder("courier-application-adapter", "1.0+demo-fix" if args.fixed else "1.0")
    _, verdict = recorder.transform(MESSAGES, adapter, request_id="shipping-quote-1")
    recorder.save(args.output)
    print("Captured " + str(args.output) + "; observed contract: " + verdict["status"])
    print("Controlled in-memory example. No SDK, model or network request was made.")


if __name__ == "__main__":
    main()
