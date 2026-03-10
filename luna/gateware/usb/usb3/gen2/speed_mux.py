#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""Speed multiplexer for Gen1/Gen2 data path selection.

Selects between the Gen1 (32-bit @ 125 MHz) and Gen2 (64-bit @ 156.25 MHz)
link layer paths based on the negotiated link speed.  The mux sits between
the link layers and the protocol layer::

    Gen1 Link Layer ──┐
                      ├── SpeedMux ──► Protocol Layer
    Gen2 Link Layer ──┘

Header packets use the same 96-bit format in both generations, so they are
muxed directly.  Data packets differ in width (32-bit Gen1 vs 64-bit Gen2),
so the mux exposes separate Gen1/Gen2 data interfaces to the protocol layer
and only activates the one corresponding to the current speed.

All muxing is purely combinational — no clock-domain crossing is performed
here (CDC is handled elsewhere).
"""

from amaranth import *

from ...stream import SuperSpeedStreamInterface
from .interfaces import Gen2SuperSpeedStreamInterface


class SpeedMux(Elaboratable):
    """Multiplexes between Gen1 and Gen2 link layer paths.

    Based on the ``use_gen2`` control signal, routes header packets, data
    packets, link commands, and status signals between the appropriate link
    layer and the protocol layer.

    For the initial implementation this module provides separate Gen1 and
    Gen2 data interfaces to the protocol layer, since the data widths differ
    (32-bit vs 64-bit).  Header packets use the same 96-bit format in both
    generations and are therefore unified.

    Attributes
    ----------
    use_gen2 : Signal, in
        When high, routes traffic through the Gen2 path.  When low, uses Gen1.

    gen1_link_ready : Signal, in
        Gen1 link layer ready/trained status.
    gen1_header_source_valid : Signal, in
        Gen1 link layer has a new header packet.
    gen1_header_source_data : Signal(96), in
        Gen1 header packet payload (12 bytes).
    gen1_header_source_crc_good : Signal, in
        Gen1 header CRC validated.
    gen1_data_source : SuperSpeedStreamInterface (32-bit), in
        Gen1 received data stream.
    gen1_data_packet_good : Signal, in
        Gen1 data packet CRC good.
    gen1_data_packet_bad : Signal, in
        Gen1 data packet CRC bad.
    gen1_header_sink_data : Signal(96), out
        Header data routed to Gen1 link layer for TX.
    gen1_header_sink_send : Signal, out
        Trigger Gen1 header transmission.
    gen1_header_sink_busy : Signal, in
        Gen1 header TX busy.
    gen1_data_sink : SuperSpeedStreamInterface (32-bit), out
        Data stream routed to Gen1 link layer for TX.
    gen1_link_command_valid : Signal, in
        Gen1 link command received.
    gen1_link_command : Signal(11), in
        Gen1 received link command.
    gen1_link_command_to_send : Signal(11), out
        Link command routed to Gen1 for TX.
    gen1_link_command_send : Signal, out
        Trigger Gen1 link command TX.
    gen1_link_command_busy : Signal, in
        Gen1 link command TX busy.

    gen2_link_ready : Signal, in
        Gen2 link layer ready/trained status.
    gen2_header_source_valid : Signal, in
        Gen2 link layer has a new header packet.
    gen2_header_source_data : Signal(96), in
        Gen2 header packet payload (12 bytes).
    gen2_header_source_crc_good : Signal, in
        Gen2 header CRC validated.
    gen2_data_source : Gen2SuperSpeedStreamInterface (64-bit), in
        Gen2 received data stream.
    gen2_data_packet_good : Signal, in
        Gen2 data packet CRC good.
    gen2_data_packet_bad : Signal, in
        Gen2 data packet CRC bad.
    gen2_header_sink_data : Signal(96), out
        Header data routed to Gen2 link layer for TX.
    gen2_header_sink_send : Signal, out
        Trigger Gen2 header transmission.
    gen2_header_sink_busy : Signal, in
        Gen2 header TX busy.
    gen2_data_sink : Gen2SuperSpeedStreamInterface (64-bit), out
        Data stream routed to Gen2 link layer for TX.
    gen2_link_command_valid : Signal, in
        Gen2 link command received.
    gen2_link_command : Signal(11), in
        Gen2 received link command.
    gen2_link_command_to_send : Signal(11), out
        Link command routed to Gen2 for TX.
    gen2_link_command_send : Signal, out
        Trigger Gen2 link command TX.
    gen2_link_command_busy : Signal, in
        Gen2 link command TX busy.

    link_ready : Signal, out
        Unified link ready status from the active link layer.
    header_rx_valid : Signal, out
        A new header packet is available from the active link layer.
    header_rx_data : Signal(96), out
        Header packet payload from the active link layer.
    header_rx_crc_good : Signal, out
        Header CRC status from the active link layer.
    header_tx_data : Signal(96), in
        Header packet payload from the protocol layer for TX.
    header_tx_send : Signal, in
        Protocol layer requests header transmission.
    header_tx_busy : Signal, out
        Header TX busy from the active link layer.

    gen1_data_rx : SuperSpeedStreamInterface (32-bit), out
        Gen1 data received — active when ``use_gen2`` is low.
    gen2_data_rx : Gen2SuperSpeedStreamInterface (64-bit), out
        Gen2 data received — active when ``use_gen2`` is high.
    data_rx_packet_good : Signal, out
        Data packet CRC good from the active link layer.
    data_rx_packet_bad : Signal, out
        Data packet CRC bad from the active link layer.
    gen1_data_tx : SuperSpeedStreamInterface (32-bit), in
        Gen1 data to transmit — active when ``use_gen2`` is low.
    gen2_data_tx : Gen2SuperSpeedStreamInterface (64-bit), in
        Gen2 data to transmit — active when ``use_gen2`` is high.

    link_command_rx_valid : Signal, out
        A new link command is available from the active link layer.
    link_command_rx : Signal(11), out
        Link command from the active link layer.
    link_command_tx : Signal(11), in
        Link command from the protocol layer for TX.
    link_command_tx_send : Signal, in
        Protocol layer requests link command transmission.
    link_command_tx_busy : Signal, out
        Link command TX busy from the active link layer.
    """

    def __init__(self):
        # ── Control ──────────────────────────────────────────────────
        self.use_gen2 = Signal()

        # ── Gen1 link layer connections ──────────────────────────────
        self.gen1_link_ready            = Signal()

        # Gen1 header RX (from Gen1 link layer)
        self.gen1_header_source_valid   = Signal()
        self.gen1_header_source_data    = Signal(96)
        self.gen1_header_source_crc_good = Signal()

        # Gen1 data RX (from Gen1 link layer)
        self.gen1_data_source           = SuperSpeedStreamInterface()
        self.gen1_data_packet_good      = Signal()
        self.gen1_data_packet_bad       = Signal()

        # Gen1 header TX (to Gen1 link layer)
        self.gen1_header_sink_data      = Signal(96)
        self.gen1_header_sink_send      = Signal()
        self.gen1_header_sink_busy      = Signal()

        # Gen1 data TX (to Gen1 link layer)
        self.gen1_data_sink             = SuperSpeedStreamInterface()

        # Gen1 link commands RX (from Gen1 link layer)
        self.gen1_link_command_valid    = Signal()
        self.gen1_link_command          = Signal(11)

        # Gen1 link commands TX (to Gen1 link layer)
        self.gen1_link_command_to_send  = Signal(11)
        self.gen1_link_command_send     = Signal()
        self.gen1_link_command_busy     = Signal()

        # ── Gen2 link layer connections ──────────────────────────────
        self.gen2_link_ready            = Signal()

        # Gen2 header RX (from Gen2 link layer)
        self.gen2_header_source_valid   = Signal()
        self.gen2_header_source_data    = Signal(96)
        self.gen2_header_source_crc_good = Signal()

        # Gen2 data RX (from Gen2 link layer)
        self.gen2_data_source           = Gen2SuperSpeedStreamInterface()
        self.gen2_data_packet_good      = Signal()
        self.gen2_data_packet_bad       = Signal()

        # Gen2 header TX (to Gen2 link layer)
        self.gen2_header_sink_data      = Signal(96)
        self.gen2_header_sink_send      = Signal()
        self.gen2_header_sink_busy      = Signal()

        # Gen2 data TX (to Gen2 link layer)
        self.gen2_data_sink             = Gen2SuperSpeedStreamInterface()

        # Gen2 link commands RX (from Gen2 link layer)
        self.gen2_link_command_valid    = Signal()
        self.gen2_link_command          = Signal(11)

        # Gen2 link commands TX (to Gen2 link layer)
        self.gen2_link_command_to_send  = Signal(11)
        self.gen2_link_command_send     = Signal()
        self.gen2_link_command_busy     = Signal()

        # ── Unified protocol layer interface ─────────────────────────

        # Status
        self.link_ready                 = Signal()

        # Header RX (to protocol layer)
        self.header_rx_valid            = Signal()
        self.header_rx_data             = Signal(96)
        self.header_rx_crc_good         = Signal()

        # Header TX (from protocol layer)
        self.header_tx_data             = Signal(96)
        self.header_tx_send             = Signal()
        self.header_tx_busy             = Signal()

        # Data RX — separate interfaces per generation
        self.gen1_data_rx               = SuperSpeedStreamInterface()
        self.gen2_data_rx               = Gen2SuperSpeedStreamInterface()
        self.data_rx_packet_good        = Signal()
        self.data_rx_packet_bad         = Signal()

        # Data TX — separate interfaces per generation
        self.gen1_data_tx               = SuperSpeedStreamInterface()
        self.gen2_data_tx               = Gen2SuperSpeedStreamInterface()

        # Link commands (unified)
        self.link_command_rx_valid      = Signal()
        self.link_command_rx            = Signal(11)
        self.link_command_tx            = Signal(11)
        self.link_command_tx_send       = Signal()
        self.link_command_tx_busy       = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.If(self.use_gen2):
            # =============================================================
            # Gen2 path active
            # =============================================================

            # -- Status --
            m.d.comb += self.link_ready.eq(self.gen2_link_ready)

            # -- Header RX: Gen2 link layer → protocol layer --
            m.d.comb += [
                self.header_rx_valid    .eq(self.gen2_header_source_valid),
                self.header_rx_data     .eq(self.gen2_header_source_data),
                self.header_rx_crc_good .eq(self.gen2_header_source_crc_good),
            ]

            # -- Header TX: protocol layer → Gen2 link layer --
            m.d.comb += [
                self.gen2_header_sink_data .eq(self.header_tx_data),
                self.gen2_header_sink_send .eq(self.header_tx_send),
                self.header_tx_busy        .eq(self.gen2_header_sink_busy),
            ]
            # Deassert Gen1 header TX to prevent spurious transmissions.
            m.d.comb += [
                self.gen1_header_sink_data .eq(0),
                self.gen1_header_sink_send .eq(0),
            ]

            # -- Data RX: Gen2 link layer → protocol layer --
            m.d.comb += [
                self.gen2_data_rx.payload .eq(self.gen2_data_source.payload),
                self.gen2_data_rx.valid   .eq(self.gen2_data_source.valid),
                self.gen2_data_rx.first   .eq(self.gen2_data_source.first),
                self.gen2_data_rx.last    .eq(self.gen2_data_source.last),
                self.gen2_data_source.ready .eq(self.gen2_data_rx.ready),

                self.data_rx_packet_good  .eq(self.gen2_data_packet_good),
                self.data_rx_packet_bad   .eq(self.gen2_data_packet_bad),
            ]
            # Silence Gen1 data RX.
            m.d.comb += [
                self.gen1_data_rx.payload .eq(0),
                self.gen1_data_rx.valid   .eq(0),
                self.gen1_data_rx.first   .eq(0),
                self.gen1_data_rx.last    .eq(0),
            ]

            # -- Data TX: protocol layer → Gen2 link layer --
            m.d.comb += [
                self.gen2_data_sink.payload .eq(self.gen2_data_tx.payload),
                self.gen2_data_sink.valid   .eq(self.gen2_data_tx.valid),
                self.gen2_data_sink.first   .eq(self.gen2_data_tx.first),
                self.gen2_data_sink.last    .eq(self.gen2_data_tx.last),
                self.gen2_data_tx.ready     .eq(self.gen2_data_sink.ready),
            ]
            # Deassert Gen1 data TX path.
            m.d.comb += [
                self.gen1_data_sink.payload .eq(0),
                self.gen1_data_sink.valid   .eq(0),
                self.gen1_data_sink.first   .eq(0),
                self.gen1_data_sink.last    .eq(0),
            ]

            # -- Link commands RX: Gen2 link layer → protocol layer --
            m.d.comb += [
                self.link_command_rx_valid .eq(self.gen2_link_command_valid),
                self.link_command_rx       .eq(self.gen2_link_command),
            ]

            # -- Link commands TX: protocol layer → Gen2 link layer --
            m.d.comb += [
                self.gen2_link_command_to_send .eq(self.link_command_tx),
                self.gen2_link_command_send    .eq(self.link_command_tx_send),
                self.link_command_tx_busy      .eq(self.gen2_link_command_busy),
            ]
            # Deassert Gen1 link command TX.
            m.d.comb += [
                self.gen1_link_command_to_send .eq(0),
                self.gen1_link_command_send    .eq(0),
            ]

        with m.Else():
            # =============================================================
            # Gen1 path active (default)
            # =============================================================

            # -- Status --
            m.d.comb += self.link_ready.eq(self.gen1_link_ready)

            # -- Header RX: Gen1 link layer → protocol layer --
            m.d.comb += [
                self.header_rx_valid    .eq(self.gen1_header_source_valid),
                self.header_rx_data     .eq(self.gen1_header_source_data),
                self.header_rx_crc_good .eq(self.gen1_header_source_crc_good),
            ]

            # -- Header TX: protocol layer → Gen1 link layer --
            m.d.comb += [
                self.gen1_header_sink_data .eq(self.header_tx_data),
                self.gen1_header_sink_send .eq(self.header_tx_send),
                self.header_tx_busy        .eq(self.gen1_header_sink_busy),
            ]
            # Deassert Gen2 header TX to prevent spurious transmissions.
            m.d.comb += [
                self.gen2_header_sink_data .eq(0),
                self.gen2_header_sink_send .eq(0),
            ]

            # -- Data RX: Gen1 link layer → protocol layer --
            m.d.comb += [
                self.gen1_data_rx.payload .eq(self.gen1_data_source.payload),
                self.gen1_data_rx.valid   .eq(self.gen1_data_source.valid),
                self.gen1_data_rx.first   .eq(self.gen1_data_source.first),
                self.gen1_data_rx.last    .eq(self.gen1_data_source.last),
                self.gen1_data_source.ready .eq(self.gen1_data_rx.ready),

                self.data_rx_packet_good  .eq(self.gen1_data_packet_good),
                self.data_rx_packet_bad   .eq(self.gen1_data_packet_bad),
            ]
            # Silence Gen2 data RX.
            m.d.comb += [
                self.gen2_data_rx.payload .eq(0),
                self.gen2_data_rx.valid   .eq(0),
                self.gen2_data_rx.first   .eq(0),
                self.gen2_data_rx.last    .eq(0),
            ]

            # -- Data TX: protocol layer → Gen1 link layer --
            m.d.comb += [
                self.gen1_data_sink.payload .eq(self.gen1_data_tx.payload),
                self.gen1_data_sink.valid   .eq(self.gen1_data_tx.valid),
                self.gen1_data_sink.first   .eq(self.gen1_data_tx.first),
                self.gen1_data_sink.last    .eq(self.gen1_data_tx.last),
                self.gen1_data_tx.ready     .eq(self.gen1_data_sink.ready),
            ]
            # Deassert Gen2 data TX path.
            m.d.comb += [
                self.gen2_data_sink.payload .eq(0),
                self.gen2_data_sink.valid   .eq(0),
                self.gen2_data_sink.first   .eq(0),
                self.gen2_data_sink.last    .eq(0),
            ]

            # -- Link commands RX: Gen1 link layer → protocol layer --
            m.d.comb += [
                self.link_command_rx_valid .eq(self.gen1_link_command_valid),
                self.link_command_rx       .eq(self.gen1_link_command),
            ]

            # -- Link commands TX: protocol layer → Gen1 link layer --
            m.d.comb += [
                self.gen1_link_command_to_send .eq(self.link_command_tx),
                self.gen1_link_command_send    .eq(self.link_command_tx_send),
                self.link_command_tx_busy      .eq(self.gen1_link_command_busy),
            ]
            # Deassert Gen2 link command TX.
            m.d.comb += [
                self.gen2_link_command_to_send .eq(0),
                self.gen2_link_command_send    .eq(0),
            ]

        return m
