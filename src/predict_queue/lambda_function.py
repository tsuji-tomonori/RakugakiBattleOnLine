from __future__ import annotations

import os
import json
import logging
from typing import NamedTuple

import boto3


class EnvironParam(NamedTuple):
    LOG_LEVEL: str
    PREDICT_QUEUE_URL: str

    @classmethod
    def from_env(cls) -> EnvironParam:
        return EnvironParam(**{k: os.environ[k] for k in EnvironParam._fields})


ep = EnvironParam.from_env()
logger = logging.getLogger()
logger.setLevel(ep.LOG_LEVEL)
sqs = boto3.client("sqs")


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    try:
        sqs.send_message(
            QueueUrl=ep.PREDICT_QUEUE_URL,
            MessageBody=json.dumps(event),
        )
        return {
            "statusCode": 200,
        }
    except:
        logger.exception("send_message")
        return {
            "statusCode": 500,
        }
