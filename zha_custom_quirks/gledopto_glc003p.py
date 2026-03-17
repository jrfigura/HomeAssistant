"""GLEDOPTO GL-C-003P device quirk - RGB Mode."""

from zigpy.profiles import zha
from zigpy.quirks import CustomCluster, CustomDevice
from zigpy.zcl.clusters.general import (
    Basic,
    Groups,
    Identify,
    LevelControl,
    OnOff,
    Ota,
    Scenes,
)
from zigpy.zcl.clusters.lighting import Color
from zigpy.zcl.clusters.lightlink import LightLink
from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    MODELS_INFO,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
)
from zhaquirks.gledopto import GLEDOPTO

class GledoptoRGBCluster(CustomCluster, Color):
    """Custom Color cluster for GL-C-003P RGB mode."""
    cluster_id = Color.cluster_id
    
    # Force RGB-only support using XY and HS color modes
    _CONSTANT_ATTRIBUTES = {
        # ColorCapabilities: 0x0019 = 25 decimal
        # Bit 0 (Hue/Sat) + Bit 3 (XY) + Bit 4 (Enhanced Hue) = 0b11001 = 25
        0x400A: 25,
        # ColorMode: 1 = Current hue and saturation
        0x0008: 1,
    }

class GLC003P(CustomDevice):
    """GLEDOPTO GL-C-003P RGB mode device."""

    signature = {
        MODELS_INFO: [(GLEDOPTO, "GL-C-003P")],
        ENDPOINTS: {
            11: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: 0x0102,  # Color Dimmable Light
                INPUT_CLUSTERS: [
                    Basic.cluster_id,       # 0x0000
                    Identify.cluster_id,    # 0x0003
                    Groups.cluster_id,      # 0x0004
                    Scenes.cluster_id,      # 0x0005
                    OnOff.cluster_id,       # 0x0006
                    LevelControl.cluster_id,# 0x0008
                    Color.cluster_id,       # 0x0300
                    0x1000,                 # ZLL Commissioning
                ],
                OUTPUT_CLUSTERS: [
                    Ota.cluster_id,         # 0x0019
                ],
            },
        },
    }

    replacement = {
        ENDPOINTS: {
            11: {
                PROFILE_ID: zha.PROFILE_ID,
                # Use Extended Color Light to support both XY and HS
                #DEVICE_TYPE: zha.DeviceType.EXTENDED_COLOR_LIGHT,
                DEVICE_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT ,
                INPUT_CLUSTERS: [
                    Basic.cluster_id,
                    Identify.cluster_id,
                    Groups.cluster_id,
                    Scenes.cluster_id,
                    OnOff.cluster_id,
                    LevelControl.cluster_id,
                    GledoptoRGBCluster,  # Custom cluster for proper RGB support
                ],
                OUTPUT_CLUSTERS: [
                    Ota.cluster_id,
                ],
            },
        },
    }
