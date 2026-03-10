#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Gen2 Header Packet Receiver and Transmitter for USB 3.1 Gen2.

Gen2 header packets are 14 bytes total (12-byte payload + 2-byte CRC-16),
contained in a single HP_START control block (2 × 64-bit words):

    Word 0: [subtype(8)][hdr[0](8)][hdr[1](8)]...[hdr[6](8)]
            = HP_START subtype byte + header bytes 0–6

    Word 1: [hdr[7](8)][hdr[8](8)]...[hdr[11](8)][crc16_lo(8)][crc16_hi(8)][pad(8)]
            = header bytes 7–11 + CRC-16 (little-endian) + padding

The CRC-16 covers header bytes 0–11 (96 bits = 12 bytes).
"""

from amaranth import *

from ..interfaces import Gen2BlockType, Gen2RawSuperSpeedStream
from ..crc        import Gen2HeaderCRC


class Gen2HeaderPacketReceiver(Elaboratable):
    """Receives and validates Gen2 header packets.

    In Gen2, a header packet is contained in a single HP_START control block:

    - Word 0: ``[subtype(8)][header_bytes_0_6(56)]``
    - Word 1: ``[header_bytes_7_11(40)][crc16(16)][padding(8)]``

    The receiver extracts the 12-byte header, validates CRC-16 using a
    two-cycle pipeline (8 bytes + 4 bytes), and outputs the header fields
    to the protocol layer.

    All logic runs in the ``ss`` clock domain.

    Attributes
    ----------
    word0 : Signal(64), input
        First 64-bit word of the HP_START block (from block parser).
    word1 : Signal(64), input
        Second 64-bit word of the HP_START block (from block parser).
    hp_start_strobe : Signal(), input
        Strobe from the block parser indicating an HP_START block.

    new_header : Signal(), output
        Asserted for one cycle when a header has been received and
        CRC validation is complete (check ``crc_good`` / ``crc_bad``).
    header_data : Signal(96), output
        12-byte header payload (bytes 0–11), valid when ``new_header``
        is asserted.
    crc_good : Signal(), output
        CRC-16 validated OK (valid when ``new_header`` is asserted).
    crc_bad : Signal(), output
        CRC-16 failed (valid when ``new_header`` is asserted).
    """

    def __init__(self):
        #
        # I/O port
        #

        # Inputs from block parser
        self.word0            = Signal(64)
        self.word1            = Signal(64)
        self.hp_start_strobe  = Signal()

        # Header output
        self.new_header  = Signal()
        self.header_data = Signal(96)
        self.crc_good    = Signal()
        self.crc_bad     = Signal()


    def elaborate(self, platform):
        m = Module()

        #
        # CRC-16 engine
        #
        m.submodules.crc16 = crc16 = Gen2HeaderCRC()

        # Latched copies of the block words, captured when hp_start fires.
        latched_word0 = Signal(64)
        latched_word1 = Signal(64)

        # Reconstruct the 12 header bytes from the block layout.
        # Bytes 0–6 come from word0[8:64] (skip the subtype byte).
        # Bytes 7–11 come from word1[0:40].
        header_bytes_0_6  = Signal(56)
        header_bytes_7_11 = Signal(40)
        full_header       = Signal(96)

        m.d.comb += [
            header_bytes_0_6  .eq(latched_word0[8:64]),
            header_bytes_7_11 .eq(latched_word1[0:40]),
            full_header       .eq(Cat(header_bytes_0_6, header_bytes_7_11)),
        ]

        # Extract the received CRC-16 from word1[40:56].
        received_crc = Signal(16)
        m.d.comb += received_crc.eq(latched_word1[40:56])

        # For CRC computation, we need to feed the 12 header bytes in order.
        # Cycle 1: bytes 0–7 (64 bits) via advance_crc
        #   We need to reconstruct bytes 0–7 as a contiguous 64-bit word:
        #   bytes 0–6 = word0[8:64] (56 bits), byte 7 = word1[0:8] (8 bits)
        crc_data_cycle1 = Signal(64)
        m.d.comb += crc_data_cycle1.eq(Cat(header_bytes_0_6, latched_word1[0:8]))

        # Cycle 2: bytes 8–11 (32 bits) via advance_4B
        crc_data_cycle2 = Signal(64)
        m.d.comb += crc_data_cycle2.eq(latched_word1[8:40])

        # Default: clear output strobes each cycle.
        m.d.ss += [
            self.new_header .eq(0),
            self.crc_good   .eq(0),
            self.crc_bad    .eq(0),
        ]

        with m.FSM(domain="ss"):

            # IDLE — wait for an HP_START strobe from the block parser.
            with m.State("IDLE"):
                with m.If(self.hp_start_strobe):
                    # Latch the block words.
                    m.d.ss += [
                        latched_word0 .eq(self.word0),
                        latched_word1 .eq(self.word1),
                    ]
                    m.next = "CRC_CYCLE1"

            # CRC_CYCLE1 — clear CRC and feed the first 8 header bytes.
            with m.State("CRC_CYCLE1"):
                m.d.comb += [
                    crc16.clear       .eq(1),
                ]
                m.next = "CRC_CYCLE2"

            # CRC_CYCLE2 — feed bytes 0–7 (64 bits) to the CRC engine.
            with m.State("CRC_CYCLE2"):
                m.d.comb += [
                    crc16.data_input  .eq(crc_data_cycle1),
                    crc16.advance_crc .eq(1),
                ]
                m.next = "CRC_CYCLE3"

            # CRC_CYCLE3 — feed bytes 8–11 (32 bits) to the CRC engine.
            with m.State("CRC_CYCLE3"):
                m.d.comb += [
                    crc16.data_input .eq(crc_data_cycle2),
                    crc16.advance_4B .eq(1),
                ]
                m.next = "CHECK_CRC"

            # CHECK_CRC — compare computed CRC with received CRC.
            with m.State("CHECK_CRC"):
                m.d.ss += [
                    self.new_header  .eq(1),
                    self.header_data .eq(full_header),
                ]

                with m.If(crc16.crc == received_crc):
                    m.d.ss += self.crc_good.eq(1)
                with m.Else():
                    m.d.ss += self.crc_bad.eq(1)

                m.next = "IDLE"

        return m


class Gen2HeaderPacketTransmitter(Elaboratable):
    """Transmits Gen2 header packets as HP_START control blocks.

    Takes a 12-byte header payload, computes CRC-16, and formats it
    into a 2-word control block for transmission on a
    :class:`Gen2RawSuperSpeedStream`.

    The transmitter uses a pipelined approach:

    1. **COMPUTE_CRC1**: Clear CRC, feed header bytes 0–7 (64 bits).
    2. **COMPUTE_CRC2**: Feed header bytes 8–11 (32 bits).
    3. **SEND_WORD0**: Output word 0 (subtype + header bytes 0–6) with
       ``start_block=1`` and ``sync_head=CONTROL_BLOCK``.
    4. **SEND_WORD1**: Output word 1 (header bytes 7–11 + CRC-16 + pad)
       with ``start_block=0``.

    All logic runs in the ``ss`` clock domain.

    Attributes
    ----------
    header_data : Signal(96), input
        12-byte header payload (bytes 0–11).
    send : Signal(), input
        Trigger transmission of the header packet.

    source : Gen2RawSuperSpeedStream, output
        Output stream carrying the formatted HP_START block.

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
        self.header_data = Signal(96)
        self.send        = Signal()

        # Output stream
        self.source = Gen2RawSuperSpeedStream()

        # Status
        self.busy = Signal()
        self.done = Signal()


    def elaborate(self, platform):
        m = Module()

        #
        # CRC-16 engine
        #
        m.submodules.crc16 = crc16 = Gen2HeaderCRC()

        # Latched header data, guaranteed stable during transmission.
        latched_header = Signal(96)

        # Decompose the 96-bit header into byte ranges.
        # header_data[0:56]  = bytes 0–6
        # header_data[56:96] = bytes 7–11 (40 bits)
        header_bytes_0_6  = latched_header[0:56]
        header_bytes_7_11 = latched_header[56:96]

        # CRC input data: bytes 0–7 (64 bits) for cycle 1.
        # bytes 0–6 = header_data[0:56], byte 7 = header_data[56:64]
        crc_data_cycle1 = Signal(64)
        m.d.comb += crc_data_cycle1.eq(latched_header[0:64])

        # CRC input data: bytes 8–11 (32 bits) for cycle 2.
        crc_data_cycle2 = Signal(64)
        m.d.comb += crc_data_cycle2.eq(latched_header[64:96])

        # Build the two 64-bit words of the HP_START block.
        # Word 0: [HP_START(8)][header_bytes_0_6(56)]
        tx_word0 = Signal(64)
        m.d.comb += [
            tx_word0[0:8]   .eq(Gen2BlockType.HP_START),
            tx_word0[8:64]  .eq(header_bytes_0_6),
        ]

        # Word 1: [header_bytes_7_11(40)][crc16(16)][padding(8)]
        # CRC is filled in from the CRC engine output.
        tx_word1 = Signal(64)
        m.d.comb += [
            tx_word1[0:40]  .eq(header_bytes_7_11),
            tx_word1[40:56] .eq(crc16.crc),
            tx_word1[56:64] .eq(0),  # padding
        ]

        # Default: done is a single-cycle strobe.
        m.d.ss += self.done.eq(0)

        with m.FSM(domain="ss"):

            # IDLE — waiting for a send request.
            with m.State("IDLE"):
                m.d.comb += self.busy.eq(0)

                with m.If(self.send):
                    m.d.ss += latched_header.eq(self.header_data)
                    m.next = "COMPUTE_CRC1"

            # COMPUTE_CRC1 — clear CRC and feed header bytes 0–7.
            with m.State("COMPUTE_CRC1"):
                m.d.comb += [
                    self.busy         .eq(1),
                    crc16.clear       .eq(1),
                ]
                m.next = "COMPUTE_CRC2"

            # COMPUTE_CRC2 — feed bytes 0–7 (64 bits) to CRC engine.
            with m.State("COMPUTE_CRC2"):
                m.d.comb += [
                    self.busy          .eq(1),
                    crc16.data_input   .eq(crc_data_cycle1),
                    crc16.advance_crc  .eq(1),
                ]
                m.next = "COMPUTE_CRC3"

            # COMPUTE_CRC3 — feed bytes 8–11 (32 bits) to CRC engine.
            with m.State("COMPUTE_CRC3"):
                m.d.comb += [
                    self.busy         .eq(1),
                    crc16.data_input  .eq(crc_data_cycle2),
                    crc16.advance_4B  .eq(1),
                ]
                m.next = "SEND_WORD0"

            # SEND_WORD0 — output the first 64-bit word (start of block).
            with m.State("SEND_WORD0"):
                m.d.comb += [
                    self.busy                .eq(1),
                    self.source.valid        .eq(1),
                    self.source.data         .eq(tx_word0),
                    self.source.sync_head    .eq(Gen2BlockType.CONTROL_BLOCK),
                    self.source.start_block  .eq(1),
                ]

                with m.If(self.source.ready):
                    m.next = "SEND_WORD1"

            # SEND_WORD1 — output the second 64-bit word (block continuation).
            with m.State("SEND_WORD1"):
                m.d.comb += [
                    self.busy                .eq(1),
                    self.source.valid        .eq(1),
                    self.source.data         .eq(tx_word1),
                    self.source.sync_head    .eq(0),
                    self.source.start_block  .eq(0),
                ]

                with m.If(self.source.ready):
                    m.d.ss += self.done.eq(1)
                    m.next = "IDLE"

        return m
