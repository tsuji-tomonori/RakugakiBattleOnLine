from __future__ import annotations

import os
import json
import logging
from typing import NamedTuple

import boto3


class EnvironParam(NamedTuple):
    LOG_LEVEL: str
    USER_TABLE_NAME: str
    USER_TABLE_PKEY: str
    USER_TABLE_SKEY: str

    @classmethod
    def from_env(cls) -> EnvironParam:
        return EnvironParam(**{k: os.environ[k] for k in EnvironParam._fields})


ep = EnvironParam.from_env()
logger = logging.getLogger()
logger.setLevel(ep.LOG_LEVEL)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(ep.USER_TABLE_NAME)


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    try:
        table.put_item(
            Item={
                ep.USER_TABLE_PKEY: event["requestContext"]["connectionId"],
                ep.USER_TABLE_SKEY: "login",
            }
        )
        return {
            "statusCode": 200,
        }
    except:
        logger.exception("TablePutError")
        return {
            "statusCode": 500,
        }
