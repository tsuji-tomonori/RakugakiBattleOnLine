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


class DoNotRetryException(Exception):
    ...


def put_item(connection_id: str, body: BodySchema) -> None:
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
    except Exception as e:
        logger.exception("put_item")
        raise DoNotRetryException from e


def post_room(body: BodySchema) -> None:
    try:
        items = room_table.query(
            KeyConditionExpression=Key(ep.ROOM_TABLE_PKEY).eq(body.room_id)
        )["Items"]
        connection_ids = [item[ep.ROOM_TABLE_SKEY] for item in items]
    except Exception as e:
        logger.exception("query")
        raise DoNotRetryException from e
    for connection_id in connection_ids:
        try:
            apigw.post_to_connection(
                Data=json.dumps({"command": "enter_room", "name": body.user_name}).encode(),
                ConnectionId=connection_id,
            )
        except boto3.client.exceptions.GoneException:
            # 何らかの事情でDBに残っていても接続が切れている場合があるのでSkip
            logger.exception("warn")
        except Exception as e:
            logger.exception("delete_item_error")
            raise DoNotRetryException from e


def service(connection_id: str, body: BodySchema) -> None:
    put_item(connection_id, body)
    post_room(body)


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    try:
        service(event["requestContext"]["connectionId"], BodySchema.from_event(event))
        return {
            "statusCode": 200,
        }
    except:
        return {
            "statusCode": 500,
        }
