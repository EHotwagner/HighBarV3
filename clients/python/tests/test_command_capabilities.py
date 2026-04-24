# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

from highbar_client.highbar import commands_pb2, service_pb2


def test_schema_capability_message_shape():
    schema = service_pb2.CommandSchemaResponse(
        schema_version="1.0.0",
        feature_flags=["protobuf_proxy_safety", "command_capabilities"],
        supported_command_arms=["move_unit", "stop", "build_unit"],
        validation_mode=commands_pb2.VALIDATION_MODE_STRICT,
        max_batch_commands=64,
        queue_depth=1,
        queue_capacity=1024,
    )
    schema.option_masks.add(command_arm="move_unit", valid_option_mask=0x7)

    assert "command_capabilities" in schema.feature_flags
    assert "move_unit" in schema.supported_command_arms
    assert schema.option_masks[0].valid_option_mask == 0x7


def test_unit_capability_message_shape():
    caps = service_pb2.UnitCapabilitiesResponse(unit_id=42)
    caps.generation.unit_id = 42
    caps.generation.generation = 3
    caps.legal_command_arms.extend(["move_unit", "stop"])
    caps.feature_flags.append("dry_run_validation")

    assert caps.unit_id == 42
    assert caps.generation.generation == 3
    assert list(caps.legal_command_arms) == ["move_unit", "stop"]
    assert "dry_run_validation" in caps.feature_flags
