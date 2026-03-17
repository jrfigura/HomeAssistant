"""Custom ZHA quirk for Aqara Smart Wall Switch H1 EU (WS-EUK02, no-neutral).

Model:        lumi.switch.l2aeu1
Manufacturer: LUMI
HA version:   2026.3.1 (tested)

PURPOSE:
    1. Adds select entities for decoupled/relay operation mode per button
    2. Makes decoupled button presses fire zha_event so automations can use them

WHAT THE PROBLEM WAS:
    In decoupled mode, button presses fire attribute_updated on MultistateInput
    cluster (0x0012) on EP41 (button 1) and EP42 (button 2). The built-in quirk
    doesn't register these endpoints as event sources, so HA silently drops them.

    The solution: add a custom cluster handler for EP41/EP42 that calls
    ZHA_SEND_EVENT when the MultistateInput "present_value" attribute changes.
    Values: 1 = single press, 2 = double press, 3 = long press (hold).

ZHA EVENTS FIRED (when button is in decoupled mode):
    event_type: zha_event
    event_data:
      device_ieee: 54:ef:44:10:01:13:26:90
      endpoint_id: 41   # button 1 (left/top)
      cluster_id: 18    # 0x0012 MultistateInput
      command: attribute_updated
      args:
        attribute_id: 85   # present_value
        attribute_name: present_value
        value: 1           # 1=single, 2=double, 3=hold

AUTOMATION TRIGGER EXAMPLE:
    trigger:
      - platform: event
        event_type: zha_event
        event_data:
          device_ieee: "54:ef:44:10:01:13:26:90"
          endpoint_id: 41
          args:
            value: 1   # single press

INSTALLATION:
    Copy to /config/custom_zha_quirks/aqara_h1_l2aeu1.py
    Full HA restart, then Rekonfiguruj the device in ZHA.
"""

from __future__ import annotations

import zigpy.types as t
from zhaquirks.xiaomi.aqara.opple_switch import OppleSwitchCluster, OppleOperationMode
from zigpy.quirks.v2 import QuirkBuilder
from zigpy.zcl.clusters.general import MultistateInput

LUMI_MFR_CODE = 0x115F
OPERATION_MODE_ATTR = 0x0200


class OppleSwitchClusterWithInit(OppleSwitchCluster):
    """OppleSwitchCluster that reads operation_mode on ZHA initialization."""

    async def async_initialize_cluster_handler_specific(self, from_cache: bool) -> None:
        await super().async_initialize_cluster_handler_specific(from_cache)
        try:
            await self.read_attributes(
                [OPERATION_MODE_ATTR],
                allow_cache=False,
                only_cache=False,
                manufacturer=LUMI_MFR_CODE,
            )
        except Exception:
            pass


class MultistateInputEventCluster(MultistateInput):
    """MultistateInput cluster that fires ZHA events on attribute_updated.

    In decoupled mode, button presses update 'present_value':
      1 = single press
      2 = double press
      3 = long press / hold
    """

    # ZHA will call _update_attribute -> listeners -> send event
    # We need the cluster to be treated as an event source.
    # The magic: when present_value changes, the cluster handler sends a ZHA event.

    def handle_cluster_request(
        self,
        hdr: t.Struct,
        args: list,
        *,
        dst_addressing=None,
    ) -> None:
        """Pass through to parent."""
        super().handle_cluster_request(hdr, args, dst_addressing=dst_addressing)

    def _update_attribute(self, attrid: int, value: t.Any) -> None:
        """Intercept attribute updates and fire ZHA events for present_value."""
        super()._update_attribute(attrid, value)
        # present_value attribute id = 0x0055 = 85
        if attrid == 0x0055:
            self.listener_event(
                "zha_send_event",
                "attribute_updated",
                {
                    "attribute_id": attrid,
                    "attribute_name": "present_value",
                    "value": value,
                },
            )


(
    QuirkBuilder("LUMI", "lumi.switch.l2aeu1")
    # Fix operation_mode read on startup
    .replaces(OppleSwitchClusterWithInit, endpoint_id=1)
    .replaces(OppleSwitchClusterWithInit, endpoint_id=2)
    # Replace MultistateInput on EP41/EP42 with our event-emitting version
    .replaces(MultistateInputEventCluster, endpoint_id=41)
    .replaces(MultistateInputEventCluster, endpoint_id=42)
    # Expose operation mode as select entities
    .enum(
        attribute_name="operation_mode",
        cluster_id=OppleSwitchCluster.cluster_id,
        endpoint_id=1,
        enum_class=OppleOperationMode,
        translation_key="operation_mode",
        fallback_name="Tryb przycisku 1",
    )
    .enum(
        attribute_name="operation_mode",
        cluster_id=OppleSwitchCluster.cluster_id,
        endpoint_id=2,
        enum_class=OppleOperationMode,
        translation_key="operation_mode",
        fallback_name="Tryb przycisku 2",
    )
    .add_to_registry()
)
