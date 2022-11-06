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


class UDbInfoSchema(NamedTuple):
    room_id: str
    user_name: str

    @classmethod
    def from_db(cls, response: dict[str, Any]) -> UDbInfoSchema:
        return UDbInfoSchema(**{k: response["Item"][k] for k in UDbInfoSchema._fields})


class DoNotRetryException(Exception):
    ...


def all_delete_user_table(connection_id: str) -> None:
    res = user_table.query(KeyConditionExpression=Key(ep.USER_TABLE_PKEY).eq(connection_id))
    skeys = [item[ep.USER_TABLE_SKEY] for item in res["Items"]]
    try:
        for skey in skeys:
            user_table.delete_item(
                Key={
                    ep.USER_TABLE_PKEY: connection_id,
                    ep.USER_TABLE_SKEY: skey,
                }
            )
    except Exception as e:
        logger.exception("delete_item_error")
        raise DoNotRetryException from e


def get_info(connection_id: str) -> UDbInfoSchema | None:
    try:
        res_info = user_table.get_item(
            Key={
                ep.USER_TABLE_PKEY: connection_id,
                ep.USER_TABLE_SKEY: "info",
            }
        )
        logger.info(json.dumps(res_info, indent=2))
    except Exception as e:
        logger.exception("get_item_error")
        raise DoNotRetryException from e
    try:
        return UDbInfoSchema.from_db(res_info)
    except:
        return None


def delete_room_table(room_id: str, connection_id: str) -> None:
    try:
        room_table.delete_item(
            Key={
                ep.ROOM_TABLE_PKEY: room_id,
                ep.ROOM_TABLE_SKEY: connection_id,
            }
        )
    except Exception as e:
        logger.exception("delete_item_error")
        raise DoNotRetryException from e


def post_room(info: UDbInfoSchema) -> None:
    try:
        items = room_table.query(
            KeyConditionExpression=Key(ep.ROOM_TABLE_PKEY).eq(info.room_id)
        )["Items"]
        connection_ids = [item[ep.ROOM_TABLE_SKEY] for item in items]
    except Exception as e:
        logger.exception("query")
        raise DoNotRetryException from e
    for connection_id in connection_ids:
        try:
            apigw.post_to_connection(
                Data=f"{info.user_name}さんが退出しました!".encode(),
                ConnectionId=connection_id,
            )
        except boto3.client.exceptions.GoneException:
            # 何らかの事情でDBに残っていても接続が切れている場合があるのでSkip
            continue
        except Exception as e:
            logger.exception("delete_item_error")
            raise DoNotRetryException from e


def service(connection_id: str) -> None:
    info = get_info(connection_id)
    all_delete_user_table(connection_id)
    if info is None:
        return
    delete_room_table(info.room_id, connection_id)
    post_room(info)


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    try:
        service(event["requestContext"]["connectionId"])
        return {
            "statusCode": 200,
        }
    except:
        return {
            "statusCode": 500,
        }
