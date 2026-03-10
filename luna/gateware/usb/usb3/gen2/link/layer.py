#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Top-level Gen2 link layer for USB 3.1 Gen2.

Wires together the block parser, header/data/link-command receivers and
transmitters, and provides a clean interface to the protocol layer above.

Gen2 link layer architecture::

    PHY source (Gen2RawSuperSpeedStream) â Gen2BlockParser â {
        hp_start â Gen2HeaderPacketReceiver â header_source (to protocol layer)
        dp_start/data/end â Gen2DataPacketReceiver â data_source (to protocol layer)
        link_cmd â Gen2LinkCommandReceiver â link command handling
        nop â (ignored)
    }

    Protocol layer â {
        header_sink â Gen2HeaderPacketTransmitter â TX arbiter
        data_sink â Gen2DataPacketTransmitter â TX arbiter
        link_cmd_sink â Gen2LinkCommandTransmitter â TX arbiter
    }

    TX arbiter â PHY sink (Gen2RawSuperSpeedStream)

The Gen2 link layer is simpler than Gen1 because the PHY handles
scrambling/descrambling, CTC skip insertion/removal, and word alignment.
Block-type framing replaces K-character framing.
"""

from amaranth import *

from ..interfaces import Gen2BlockType, Gen2RawSuperSpeedStream, Gen2SuperSpeedStreamInterface

from .block_parser import Gen2BlockParser
from .command      import Gen2LinkCommandReceiver, Gen2LinkCommandTransmitter
from .header       import Gen2HeaderPacketReceiver, Gen2HeaderPacketTransmitter
from .data         import Gen2DataPacketReceiver, Gen2DataPacketTransmitter


class Gen2LinkLayer(Elaboratable):
    """Top-level Gen2 link layer.

    Wires together the block parser, header/data/link-command receivers and
    transmitters, and provides a clean interface to the protocol layer.

    Parameters
    ----------
    ss_clock_frequency : float
        SuperSpeed clock frequency in Hz (default: 156.25e6 for Gen2).
    """

    def __init__(self, ss_clock_frequency=156.25e6):
        self._ss_clock_frequency = ss_clock_frequency

        # === RX Interface (to protocol layer) ===

        # Header packets received
        self.header_source_valid    = Signal()     # New header available
        self.header_source_data     = Signal(96)   # 12-byte header payload
        self.header_source_crc_good = Signal()     # CRC-16 validated

        # Data packets received
        self.data_source      = Gen2SuperSpeedStreamInterface()  # Data payload stream
        self.data_packet_good = Signal()       # Data packet CRC-32 good
        self.data_packet_bad  = Signal()       # Data packet CRC-32 bad

        # Link commands received
        self.link_command_valid = Signal()      # New link command
        self.link_command       = Signal(11)    # 11-bit link command

        # === TX Interface (from protocol layer) ===

        # Header packets to send
        self.header_sink_data = Signal(96)     # 12-byte header to transmit
        self.header_sink_send = Signal()       # Trigger header transmission
        self.header_sink_busy = Signal()       # Header TX busy
        self.header_sink_done = Signal()       # Header TX complete

        # Data packets to send
        self.data_sink       = Gen2SuperSpeedStreamInterface()  # Data payload to transmit
        self.data_sink_start = Signal()        # Start data packet transmission
        self.data_sink_busy  = Signal()        # Data TX busy
        self.data_sink_done  = Signal()        # Data TX complete

        # Link commands to send
        self.link_command_send    = Signal()    # Trigger link command TX
        self.link_command_to_send = Signal(11)  # 11-bit link command to send
        self.link_command_busy    = Signal()    # Link command TX busy

        # === PHY Interface ===
        self.phy_source = Gen2RawSuperSpeedStream()  # RX from PHY
        self.phy_sink   = Gen2RawSuperSpeedStream()  # TX to PHY

        # === Status ===
        self.link_ready     = Signal()         # Link is trained and ready
        self.receiving_data = Signal()         # Currently receiving a data packet


    def elaborate(self, platform):
        m = Module()

        # ----------------------------------------------------------------
        # Submodule instantiation
        # ----------------------------------------------------------------

        m.submodules.block_parser = block_parser = Gen2BlockParser()
        m.submodules.header_rx    = header_rx    = Gen2HeaderPacketReceiver()
        m.submodules.data_rx      = data_rx      = Gen2DataPacketReceiver()
        m.submodules.link_cmd_rx  = link_cmd_rx  = Gen2LinkCommandReceiver()
        m.submodules.header_tx    = header_tx    = Gen2HeaderPacketTransmitter()
        m.submodules.data_tx      = data_tx      = Gen2DataPacketTransmitter()
        m.submodules.link_cmd_tx  = link_cmd_tx  = Gen2LinkCommandTransmitter()

        # ----------------------------------------------------------------
        # RX path: PHY â block parser â receivers â protocol layer
        # ----------------------------------------------------------------

        # Connect PHY source to block parser sink (stream connect).
        m.d.comb += block_parser.sink.stream_eq(self.phy_source)

        # Wire block parser outputs to header receiver.
        m.d.comb += [
            header_rx.word0           .eq(block_parser.word0),
            header_rx.word1           .eq(block_parser.word1),
            header_rx.hp_start_strobe .eq(block_parser.hp_start),
        ]

        # Wire block parser outputs to data receiver.
        m.d.comb += [
            data_rx.word0             .eq(block_parser.word0),
            data_rx.word1             .eq(block_parser.word1),
            data_rx.dp_start_strobe   .eq(block_parser.dp_start),
            data_rx.data_block_strobe .eq(block_parser.is_data & block_parser.block_valid),
            data_rx.end_good_strobe   .eq(block_parser.end_good),
            data_rx.end_bad_strobe    .eq(block_parser.end_bad),
        ]

        # Wire block parser outputs to link command receiver.
        m.d.comb += [
            link_cmd_rx.word0           .eq(block_parser.word0),
            link_cmd_rx.link_cmd_strobe .eq(block_parser.link_cmd),
        ]

        # Wire header receiver outputs to protocol layer interface.
        m.d.comb += [
            self.header_source_valid    .eq(header_rx.new_header),
            self.header_source_data     .eq(header_rx.header_data),
            self.header_source_crc_good .eq(header_rx.crc_good),
        ]

        # Wire data receiver outputs to protocol layer interface.
        m.d.comb += [
            self.data_source    .stream_eq(data_rx.source),
            self.data_packet_good .eq(data_rx.packet_good),
            self.data_packet_bad  .eq(data_rx.packet_bad),
            self.receiving_data   .eq(data_rx.receiving),
        ]

        # Wire link command receiver outputs to protocol layer interface.
        m.d.comb += [
            self.link_command_valid .eq(link_cmd_rx.new_command),
            self.link_command       .eq(link_cmd_rx.command),
        ]

        # ----------------------------------------------------------------
        # TX path: protocol layer â transmitters â TX arbiter â PHY
        # ----------------------------------------------------------------

        # Wire protocol layer header TX interface to header transmitter.
        m.d.comb += [
            header_tx.header_data .eq(self.header_sink_data),
            header_tx.send        .eq(self.header_sink_send),
            self.header_sink_busy .eq(header_tx.busy),
            self.header_sink_done .eq(header_tx.done),
        ]

        # Wire protocol layer data TX interface to data transmitter.
        m.d.comb += [
            data_tx.sink       .stream_eq(self.data_sink),
            data_tx.start      .eq(self.data_sink_start),
            self.data_sink_busy .eq(data_tx.busy),
            self.data_sink_done .eq(data_tx.done),
        ]

        # Wire protocol layer link command TX interface to link command transmitter.
        m.d.comb += [
            link_cmd_tx.command       .eq(self.link_command_to_send),
            link_cmd_tx.send          .eq(self.link_command_send),
            self.link_command_busy    .eq(link_cmd_tx.busy),
        ]

        # ----------------------------------------------------------------
        # TX Arbiter: priority mux of TX streams to PHY sink
        #
        # Priority (highest first):
        #   1. Link command transmitter
        #   2. Header packet transmitter
        #   3. Data packet transmitter
        #   4. NOP/idle (when nothing is transmitting)
        # ----------------------------------------------------------------

        # NOP block generation for idle periods.
        # A NOP is a control block with subtype 0x00.
        # We alternate start_block between 1 and 0 to form complete blocks.
        nop_phase = Signal()  # 0 = word0 (start), 1 = word1 (continuation)

        # Build NOP word0: [NOP_subtype(8)][padding(56)]
        nop_word0 = Signal(64)
        m.d.comb += [
            nop_word0[0:8]  .eq(Gen2BlockType.NOP),
            nop_word0[8:64] .eq(0),
        ]

        # Determine which transmitter gets access to the PHY sink.
        # We use a simple priority scheme: check each transmitter's
        # source.valid in priority order.
        link_cmd_active = link_cmd_tx.source.valid
        header_active   = header_tx.source.valid
        data_active     = data_tx.source.valid

        # Default: deassert all transmitter ready signals (backpressure).
        m.d.comb += [
            link_cmd_tx.source.ready .eq(0),
            header_tx.source.ready   .eq(0),
            data_tx.source.ready     .eq(0),
        ]

        with m.If(link_cmd_active):
            # Link command transmitter has highest priority.
            m.d.comb += [
                self.phy_sink.valid       .eq(link_cmd_tx.source.valid),
                self.phy_sink.data        .eq(link_cmd_tx.source.data),
                self.phy_sink.sync_head   .eq(link_cmd_tx.source.sync_head),
                self.phy_sink.start_block .eq(link_cmd_tx.source.start_block),
                self.phy_sink.first       .eq(link_cmd_tx.source.first),
                self.phy_sink.last        .eq(link_cmd_tx.source.last),
                link_cmd_tx.source.ready  .eq(self.phy_sink.ready),
            ]

        with m.Elif(header_active):
            # Header packet transmitter has second priority.
            m.d.comb += [
                self.phy_sink.valid       .eq(header_tx.source.valid),
                self.phy_sink.data        .eq(header_tx.source.data),
                self.phy_sink.sync_head   .eq(header_tx.source.sync_head),
                self.phy_sink.start_block .eq(header_tx.source.start_block),
                self.phy_sink.first       .eq(header_tx.source.first),
                self.phy_sink.last        .eq(header_tx.source.last),
                header_tx.source.ready    .eq(self.phy_sink.ready),
            ]

        with m.Elif(data_active):
            # Data packet transmitter has lowest priority.
            m.d.comb += [
                self.phy_sink.valid       .eq(data_tx.source.valid),
                self.phy_sink.data        .eq(data_tx.source.data),
                self.phy_sink.sync_head   .eq(data_tx.source.sync_head),
                self.phy_sink.start_block .eq(data_tx.source.start_block),
                self.phy_sink.first       .eq(data_tx.source.first),
                self.phy_sink.last        .eq(data_tx.source.last),
                data_tx.source.ready      .eq(self.phy_sink.ready),
            ]

        with m.Else():
            # No transmitter active â output NOP blocks to keep the link alive.
            # Alternate between word0 (start of block) and word1 (continuation).
            m.d.comb += [
                self.phy_sink.valid       .eq(1),
                self.phy_sink.first       .eq(0),
                self.phy_sink.last        .eq(0),
            ]

            with m.If(~nop_phase):
                # Word 0: start of NOP control block.
                m.d.comb += [
                    self.phy_sink.data        .eq(nop_word0),
                    self.phy_sink.sync_head   .eq(Gen2BlockType.CONTROL_BLOCK),
                    self.phy_sink.start_block .eq(1),
                ]
                with m.If(self.phy_sink.ready):
                    m.d.ss += nop_phase.eq(1)

            with m.Else():
                # Word 1: continuation of NOP control block (all zeros).
                m.d.comb += [
                    self.phy_sink.data        .eq(0),
                    self.phy_sink.sync_head   .eq(0),
                    self.phy_sink.start_block .eq(0),
                ]
                with m.If(self.phy_sink.ready):
                    m.d.ss += nop_phase.eq(0)

        return m
