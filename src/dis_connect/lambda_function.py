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
apigw = boto3.client('apigatewaymanagementapi', endpoint_url=ep.ENDPOINT_URL)
user_table = dynamodb.Table(ep.USER_TABLE_NAME)
room_table = dynamodb.Table(ep.ROOM_TABLE_NAME)


class UDbInfoSchema(NamedTuple):
    room_id: str

    @classmethod
    def from_db(cls, response: dict[str, Any]) -> UDbInfoSchema:
        return UDbInfoSchema(**{response["Item"][k] for k in UDbInfoSchema._fields})


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    # 自分の情報を削除する
    connection_id = event["requestContext"]["connectionId"]
    try:
        # 今後の処理のためinfoを取得しておく
        res_info = user_table.get_item(
            Key={
                ep.USER_TABLE_PKEY: connection_id,
                ep.USER_TABLE_SKEY: "info",
            }
        )
        info = UDbInfoSchema.from_db(res_info)
        user_table.delete_item(
            Key={
                ep.USER_TABLE_PKEY: connection_id,
                ep.USER_TABLE_SKEY: "info",
            }
        )
        user_table.delete_item(
            Key={
                ep.USER_TABLE_PKEY: connection_id,
                ep.USER_TABLE_SKEY: "login",
            }
        )
        room_table.delete_item(
            Key={
                ep.ROOM_TABLE_PKEY: info.room_id,
                ep.ROOM_TABLE_SKEY: connection_id,
            }
        )
    except:
        logger.exception("TablePutError")
        return {
            "statusCode": 500,
        }
    # roomに入出したことを参加者に伝える
    room_connection_ids = []
    try:
        items = room_table.query(
            KeyConditionExpression=Key(ep.ROOM_TABLE_PKEY).eq(info.room_id)
        )["Items"]
        room_connection_ids = [item[ep.ROOM_TABLE_SKEY] for item in items]
    except:
        logger.exception("TableQueryError")
        return {
            "statusCode": 500,
        }
    try:
        for room_connection_id in room_connection_ids:
            apigw.post_to_connection(
                Data=f"{info['user_name']}さんが退出しました!".encode(),
                ConnectionId=room_connection_id,
            )
    except:
        logger.exception("post_to_connection_error")
        return {
            "statusCode": 500,
        }
    return {
        "statusCode": 200,
    }
