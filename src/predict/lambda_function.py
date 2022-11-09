from __future__ import annotations

import os
import csv
import uuid
import base64
import json
import logging
from typing import Any, NamedTuple

import boto3
import cv2
import numpy as np
from PIL import Image
from tensorflow.keras.models import load_model


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
reconstructed_model = load_model("model.h5")


class BodySchema(NamedTuple):
    img_b64: str
    odai: str
    is_fin: bool
    img_id: str

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
    key = f"{ep.RESULT_BUCKET_KEY}/{connection_id}/{uuid.uuid4()}.png"
    try:
        s3.put_object(
            Body=base64.b64decode(img_b64.split(",")[1]),
            Bucket=ep.RESULT_BUCKET_NAME,
            Key=key,
        )
        return key
    except Exception as e:
        logger.exception("put_object")
        raise DoNotRetryException from e


def put_item(connection_id: str, body: BodySchema, label_score_map: dict[str, float], key: str) -> None:
    try:
        user_table.put_item(
            Item={
                ep.USER_TABLE_PKEY: connection_id,
                ep.USER_TABLE_SKEY: body.img_id,
                "key": key,
                "score": label_score_map[body.odai],
            }
        )
    except Exception as e:
        logger.exception("put_item")
        raise DoNotRetryException from e


def post_result(connection_id: str, scores: list[dict[str, float]], command: str) -> None:
    try:
        apigw.post_to_connection(
            Data=json.dumps({"command": command, "scores": scores[:5]}).encode(),
            ConnectionId=connection_id,
        )
    except boto3.client.exceptions.GoneException:
        # 何らかの事情でDBに残っていても接続が切れている場合があるのでSkip
        logger.exception("warn")
    except Exception as e:
        logger.exception("delete_item_error")
        raise DoNotRetryException from e


def preprocessing(img_b64: str) -> numpy.array:
    # いったん保存する(それ以外の方法で画像を読み込むやり方が分からなかった)
    path = f"/tmp/{uuid.uuid4()}.png"
    with open(path, "wb") as f:
        f.write(base64.b64decode(img_b64.split(",")[1]))
    # 読み込み
    img = Image.open(path)
    # 画像の切り抜き
    img = img.crop(img.getbbox())
    # グレースケール化
    img = np.array(img)[:,:,3]
    # 画像のリサイズ
    x, y = img.shape
    if x < y:
        img = cv2.resize(img, (26, min(x*26//y+1, 26)))
    else:
        img = cv2.resize(img,(min(y*26//x+1, 26), 26))
    # 28*28の背景にリサイズした画像を張り付け
    img_back = np.zeros((28, 28), np.uint8)
    x, y = img.shape
    for i in range(x):
        for j in range(y):
            img_back[i+(28-x)//2][j+(28-y)//2] += img[i][j]
    img = img_back
    # 正規化
    img = img / 255.
    return img


def get_index_label_map() -> dict[int, str]:
    with open("label.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        index_label_map = {int(l[1]): l[0] for i, l in enumerate(reader) if i != 0}
    with open("en2jp.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        en2jp = {l[0]: l[1] for l in reader}
    return {k: en2jp.get(v, v) for k, v in index_label_map.items()}


def predict(img_b64: str) -> tuple(dict[str, float], list[dict[str, float]]):
    img = preprocessing(img_b64)
    result = reconstructed_model.predict(img.reshape(1, 28, 28))
    index_score_map = dict(zip(range(len(result[0])), result[0]*10000))
    index_label_map = get_index_label_map()
    label_score_map = {index_label_map[k]: v for k, v in index_score_map.items()}
    scores = [{"key": {index_label_map[x[0]]}, "value": {x[1]:.3}} for x in sorted(index_score_map.items(), key=lambda x: x[1], reverse=True)]
    return (label_score_map, scores)


def service(connection_id: str, body: BodySchema) -> None:
    label_score_map, scores = predict(body.img_b64)
    if body.is_fin:
        key = upload_img(connection_id, body.img_b64)
        put_item(connection_id, body, label_score_map, key)
        post_result(connection_id, scores, "img_save")
    else:
        post_result(connection_id, scores, "predict")


def lambda_handler(event, context):
    logger.info(json.dumps(event, indent=2))
    for record in event["Records"]:
        body = json.loads(record["body"])
        try:
            service(body["requestContext"]["connectionId"], BodySchema.from_event(body))
        except:
            logger.exception("ERROR")
            return {
                "statusCode": 500,
            }
    return {
                "statusCode": 200,
            }

