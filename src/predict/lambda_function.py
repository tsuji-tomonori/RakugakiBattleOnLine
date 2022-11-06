from __future__ import annotations

import os
import uuid
import base64
import json
import logging
from typing import Any, NamedTuple

import boto3


class EnvironParam(NamedTuple):
    LOG_LEVEL: str
    USER_TABLE_NAME: str
    USER_TABLE_PKEY: str
    USER_TABLE_SKEY: str
    RESULT_BUCKET_NAME: str
    RESULT_BUCKET_KEY: str
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
s3 = boto3.client("s3")


class BodySchema(NamedTuple):
    img_b64: str

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> BodySchema:
        body = json.loads(event["body"])
        return BodySchema(**{k: body[k] for k in BodySchema._fields})


class UDbInfoSchema(NamedTuple):
    room_id: str
    user_name: str

    @classmethod
    def from_db(cls, response: dict[str, Any]) -> UDbInfoSchema:
        return UDbInfoSchema(**{k: response["Item"][k] for k in UDbInfoSchema._fields})


class DoNotRetryException(Exception):
    ...


def upload_img(connection_id: str, img_b64: str) -> str:
    key = f"{ep.BUCKET_KEY}/{connection_id}/{uuid.uuid4()}.png"
    try:
        s3.put_object(
            Body=base64.b64decode(img_b64),
            Bucket=ep.BUCKET_NAME,
            Key=key,
        )
    except Exception as e:
        logger.exception("put_object")
        raise DoNotRetryException from e


def put_item(connection_id: str, body: BodySchema, key: str) -> None:
    try:
        user_table.put_item(
            Item={
                ep.USER_TABLE_PKEY: connection_id,
                ep.USER_TABLE_SKEY: "image",
                "key": key,
            }
        )
    except Exception as e:
        logger.exception("put_item")
        raise DoNotRetryException from e


def post_result(connection_id: str, key: str) -> None:
    try:
        apigw.post_to_connection(
            Data=f"画像を投稿しました: {key}".encode(),
            ConnectionId=connection_id,
        )
    except boto3.client.exceptions.GoneException:
        # 何らかの事情でDBに残っていても接続が切れている場合があるのでSkip
        logger.exception("warn")
    except Exception as e:
        logger.exception("delete_item_error")
        raise DoNotRetryException from e


def service(connection_id: str, body: BodySchema) -> None:
    key = upload_img(connection_id, body.img_b64)
    put_item(connection_id, body, key)
    post_result(connection_id, key)


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
