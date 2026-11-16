import json
from typing import Any


def eventbridge_event(bucket: str, key: str, detail_type: str = "Object Created") -> dict[str, Any]:
    return {
        "detail-type": detail_type,
        "source": "aws.s3",
        "detail": {"bucket": {"name": bucket}, "object": {"key": key}},
    }


def sqs_record(message_id: str, body: str) -> dict[str, str]:
    return {"messageId": message_id, "body": body}


def sqs_event(*records: dict[str, str]) -> dict[str, Any]:
    return {"Records": list(records)}


def created_event(bucket: str, key: str, message_id: str = "m1") -> dict[str, Any]:
    return sqs_event(sqs_record(message_id, json.dumps(eventbridge_event(bucket, key))))
