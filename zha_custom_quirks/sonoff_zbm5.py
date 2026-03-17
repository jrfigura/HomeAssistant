"""Custom ZHA quirk for Sonoff ZBM5 series wall switches.

Supported models (confirmed from ZHA diagnostics):
  ZBM5-1C-80/86   — 1 gang
  ZBM5-2C-80/86   — 2 gang  (diagnostics verified, HA 2026.3.1)
  ZBM5-3C-80/86   — 3 gang  (diagnostics verified, HA 2026.3.1)

Manufacturer: SONOFF

=== CLUSTER LAYOUT (confirmed from diagnostics) ===

  EP1: 0x0000 Basic, 0x0003 Identify, 0x0004 Groups, 0x0005 Scenes,
       0x0006 OnOff, 0x0020 PollControl, 0x0b05 Diagnostic,
       0xfc11 SonoffPrivate ← detach relay lives here
       0xfc57 (unknown, no attributes)
  EP2: 0x0000, 0x0003, 0x0004, 0x0005, 0x0006, 0xfc57
  EP3: 0x0000, 0x0003, 0x0004, 0x0005, 0x0006, 0xfc57  (3-gang only)

0xfc11 is ONLY on EP1 — confirmed across both 2-gang and 3-gang devices.
This is intentional: Sonoff uses a single cluster for device-level settings.
Per-channel detach relay is controlled by separate attributes within 0xfc11.

=== CLUSTER 0xFC11 — SONOFF PRIVATE ===

Attribute 0x0001 — detach_relay_ch1  (channel 1 / EP1)
Attribute 0x0002 — detach_relay_ch2  (channel 2 / EP2)
Attribute 0x0003 — detach_relay_ch3  (channel 3 / EP3)
  Values: 0x00 = Attached (button controls relay, default)
          0x01 = Detached (relay stays on, button fires toggle event)

NOTE: Attribute IDs 0x0002 and 0x0003 are inferred from the Sonoff
ZBMINIR2 / ZBM5 pattern. They need to be verified by testing.
If the select entities for ch2/ch3 don't work, share your diagnostics
after connecting neutral wire (which exposes more attribute data).

=== REQUIREMENTS ===

With neutral wire:    Detach relay works ✅ | Device is Zigbee Router ✅
Without neutral wire: Detach relay unavailable ❌ | Device is EndDevice

The quirk installs and creates entities either way, but writing detach
relay attributes will only take effect with neutral wire connected.

=== WHAT THIS QUIRK ADDS ===

Per-channel "Detach relay" select entities:
  select.<device>_detach_relay      — channel 1
  select.<device>_detach_relay_2    — channel 2 (2/3-gang only)
  select.<device>_detach_relay_3    — channel 3 (3-gang only)
Options: "Attached" (default) / "Detached"

=== BUTTON EVENTS IN DETACH MODE ===

When a channel is set to Detached, pressing the button fires a standard
ZCL OnOff TOGGLE command on the corresponding endpoint. Unlike Aqara H1
(which uses MultistateInput), this is a native ZCL command — it appears
automatically as a ZHA device trigger in the HA automation UI.

  event_type: zha_event
  event_data:
    device_ieee: "xx:xx:xx:xx:xx:xx:xx:xx"
    endpoint_id: 1   # channel 1
    endpoint_id: 2   # channel 2
    endpoint_id: 3   # channel 3
    cluster_id: 6    # 0x0006 OnOff
    command: toggle
    args: {}

=== AUTOMATION TRIGGER ===

Option A — device trigger (recommended, available in HA UI):
  trigger:
    - platform: device
      device_id: <your device id>
      domain: zha
      type: remote_button_short_press
      subtype: turn_on

Option B — raw zha_event:
  trigger:
    - platform: event
      event_type: zha_event
      event_data:
        device_ieee: "xx:xx:xx:xx:xx:xx:xx:xx"
        endpoint_id: 1    # 1, 2, or 3
        cluster_id: 6
        command: toggle

=== IMPORTANT: RELAY STAYS ON ===

When Detached, the relay no longer follows the button. Make sure the
relay entity (switch.<device>_przelacznik / _2 / _3) is ON and hide it
from the UI to prevent accidentally cutting power to smart bulbs.

=== INSTALLATION ===

1. Copy to /config/custom_zha_quirks/sonoff_zbm5.py
2. Full Home Assistant restart (not just ZHA reload)
3. Open device page → Reconfigure
4. "Detach relay" select entities appear per channel
5. Set desired channel(s) to "Detached"
6. Keep relay entities ON and hide them from UI
"""

from __future__ import annotations

import zigpy.types as t
from zigpy.quirks.v2 import QuirkBuilder
from zigpy.zcl.clusters.manufacturer_specific import ManufacturerSpecificCluster


SONOFF_MFR_CODE = 0x1286  # 4742 decimal


class SonoffDetachRelayMode(t.enum8):
    """Values for detach_relay attributes in cluster 0xFC11."""

    Attached = 0x00   # button controls relay directly (default)
    Detached = 0x01   # relay stays on, button fires toggle event on its EP


class SonoffPrivateCluster(ManufacturerSpecificCluster):
    """Sonoff private cluster 0xFC11.

    Present on EP1 only. Controls per-channel settings for all channels.
    Confirmed on ZBM5-2C-80/86 and ZBM5-3C-80/86.
    """

    cluster_id = 0xFC11
    name = "SonoffPrivate"
    ep_attribute = "sonoff_private"

    attributes = {
        0x0001: ("detach_relay_ch1", t.uint8_t, True),
        0x0002: ("detach_relay_ch2", t.uint8_t, True),
        0x0003: ("detach_relay_ch3", t.uint8_t, True),
    }

    async def async_initialize_cluster_handler_specific(self, from_cache: bool) -> None:
        """Read detach_relay attributes on startup so select entities are not unavailable."""
        await super().async_initialize_cluster_handler_specific(from_cache)
        try:
            await self.read_attributes(
                [0x0001, 0x0002, 0x0003],
                allow_cache=False,
                only_cache=False,
                manufacturer=SONOFF_MFR_CODE,
            )
        except Exception:
            pass


# ─── 1-gang: ZBM5-1C-80/86 ───────────────────────────────────────────────────
(
    QuirkBuilder("SONOFF", "ZBM5-1C-80/86")
    .replaces(SonoffPrivateCluster, endpoint_id=1)
    .enum(
        attribute_name="detach_relay_ch1",
        cluster_id=SonoffPrivateCluster.cluster_id,
        endpoint_id=1,
        enum_class=SonoffDetachRelayMode,
        translation_key="detach_relay",
        fallback_name="Detach relay",
    )
    .add_to_registry()
)


# ─── 2-gang: ZBM5-2C-80/86 ───────────────────────────────────────────────────
(
    QuirkBuilder("SONOFF", "ZBM5-2C-80/86")
    .replaces(SonoffPrivateCluster, endpoint_id=1)
    .enum(
        attribute_name="detach_relay_ch1",
        cluster_id=SonoffPrivateCluster.cluster_id,
        endpoint_id=1,
        enum_class=SonoffDetachRelayMode,
        translation_key="detach_relay",
        fallback_name="Detach relay ch1",
    )
    .enum(
        attribute_name="detach_relay_ch2",
        cluster_id=SonoffPrivateCluster.cluster_id,
        endpoint_id=1,
        enum_class=SonoffDetachRelayMode,
        translation_key="detach_relay_2",
        fallback_name="Detach relay ch2",
    )
    .add_to_registry()
)


# ─── 3-gang: ZBM5-3C-80/86 ───────────────────────────────────────────────────
(
    QuirkBuilder("SONOFF", "ZBM5-3C-80/86")
    .replaces(SonoffPrivateCluster, endpoint_id=1)
    .enum(
        attribute_name="detach_relay_ch1",
        cluster_id=SonoffPrivateCluster.cluster_id,
        endpoint_id=1,
        enum_class=SonoffDetachRelayMode,
        translation_key="detach_relay",
        fallback_name="Detach relay ch1",
    )
    .enum(
        attribute_name="detach_relay_ch2",
        cluster_id=SonoffPrivateCluster.cluster_id,
        endpoint_id=1,
        enum_class=SonoffDetachRelayMode,
        translation_key="detach_relay_2",
        fallback_name="Detach relay ch2",
    )
    .enum(
        attribute_name="detach_relay_ch3",
        cluster_id=SonoffPrivateCluster.cluster_id,
        endpoint_id=1,
        enum_class=SonoffDetachRelayMode,
        translation_key="detach_relay_3",
        fallback_name="Detach relay ch3",
    )
    .add_to_registry()
)
