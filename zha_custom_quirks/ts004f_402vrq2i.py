"""Tuya TS004F rotary button custom quirk."""

from __future__ import annotations

from zigpy.profiles import zha
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Identify,
    LevelControl,
    OnOff,
    Ota,
    PowerConfiguration,
    Scenes,
    Time,
)
from zigpy.zcl.clusters.lighting import Color
from zigpy.zcl.clusters.lightlink import LightLink

from zhaquirks.const import (
    BUTTON,
    BUTTON_1,
    CLUSTER_ID,
    COMMAND,
    COMMAND_STEP,
    COMMAND_STEP_COLOR_TEMP,
    COMMAND_TOGGLE,
    DEVICE_TYPE,
    DIM_DOWN,
    DIM_UP,
    DOUBLE_PRESS,
    ENDPOINT_ID,
    ENDPOINTS,
    INPUT_CLUSTERS,
    LEFT,
    LONG_PRESS,
    MODEL,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PARAMS,
    PROFILE_ID,
    RIGHT,
    ROTATED,
    SHORT_PRESS,
)
from zhaquirks.tuya import (
    EnchantedDevice,
    TuyaNoBindPowerConfigurationCluster,
    TuyaSmartRemoteOnOffCluster,
)


class TuyaSmartRemote004FRotaryDimmer(EnchantedDevice):
    """Tuya TS004F rotary encoder remote, _TZ3000_402vrq2i variant."""

    signature = {
        MODELS_INFO: [
            ("_TZ3000_402vrq2i", "TS004F")
        ],
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.DIMMER_SWITCH,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    PowerConfiguration.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    OnOff.cluster_id,
                    LightLink.cluster_id,
                ],
                OUTPUT_CLUSTERS: [
                    Ota.cluster_id,
                    Time.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    OnOff.cluster_id,
                    LevelControl.cluster_id,
                    LightLink.cluster_id,
                ],
            },
        },
    }

    replacement = {
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.NON_COLOR_CONTROLLER,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    TuyaNoBindPowerConfigurationCluster,
                    Identify.cluster_id,
                    LightLink.cluster_id,
                ],
                OUTPUT_CLUSTERS: [
                    Ota.cluster_id,
                    Time.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    TuyaSmartRemoteOnOffCluster,
                    LevelControl.cluster_id,
                    Color.cluster_id,
                    LightLink.cluster_id,
                ],
            },
        },
    }

    device_automation_triggers = {
        # --- Dimmer / Remote mode ---
        (SHORT_PRESS, BUTTON): {
            COMMAND: COMMAND_TOGGLE,
            ENDPOINT_ID: 1,
            CLUSTER_ID: 6
        },
        (ROTATED, DIM_UP): {
            COMMAND: COMMAND_STEP,
            ENDPOINT_ID: 1,
            CLUSTER_ID: 8,
            PARAMS: {"step_mode": 0},
        },
        (ROTATED, DIM_DOWN): {
            COMMAND: COMMAND_STEP,
            ENDPOINT_ID: 1,
            CLUSTER_ID: 8,
            PARAMS: {"step_mode": 1},
        },
        (ROTATED, RIGHT): {
            COMMAND: COMMAND_STEP_COLOR_TEMP,
            ENDPOINT_ID: 1,
            CLUSTER_ID: 768,
            PARAMS: {"step_mode": 1},
        },
        (ROTATED, LEFT): {
            COMMAND: COMMAND_STEP_COLOR_TEMP,
            ENDPOINT_ID: 1,
            CLUSTER_ID: 768,
            PARAMS: {"step_mode": 3},
        },

        # --- Scene mode ---
        (SHORT_PRESS, BUTTON_1): {
            ENDPOINT_ID: 1,
            COMMAND: SHORT_PRESS
        },
        (DOUBLE_PRESS, BUTTON_1): {
            ENDPOINT_ID: 1,
            COMMAND: DOUBLE_PRESS
        },
        (LONG_PRESS, BUTTON_1): {
            ENDPOINT_ID: 1,
            COMMAND: LONG_PRESS
        },
        (SHORT_PRESS, RIGHT): {
            COMMAND: RIGHT,
            ENDPOINT_ID: 1,
            CLUSTER_ID: 6,
        },
        (SHORT_PRESS, LEFT): {
            COMMAND: LEFT,
            ENDPOINT_ID: 1,
            CLUSTER_ID: 6,
        },
    }