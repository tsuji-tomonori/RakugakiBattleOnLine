from __future__ import annotations

import os
import json
import logging
from typing import Any, NamedTuple

import boto3
from boto3.dynamodb.conditions import Key


class EnvironParam(NamedTuple):
    LOG_LEVEL: str
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
apigw = boto3.client("apigatewaymanagementapi", endpoint_url=ep.ENDPOINT_URL)
dynamodb = boto3.resource("dynamodb")
room_table = dynamodb.Table(ep.ROOM_TABLE_NAME)


class BodySchema(NamedTuple):
    room_id: str
    n_odai: int
    n_time_sec: int

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> BodySchema:
        body = json.loads(event["body"])
        return BodySchema(**{k: body[k] for k in BodySchema._fields})


class DoNotRetryException(Exception):
    ...


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
                Data=json.dumps({"command": "game_start", "n_odai": body.n_odai, "n_time": body.n_time_sec}).encode(),
                ConnectionId=connection_id,
            )
        except boto3.client.exceptions.GoneException:
            # 何らかの事情でDBに残っていても接続が切れている場合があるのでSkip
            logger.exception("warn")
        except Exception as e:
            logger.exception("post_to_connection")
            raise DoNotRetryException from e


def service(connection_id: str, body: BodySchema) -> None:
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
