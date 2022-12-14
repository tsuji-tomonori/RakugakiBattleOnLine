from __future__ import annotations

from aws_cdk import (
    Stack,
    Tags,
    CfnOutput,
)
from aws_cdk.aws_apigatewayv2_integrations_alpha import WebSocketLambdaIntegration
from aws_cdk.aws_apigatewayv2_alpha import(
    WebSocketApi,
    WebSocketStage,
    WebSocketRouteOptions,
)
from constructs import Construct

from cdk.construct import *


class RakugakiBattleOnLine(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        on_connect = PythonLambdaWithoutLayer(self, "on_connect")
        enter_room = PythonLambdaWithoutLayer(self, "enter_room")
        dis_connect = PythonLambdaWithoutLayer(self, "dis_connect")
        predict = DockerLambdaWithoutLayer(self, "predict")
        predict_queue = LambdaToSqsToLambda(self, "predict_queue", predict.fn)
        start_game = PythonLambdaWithoutLayer(self, "start_game")

        for construst in [on_connect, enter_room, dis_connect, predict, predict_queue, start_game]:
            Tags.of(construst).add("Construct", construst.node.id)

        user = CreateDbAndSetEnvToFn(self, "user", [on_connect.fn, enter_room.fn, dis_connect.fn, predict.fn])
        user.db.grant_write_data(on_connect.fn.role)
        user.db.grant_read_write_data(enter_room.fn.role)
        user.db.grant_full_access(dis_connect.fn.role)
        user.db.grant_write_data(predict.fn.role)

        room = CreateDbAndSetEnvToFn(self, "room", [enter_room.fn, dis_connect.fn, start_game.fn])
        room.db.grant_read_write_data(enter_room.fn.role)
        room.db.grant_full_access(dis_connect.fn.role)
        room.db.grant_read_data(start_game.fn.role)

        result = CreateBucketAndSetEnvToFn(self, "result", [predict.fn])
        result.bucket.grant_put(predict.fn.role)

        api = WebSocketApi(
            self, "RakugakiBattleOnLineApi",
            route_selection_expression="$request.body.action",
            connect_route_options=WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration("on_connect_integration", handler=on_connect.fn)
            ),
            disconnect_route_options=WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration("dis_connect_integration", handler=dis_connect.fn)
            ),
            api_name="rakugaki_battle_online",
        )
        api.add_route(
            route_key="enter_room",
            integration=WebSocketLambdaIntegration("enter_room_integration", enter_room.fn)
        )
        api.add_route(
            route_key="predict",
            integration=WebSocketLambdaIntegration("predict_integration", predict_queue.fn),
        )
        api.add_route(
            route_key="start_game",
            integration=WebSocketLambdaIntegration("start_game_integration", start_game.fn),
        )
        api.grant_manage_connections(enter_room.fn.role)
        api.grant_manage_connections(dis_connect.fn.role)
        api.grant_manage_connections(predict.fn.role)
        api.grant_manage_connections(start_game.fn.role)

        prod = WebSocketStage(
            self, "ProdApi",
            stage_name="prod",
            auto_deploy=True,
            web_socket_api=api,
        )
        endpoint = f"https://{api.api_id}.execute-api.{api.env.region}.amazonaws.com/{prod.stage_name}"
        enter_room.fn.add_environment("ENDPOINT_URL", endpoint)
        dis_connect.fn.add_environment("ENDPOINT_URL", endpoint)
        predict.fn.add_environment("ENDPOINT_URL", endpoint)
        start_game.fn.add_environment("ENDPOINT_URL", endpoint)

        StaticWebSite(self, "rakugaki-battle-online")

        CfnOutput(
            self, "WebSocketURI",
            value=prod.url,
            description="The WSS Protocol URI to connect to",
        )