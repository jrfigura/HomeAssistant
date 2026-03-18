"""Custom ZHA quirk for Aqara Smart Wall Switch H1 EU (WS-EUK02, no-neutral).

Device:       Aqara Smart Wall Switch H1 EU (no neutral, double rocker)
Model:        lumi.switch.l2aeu1
Manufacturer: LUMI
Tested on:    HA 2026.3.1 + ZHA

=== PROBLEM THIS SOLVES ===

The built-in ZHA quirk (AqaraH1DoubleRockerSwitchNoNeutral) handles the relays
and power metering fine, but has two gaps:

1. No way to set decoupled (detached) mode per button via the HA UI.
   In decoupled mode the physical button fires Zigbee events but does NOT
   toggle its relay — ideal for controlling smart bulbs while keeping power on.

2. In decoupled mode, button presses are silently dropped by ZHA.
   The device sends attribute_updated on the MultistateInput cluster (0x0012)
   on EP41 (button 1) and EP42 (button 2), but no cluster handler listens
   for these and emits them as zha_event.

=== WHAT THIS QUIRK ADDS ===

1. OppleSwitchClusterWithInit (EP1 + EP2)
   Subclass of OppleSwitchCluster (0xFCC0) that overrides
   async_initialize_cluster_handler_specific() to explicitly read the
   operation_mode attribute (0x0200) from the device on HA startup and after
   Reconfigure. Without this, QuirkBuilder.enum() creates the select entity
   but it stays "unavailable" forever because EndDevices don't self-report
   manufacturer-specific clusters.

2. MultistateInputEventCluster (EP41 + EP42 + EP51)
   Subclass of MultistateInput that intercepts _update_attribute() for
   present_value (attr 0x0055) and fires it as zha_event via
   listener_event("zha_send_event", ...). This makes button presses visible
   to HA automations when a button is in decoupled mode.
   EP51 = both buttons pressed simultaneously.

3. Two select entities via QuirkBuilder.enum():
   - select.<device>_operation_mode    -> EP1 (left/top rocker)
   - select.<device>_operation_mode_2  -> EP2 (right/bottom rocker)
   Options: "Attached" (default) / "Detached"

=== ENDPOINT MAP (from upstream zhaquirks signature) ===

  EP1:  OnOff relay 1, MultistateInput, OppleSwitchCluster (0xFCC0)
  EP2:  OnOff relay 2, MultistateInput, OppleSwitchCluster (0xFCC0)
  EP41: MultistateInput -> button 1 press events (decoupled mode)
  EP42: MultistateInput -> button 2 press events (decoupled mode)
  EP51: MultistateInput -> both buttons pressed simultaneously
  EP242: GreenPowerProxy

=== ZHA EVENTS FIRED (decoupled mode) ===

  event_type: zha_event
  event_data:
    device_ieee: <your device IEEE>
    endpoint_id: 41   # button 1 (left/top)  -- or 42 / 51
    cluster_id: 18    # 0x0012 MultistateInput
    command: attribute_updated
    args:
      attribute_id: 85
      attribute_name: present_value
      value: 1        # 1 = single press, 2 = double press, 3 = hold

=== AUTOMATION TRIGGER EXAMPLE ===

  trigger:
    - platform: event
      event_type: zha_event
      event_data:
        device_ieee: "xx:xx:xx:xx:xx:xx:xx:xx"   # your device IEEE
        endpoint_id: 42                            # 41=button1, 42=button2, 51=both
        command: attribute_updated
        args:
          value: 1                                 # 1=single, 2=double, 3=hold

=== IMPORTANT: RELAY STAYS ON ===

When a button is set to Detached, its relay no longer responds to the button.
The relay entity (light.<device>_swiatlo / light.<device>_swiatlo_2) must stay
ON and should be hidden in the entity registry so it cannot be accidentally
switched off, which would cut power to the smart bulb.

=== INSTALLATION ===

1. Copy this file to /config/custom_zha_quirks/aqara_h1_l2aeu1.py
2. Full Home Assistant restart (not just ZHA reload)
3. Open the device page -> Reconfigure
4. The two Operation mode select entities should now show "Attached"
5. Set the desired button to "Detached"
6. Create an automation using the trigger format above

=== NOTE ON ALTERNATIVE FIRMWARE (AqaraH1DoubleRockerSwitchNoNeutralAlt) ===

Some devices with the same model string lumi.switch.l2aeu1 have a different
endpoint layout (no EP41/EP42/EP51, no 0xFCC0). Those match the upstream
AqaraH1DoubleRockerSwitchNoNeutralAlt quirk and do not support decoupled mode
via cluster attributes. This quirk will not match those devices.
"""

from __future__ import annotations

import zigpy.types as t
from zhaquirks.xiaomi.aqara.opple_switch import OppleSwitchCluster
from zigpy.quirks.v2 import QuirkBuilder
from zigpy.zcl.clusters.general import MultistateInput

LUMI_MFR_CODE = 0x115F
OPERATION_MODE_ATTR = 0x0200


class AqaraOperationMode(t.enum8):
    """Operation mode for Aqara H1 EU switch.

    Uses Attached/Detached terminology consistent with Sonoff ZBM5 quirk
    and general industry convention, instead of the upstream Coupled/Decoupled.
      Attached = button controls relay directly (default)
      Detached = relay stays on, button fires zha_event
    """

    Detached = 0x00
    Attached = 0x01


class OppleSwitchClusterWithInit(OppleSwitchCluster):
    """OppleSwitchCluster that reads operation_mode on ZHA initialization.

    Without this override, QuirkBuilder.enum() creates the select entity
    but ZHA never reads the attribute value -- it stays "unavailable" forever
    on this EndDevice because manufacturer-specific clusters don't self-report.
    """

    async def async_initialize_cluster_handler_specific(self, from_cache: bool) -> None:
        """Read operation_mode from device on startup / after Reconfigure."""
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
    """MultistateInput cluster that emits zha_event on button press.

    In decoupled mode the device sends attribute_updated on present_value:
      1 = single press
      2 = double press
      3 = long press / hold

    Without this override ZHA silently processes the attribute update
    but never surfaces it as a zha_event for automations to use.

    handle_cluster_request is preserved as a pass-through to parent to ensure
    any cluster commands are still forwarded correctly.
    """

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
        """Intercept attribute updates and fire zha_event for present_value."""
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
    # Read operation_mode on startup so select entities are not stuck "unavailable"
    .replaces(OppleSwitchClusterWithInit, endpoint_id=1)
    .replaces(OppleSwitchClusterWithInit, endpoint_id=2)
    # Emit zha_event when a button is pressed in decoupled mode
    # EP41 = button 1, EP42 = button 2, EP51 = both buttons simultaneously
    .replaces(MultistateInputEventCluster, endpoint_id=41)
    .replaces(MultistateInputEventCluster, endpoint_id=42)
    .replaces(MultistateInputEventCluster, endpoint_id=51)
    # Expose operation mode as select entities in the HA UI
    .enum(
        attribute_name="operation_mode",
        cluster_id=OppleSwitchCluster.cluster_id,
        endpoint_id=1,
        enum_class=AqaraOperationMode,
        translation_key="operation_mode",
        fallback_name="Operation mode button 1",
    )
    .enum(
        attribute_name="operation_mode",
        cluster_id=OppleSwitchCluster.cluster_id,
        endpoint_id=2,
        enum_class=AqaraOperationMode,
        translation_key="operation_mode",
        fallback_name="Operation mode button 2",
    )
    .add_to_registry()
)
