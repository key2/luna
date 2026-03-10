#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Gen2 128b/132b block parser for USB 3.1 Gen2 link layer. """

from amaranth import *

from ..interfaces import Gen2BlockType, Gen2RawSuperSpeedStream
from ..coding     import is_data_block, is_control_block, get_control_subtype


class Gen2BlockParser(Elaboratable):
    """Parses Gen2 128b/132b blocks from the raw PHY stream.

    The PHY outputs 64-bit words at ~156.25 MHz. Each 128-bit block spans
    two consecutive 64-bit words. The first word has ``start_block=1`` and
    carries the sync header that distinguishes data blocks from control
    blocks.

    This module accumulates both halves of a block and then classifies it,
    asserting per-type strobe signals for one cycle when a complete block
    has been received.

    All logic runs in the ``ss`` clock domain.

    Attributes
    ----------
    sink : Gen2RawSuperSpeedStream, input
        Raw 64-bit stream from the PHY (or upstream descrambler).

    block_valid : Signal(), output
        Asserted for one cycle when a complete 128-bit block has been
        received and classified.
    is_data : Signal(), output
        The received block is a data block (sync header = 0x3).
    is_control : Signal(), output
        The received block is a control block (sync header = 0xC).
    control_subtype : Signal(8), output
        Control block subtype byte (valid when ``is_control`` is asserted).

    word0 : Signal(64), output
        First 64-bit word of the block.
    word1 : Signal(64), output
        Second 64-bit word of the block.
    sync_head : Signal(4), output
        Sync header captured from the first word.

    hp_start : Signal(), output
        Header Packet Start control block detected.
    dp_start : Signal(), output
        Data Packet Start control block detected.
    end_good : Signal(), output
        End Good control block detected.
    end_bad : Signal(), output
        End Bad control block detected.
    link_cmd : Signal(), output
        Link Command control block detected.
    nop : Signal(), output
        NOP control block detected.
    """

    def __init__(self):
        #
        # I/O port
        #

        # Input: raw stream from PHY
        self.sink = Gen2RawSuperSpeedStream()

        # Block classification outputs (active for 1 cycle when block is complete)
        self.block_valid     = Signal()
        self.is_data         = Signal()
        self.is_control      = Signal()
        self.control_subtype = Signal(8)

        # Block payload (both halves captured)
        self.word0     = Signal(64)
        self.word1     = Signal(64)
        self.sync_head = Signal(4)

        # Specific block type strobes (active for 1 cycle)
        self.hp_start = Signal()
        self.dp_start = Signal()
        self.end_good = Signal()
        self.end_bad  = Signal()
        self.link_cmd = Signal()
        self.nop      = Signal()


    def elaborate(self, platform):
        m = Module()

        # Internal registers for capturing the first word of a block.
        captured_word0     = Signal(64)
        captured_sync_head = Signal(4)

        # Clear all output strobes by default each cycle.
        m.d.ss += [
            self.block_valid  .eq(0),
            self.is_data      .eq(0),
            self.is_control   .eq(0),
            self.hp_start     .eq(0),
            self.dp_start     .eq(0),
            self.end_good     .eq(0),
            self.end_bad      .eq(0),
            self.link_cmd     .eq(0),
            self.nop          .eq(0),
        ]

        with m.FSM(domain="ss"):

            # WAIT_FOR_BLOCK -- idle state; wait for the first word of a new block.
            with m.State("WAIT_FOR_BLOCK"):

                with m.If(self.sink.valid & self.sink.start_block):
                    # Capture the first 64-bit word and sync header.
                    m.d.ss += [
                        captured_word0      .eq(self.sink.data),
                        captured_sync_head  .eq(self.sink.sync_head),
                    ]
                    m.next = "CAPTURE_WORD1"


            # CAPTURE_WORD1 -- we have the first word; now capture the second.
            with m.State("CAPTURE_WORD1"):

                with m.If(self.sink.valid):
                    # Latch both words and the sync header to outputs.
                    m.d.ss += [
                        self.word0      .eq(captured_word0),
                        self.word1      .eq(self.sink.data),
                        self.sync_head  .eq(captured_sync_head),
                        self.block_valid.eq(1),
                    ]

                    # Classify the block based on the sync header.
                    with m.If(is_data_block(captured_sync_head)):
                        m.d.ss += self.is_data.eq(1)

                    with m.Elif(is_control_block(captured_sync_head)):
                        subtype = get_control_subtype(captured_word0)

                        m.d.ss += [
                            self.is_control      .eq(1),
                            self.control_subtype .eq(subtype),
                        ]

                        # Assert the specific strobe for the detected subtype.
                        with m.Switch(subtype):
                            with m.Case(Gen2BlockType.HP_START):
                                m.d.ss += self.hp_start.eq(1)
                            with m.Case(Gen2BlockType.DP_START):
                                m.d.ss += self.dp_start.eq(1)
                            with m.Case(Gen2BlockType.END_GOOD):
                                m.d.ss += self.end_good.eq(1)
                            with m.Case(Gen2BlockType.END_BAD):
                                m.d.ss += self.end_bad.eq(1)
                            with m.Case(Gen2BlockType.LINK_CMD):
                                m.d.ss += self.link_cmd.eq(1)
                            with m.Case(Gen2BlockType.NOP):
                                m.d.ss += self.nop.eq(1)

                    m.next = "WAIT_FOR_BLOCK"

        return m
