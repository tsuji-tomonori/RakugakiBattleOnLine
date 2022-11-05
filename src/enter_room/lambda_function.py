from __future__ import annotations

import os
import json
import logging
from typing import NamedTuple

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

    @classmethod
    def from_env(cls) -> EnvironParam:
        return EnvironParam(**{k: os.environ[k] for k in EnvironParam._fields})


ep = EnvironParam.from_env()
logger = logging.getLogger()
logger.setLevel(ep.LOG_LEVEL)
dynamodb = boto3.resource("dynamodb")
apigw = boto3.client('apigatewaymanagementapi')
user_table = dynamodb.Table(ep.USER_TABLE_NAME)
room_table = dynamodb.Table(ep.ROOM_TABLE_NAME)


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    body = json.loads(event["body"])
    # 自分の情報をDBに登録する
    try:
        user_table.put_item(
            Item={
                ep.USER_TABLE_PKEY: event["requestContext"]["connectionId"],
                ep.USER_TABLE_SKEY: "info",
                "room_id": body["room_id"],
                "user_name": body["user_name"],
            }
        )
        room_table.put_item(
            Item={
                ep.ROOM_TABLE_PKEY: body["room_id"],
                ep.ROOM_TABLE_SKEY: event["requestContext"]["connectionId"],
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
            KeyConditions=Key(ep.ROOM_TABLE_PKEY).eq(body["room_id"])
        )
        connection_ids = [item[ep.ROOM_TABLE_SKEY] for item in items]
    except:
        logger.exception("TablePutError")
        return {
            "statusCode": 500,
        }
    try:
        for connection_id in connection_ids:
            apigw.post_to_connection(
                Data=f"{body['user_name']}さんが入出しました!".encode(),
                ConnectionId=connection_id,
            )
    except:
        logger.exception("TablePutError")
        return {
            "statusCode": 500,
        }
    return {
        "statusCode": 200,
    }
