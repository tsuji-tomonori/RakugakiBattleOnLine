from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    Tags,
)

from cdk.stack import RakugakiBattleOnLine

app = cdk.App()
apigw_stack = RakugakiBattleOnLine(app, app.node.try_get_context("project_name"))
Tags.of(apigw_stack).add("Project", app.node.try_get_context("project_name"))
Tags.of(apigw_stack).add("Type", "Pro")
Tags.of(apigw_stack).add("Creator", "cdk")
app.synth()
