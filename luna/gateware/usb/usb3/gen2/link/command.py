#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Gen2 Link Command Receiver and Transmitter for USB 3.1 Gen2. """

from amaranth import *

from ..interfaces import Gen2BlockType, Gen2RawSuperSpeedStream
from ...link.crc  import compute_usb_crc5


class Gen2LinkCommandReceiver(Elaboratable):
    """Receives and validates Gen2 link commands from parsed blocks.

    In Gen2, link commands are single control blocks with subtype
    ``LINK_CMD`` (0x4B). The block contains two copies of the same
    16-bit link command word. Each 16-bit word carries an 11-bit
    payload and a 5-bit CRC-5.

    Layout within the first 64-bit word of the block::

        word0[ 0: 8]  = subtype (0x4B)
        word0[ 8:24]  = first  link command word (16 bits)
        word0[24:40]  = second link command word (16 bits, duplicate)
        word0[40:64]  = padding / reserved

    Each 16-bit link command word::

        bits [10:0]  = 11-bit command payload
        bits [15:11] = 5-bit CRC-5

    All logic runs in the ``ss`` clock domain.

    Attributes
    ----------
    word0 : Signal(64), input
        First 64-bit word of the link command block (from block parser).
    link_cmd_strobe : Signal(), input
        Strobe from the block parser indicating a link command block.

    new_command : Signal(), output
        Asserted for one cycle when a valid link command has been received.
    command : Signal(11), output
        The 11-bit link command payload (valid when ``new_command`` is asserted).
    crc_good : Signal(), output
        CRC-5 check passed for the received command.
    """

    def __init__(self):
        #
        # I/O port
        #

        # Input from block parser
        self.word0           = Signal(64)
        self.link_cmd_strobe = Signal()

        # Output
        self.new_command = Signal()
        self.command     = Signal(11)
        self.crc_good   = Signal()


    def elaborate(self, platform):
        m = Module()

        # Default: no new command this cycle.
        m.d.ss += self.new_command.eq(0)

        with m.If(self.link_cmd_strobe):
            # Extract the two 16-bit link command words from the block.
            lc_word0 = self.word0[ 8:24]
            lc_word1 = self.word0[24:40]

            # Extract payload and CRC from the first word.
            payload0 = lc_word0[ 0:11]
            crc0     = lc_word0[11:16]

            # Compute expected CRC-5 for the first word's payload.
            expected_crc = compute_usb_crc5(payload0)

            # Validate: both copies must match, and CRC must be correct.
            redundancy_ok = (lc_word0 == lc_word1)
            crc_ok        = (crc0 == expected_crc)

            with m.If(redundancy_ok & crc_ok):
                m.d.ss += [
                    self.new_command .eq(1),
                    self.command     .eq(payload0),
                    self.crc_good   .eq(1),
                ]
            with m.Else():
                m.d.ss += [
                    self.crc_good   .eq(0),
                ]

        return m


class Gen2LinkCommandTransmitter(Elaboratable):
    """Transmits Gen2 link commands as control blocks.

    Takes an 11-bit link command, computes CRC-5, formats the 128-bit
    block (as two 64-bit words), and outputs them on a
    :class:`Gen2RawSuperSpeedStream`.

    The transmitter outputs two cycles per link command:

    - **Cycle 1** (``start_block=1``, ``sync_head=CONTROL_BLOCK``):
      ``word0`` containing the subtype byte (0x4B), two copies of the
      16-bit link command word, and padding.
    - **Cycle 2** (``start_block=0``):
      ``word1`` containing zeros (padding for the second half of the
      128-bit block).

    All logic runs in the ``ss`` clock domain.

    Attributes
    ----------
    command : Signal(11), input
        The 11-bit link command to transmit.
    send : Signal(), input
        Trigger transmission of the link command.

    source : Gen2RawSuperSpeedStream, output
        Output stream carrying the formatted link command block.

    busy : Signal(), output
        Asserted while a transmission is in progress.
    done : Signal(), output
        Asserted for one cycle when transmission is complete.
    """

    def __init__(self):
        #
        # I/O port
        #

        # Input
        self.command = Signal(11)
        self.send    = Signal()

        # Output stream
        self.source = Gen2RawSuperSpeedStream()

        # Status
        self.busy = Signal()
        self.done = Signal()


    def elaborate(self, platform):
        m = Module()

        # Latched command, guaranteed stable during transmission.
        latched_command = Signal(11)

        # Build the 16-bit link command word: {CRC-5, payload}.
        lc_word = Signal(16)
        m.d.comb += [
            lc_word[ 0:11] .eq(latched_command),
            lc_word[11:16] .eq(compute_usb_crc5(latched_command)),
        ]

        # Build the first 64-bit word of the block.
        tx_word0 = Signal(64)
        m.d.comb += [
            tx_word0[ 0: 8] .eq(Gen2BlockType.LINK_CMD),  # subtype
            tx_word0[ 8:24] .eq(lc_word),                  # first LC word
            tx_word0[24:40] .eq(lc_word),                  # duplicate LC word
            tx_word0[40:64] .eq(0),                        # padding
        ]

        # Default: done is a single-cycle strobe.
        m.d.ss += self.done.eq(0)

        with m.FSM(domain="ss"):

            # IDLE -- waiting for a send request.
            with m.State("IDLE"):
                m.d.comb += self.busy.eq(0)

                with m.If(self.send):
                    m.d.ss += latched_command.eq(self.command)
                    m.next = "TRANSMIT_WORD0"


            # TRANSMIT_WORD0 -- output the first 64-bit word (start of block).
            with m.State("TRANSMIT_WORD0"):
                m.d.comb += [
                    self.busy                .eq(1),
                    self.source.valid        .eq(1),
                    self.source.data         .eq(tx_word0),
                    self.source.sync_head    .eq(Gen2BlockType.CONTROL_BLOCK),
                    self.source.start_block  .eq(1),
                ]

                with m.If(self.source.ready):
                    m.next = "TRANSMIT_WORD1"


            # TRANSMIT_WORD1 -- output the second 64-bit word (block continuation).
            with m.State("TRANSMIT_WORD1"):
                m.d.comb += [
                    self.busy                .eq(1),
                    self.source.valid        .eq(1),
                    self.source.data         .eq(0),   # padding
                    self.source.sync_head    .eq(0),
                    self.source.start_block  .eq(0),
                ]

                with m.If(self.source.ready):
                    m.d.ss += self.done.eq(1)
                    m.next = "IDLE"


        return m
