from __future__ import annotations

import os
import json
import logging
from typing import Any, NamedTuple

import boto3
from boto3.dynamodb.conditions import Key


class EnvironParam(NamedTuple):
    LOG_LEVEL: str
    USER_TABLE_NAME: str
    USER_TABLE_PKEY: str
    USER_TABLE_SKEY: str
    ROOM_TABLE_NAME: str
    ROOM_TABLE_PKEY: str
    ROOM_TABLE_SKEY: str
    ENDPOINT_URL: str

    @classmethod
    def from_env(cls) -> EnvironParam:
        return EnvironParam(**{k: os.environ[k] for k in EnvironParam._fields})


ep = EnvironParam.from_env()
logger = logging.getLogger()
logger.setLevel(ep.LOG_LEVEL)
dynamodb = boto3.resource("dynamodb")
apigw = boto3.client("apigatewaymanagementapi", endpoint_url=ep.ENDPOINT_URL)
user_table = dynamodb.Table(ep.USER_TABLE_NAME)
room_table = dynamodb.Table(ep.ROOM_TABLE_NAME)


class BodySchema(NamedTuple):
    room_id: str
    user_name: str

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> BodySchema:
        body = json.loads(event["body"])
        return BodySchema(**{k: body[k] for k in BodySchema._fields})


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    body = BodySchema.from_event(event)
    connection_id = event["requestContext"]["connectionId"]
    # 自分の情報をDBに登録する
    try:
        user_table.put_item(
            Item={
                ep.USER_TABLE_PKEY: connection_id,
                ep.USER_TABLE_SKEY: "info",
                "room_id": body.room_id,
                "user_name": body.user_name,
            }
        )
        room_table.put_item(
            Item={
                ep.ROOM_TABLE_PKEY: body.room_id,
                ep.ROOM_TABLE_SKEY: connection_id,
            }
        )
    except:
        logger.exception("TablePutError")
        return {
            "statusCode": 500,
        }
    # roomに入出したことを参加者に伝える
    connection_ids = []
    try:
        items = room_table.query(
            KeyConditionExpression=Key(ep.ROOM_TABLE_PKEY).eq(body.room_id)
        )["Items"]
        connection_ids = [item[ep.ROOM_TABLE_SKEY] for item in items]
    except:
        logger.exception("TableQueryError")
        return {
            "statusCode": 500,
        }
    try:
        for connection_id in connection_ids:
            apigw.post_to_connection(
                Data=f"{body.user_name}さんが入出しました!".encode(),
                ConnectionId=connection_id,
            )
    except:
        logger.exception("post_to_connection_error")
        return {
            "statusCode": 500,
        }
    return {
        "statusCode": 200,
    }
