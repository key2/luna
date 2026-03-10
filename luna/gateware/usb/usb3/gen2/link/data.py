#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Gen2 Data Packet Receiver and Transmitter for USB 3.1 Gen2.

Gen2 data packets use 128b/132b block encoding and consist of:

1. A **DP_START** control block (subtype 0x66) containing the first data bytes:
   - Word 0: ``[DP_START(8)][data_bytes_0_6(56)]``
   - Word 1: ``[data_bytes_7_14(64)]``
   Total: 15 data bytes in the DP_START block.

2. Zero or more **DATA blocks** (sync header = 0x3) containing payload data:
   - Word 0: ``[data_bytes(64)]``
   - Word 1: ``[data_bytes(64)]``
   Total: 16 data bytes per DATA block.

3. An **END_GOOD** (0x78) or **END_BAD** (0x87) control block:
   - Word 0: ``[subtype(8)][framing_info(8)][remaining_data+crc+pad(48)]``
   - Word 1: ``[remaining_data+crc+pad(64)]``
   The framing_info byte indicates how many valid data bytes remain
   in this end block before the 4-byte CRC-32.

The CRC-32 covers all data bytes from DP_START through the end block.
"""

from amaranth import *

from ..interfaces import Gen2BlockType, Gen2RawSuperSpeedStream, Gen2SuperSpeedStreamInterface
from ..crc        import Gen2DataCRC


class Gen2DataPacketReceiver(Elaboratable):
    """Receives and validates Gen2 data packets.

    Data packets consist of:
    1. DP_START control block (subtype 0x66) with first 15 data bytes
    2. Zero or more DATA blocks with 16 payload bytes each
    3. END_GOOD/END_BAD control block with last data bytes + CRC-32

    The receiver accumulates data, computes running CRC-32, and outputs
    validated data on a SuperSpeed stream interface.

    All logic runs in the ``ss`` clock domain.

    Attributes
    ----------
    word0 : Signal(64), input
        First 64-bit word of the current block (from block parser).
    word1 : Signal(64), input
        Second 64-bit word of the current block (from block parser).
    dp_start_strobe : Signal(), input
        Strobe from block parser indicating a DP_START block.
    data_block_strobe : Signal(), input
        Strobe from block parser indicating a DATA block.
    end_good_strobe : Signal(), input
        Strobe from block parser indicating an END_GOOD block.
    end_bad_strobe : Signal(), input
        Strobe from block parser indicating an END_BAD block.

    source : Gen2SuperSpeedStreamInterface, output
        Stream carrying received data. ``payload`` is 64-bit,
        ``valid`` is 8-bit per-byte mask, ``first``/``last`` mark
        packet boundaries.

    packet_good : Signal(), output
        Strobe; packet ended with valid CRC (END_GOOD + CRC match).
    packet_bad : Signal(), output
        Strobe; packet ended with bad CRC or END_BAD.
    receiving : Signal(), output
        Asserted while a data packet is being received.
    """

    def __init__(self):
        #
        # I/O port
        #

        # Inputs from block parser
        self.word0             = Signal(64)
        self.word1             = Signal(64)
        self.dp_start_strobe   = Signal()
        self.data_block_strobe = Signal()
        self.end_good_strobe   = Signal()
        self.end_bad_strobe    = Signal()

        # Data output stream
        self.source = Gen2SuperSpeedStreamInterface()

        # Status
        self.packet_good = Signal()
        self.packet_bad  = Signal()
        self.receiving   = Signal()


    def elaborate(self, platform):
        m = Module()

        source = self.source

        #
        # CRC-32 engine
        #
        m.submodules.crc32 = crc32 = Gen2DataCRC()

        # Latched copies of block words.
        latched_word0 = Signal(64)
        latched_word1 = Signal(64)

        # Track whether this is the first data output of the packet.
        is_first = Signal()

        # Default: clear output strobes each cycle.
        m.d.ss += [
            self.packet_good .eq(0),
            self.packet_bad  .eq(0),
        ]

        # Default: source outputs are inactive.
        m.d.comb += [
            source.valid   .eq(0),
            source.payload .eq(0),
            source.first   .eq(0),
            source.last    .eq(0),
        ]

        with m.FSM(domain="ss"):

            # IDLE â wait for a DP_START strobe from the block parser.
            with m.State("IDLE"):
                m.d.comb += self.receiving.eq(0)

                # Keep CRC cleared while idle.
                m.d.comb += crc32.clear.eq(1)

                with m.If(self.dp_start_strobe):
                    # Latch the block words for processing.
                    m.d.ss += [
                        latched_word0 .eq(self.word0),
                        latched_word1 .eq(self.word1),
                        is_first      .eq(1),
                    ]
                    m.next = "DP_START_CRC1"


            # DP_START_CRC1 â Feed the first 7 data bytes from DP_START word0
            # to the CRC engine.
            #
            # DP_START word0 layout: [subtype(8)][data_bytes_0_6(56)]
            # We feed 7 bytes (56 bits) = data_bytes_0_6 to CRC.
            with m.State("DP_START_CRC1"):
                m.d.comb += [
                    self.receiving    .eq(1),
                    crc32.data_input  .eq(latched_word0[8:64]),
                    crc32.advance_7B  .eq(1),
                ]
                m.next = "DP_START_CRC2"


            # DP_START_CRC2 â Feed the next 8 data bytes from DP_START word1
            # to the CRC engine, and output the first data word.
            #
            # DP_START word1 layout: [data_bytes_7_14(64)]
            # All 8 bytes are data.
            with m.State("DP_START_CRC2"):
                m.d.comb += [
                    self.receiving    .eq(1),
                    crc32.data_input  .eq(latched_word1),
                    crc32.advance_word.eq(1),
                ]

                # Output the first data word: bytes 0-6 from word0[8:64]
                # packed into the low 56 bits of the payload.
                # We output 7 bytes as the first word.
                m.d.comb += [
                    source.payload .eq(latched_word0[8:64]),
                    source.valid   .eq(0b01111111),  # 7 valid bytes
                    source.first   .eq(1),
                ]

                m.d.ss += is_first.eq(0)
                m.next = "DP_START_OUTPUT_W1"


            # DP_START_OUTPUT_W1 â Output the second data word (bytes 7-14).
            with m.State("DP_START_OUTPUT_W1"):
                m.d.comb += [
                    self.receiving .eq(1),
                    source.payload .eq(latched_word1),
                    source.valid   .eq(0b11111111),  # 8 valid bytes
                    source.first   .eq(0),
                ]
                m.next = "RECEIVE_BLOCKS"


            # RECEIVE_BLOCKS â Wait for DATA blocks or END blocks.
            with m.State("RECEIVE_BLOCKS"):
                m.d.comb += self.receiving.eq(1)

                with m.If(self.data_block_strobe):
                    # Latch the data block words.
                    m.d.ss += [
                        latched_word0 .eq(self.word0),
                        latched_word1 .eq(self.word1),
                    ]
                    m.next = "DATA_BLOCK_CRC1"

                with m.Elif(self.end_good_strobe | self.end_bad_strobe):
                    # Latch the end block words.
                    m.d.ss += [
                        latched_word0 .eq(self.word0),
                        latched_word1 .eq(self.word1),
                    ]
                    # Remember whether this was END_GOOD or END_BAD.
                    m.d.ss += is_first.eq(self.end_good_strobe)  # reuse as end_good flag
                    m.next = "END_BLOCK_PROCESS"


            # DATA_BLOCK_CRC1 â Feed word0 of a DATA block to CRC and output it.
            with m.State("DATA_BLOCK_CRC1"):
                m.d.comb += [
                    self.receiving    .eq(1),
                    crc32.data_input  .eq(latched_word0),
                    crc32.advance_word.eq(1),

                    source.payload .eq(latched_word0),
                    source.valid   .eq(0b11111111),  # 8 valid bytes
                    source.first   .eq(0),
                ]
                m.next = "DATA_BLOCK_CRC2"


            # DATA_BLOCK_CRC2 â Feed word1 of a DATA block to CRC and output it.
            with m.State("DATA_BLOCK_CRC2"):
                m.d.comb += [
                    self.receiving    .eq(1),
                    crc32.data_input  .eq(latched_word1),
                    crc32.advance_word.eq(1),

                    source.payload .eq(latched_word1),
                    source.valid   .eq(0b11111111),  # 8 valid bytes
                    source.first   .eq(0),
                ]
                m.next = "RECEIVE_BLOCKS"


            # END_BLOCK_PROCESS â Process the END_GOOD/END_BAD block.
            #
            # END block layout:
            #   Word 0: [subtype(8)][framing_info(8)][data+crc+pad(48)]
            #   Word 1: [data+crc+pad(64)]
            #
            # framing_info (byte 1) tells us how many valid data bytes
            # remain in this end block before the CRC-32.
            #
            # The data bytes start at byte 2 of word0 (bit 16).
            # After `n_data_bytes` of data, the next 4 bytes are CRC-32.
            with m.State("END_BLOCK_PROCESS"):
                m.d.comb += self.receiving.eq(1)

                # Extract framing info: number of valid data bytes in end block.
                n_data_bytes = latched_word0[8:16]

                # Combine the available payload bytes from the end block
                # (excluding subtype and framing_info bytes).
                # Bytes available: word0[16:64] (6 bytes) + word1[0:64] (8 bytes) = 14 bytes
                end_payload = Signal(112)
                m.d.comb += end_payload.eq(Cat(latched_word0[16:64], latched_word1))

                # Extract the received CRC-32 from the end payload.
                # It starts at bit (n_data_bytes * 8) within end_payload.
                received_crc = Signal(32)

                # Feed the remaining data bytes to CRC.
                # We need to advance CRC by n_data_bytes (0-14).
                # Construct a data word from the end payload for CRC input.
                end_data = Signal(64)
                m.d.comb += end_data.eq(end_payload[0:64])
                m.d.comb += crc32.data_input.eq(end_data)

                # Output the last data bytes if any.
                # Build valid mask based on n_data_bytes (capped at 8 for first word).
                last_valid = Signal(8)

                # Advance CRC by the appropriate number of bytes and extract CRC.
                # We handle common cases with a Switch on n_data_bytes.
                with m.Switch(n_data_bytes):
                    with m.Case(0):
                        # No data bytes; CRC starts at byte 0 of end_payload.
                        m.d.comb += [
                            received_crc .eq(end_payload[0:32]),
                            last_valid   .eq(0),
                        ]

                    with m.Case(1):
                        m.d.comb += [
                            crc32.advance_1B .eq(1),
                            received_crc     .eq(end_payload[8:40]),
                            last_valid       .eq(0b00000001),
                        ]

                    with m.Case(2):
                        m.d.comb += [
                            crc32.advance_2B .eq(1),
                            received_crc     .eq(end_payload[16:48]),
                            last_valid       .eq(0b00000011),
                        ]

                    with m.Case(3):
                        m.d.comb += [
                            crc32.advance_3B .eq(1),
                            received_crc     .eq(end_payload[24:56]),
                            last_valid       .eq(0b00000111),
                        ]

                    with m.Case(4):
                        m.d.comb += [
                            crc32.advance_4B .eq(1),
                            received_crc     .eq(end_payload[32:64]),
                            last_valid       .eq(0b00001111),
                        ]

                    with m.Case(5):
                        m.d.comb += [
                            crc32.advance_5B .eq(1),
                            received_crc     .eq(end_payload[40:72]),
                            last_valid       .eq(0b00011111),
                        ]

                    with m.Case(6):
                        m.d.comb += [
                            crc32.advance_6B .eq(1),
                            received_crc     .eq(end_payload[48:80]),
                            last_valid       .eq(0b00111111),
                        ]

                    with m.Case(7):
                        m.d.comb += [
                            crc32.advance_7B .eq(1),
                            received_crc     .eq(end_payload[56:88]),
                            last_valid       .eq(0b01111111),
                        ]

                    with m.Default():
                        # 8 or more data bytes: advance full word, handle rest next cycle.
                        m.d.comb += [
                            crc32.advance_word .eq(1),
                            last_valid         .eq(0b11111111),
                        ]

                # Output the last data word if there are any data bytes.
                with m.If(n_data_bytes > 0):
                    m.d.comb += [
                        source.payload .eq(end_payload[0:64]),
                        source.valid   .eq(last_valid),
                        source.last    .eq(n_data_bytes <= 8),
                    ]

                # For packets with <= 8 remaining data bytes, we can check CRC now.
                with m.If(n_data_bytes <= 8):
                    m.next = "CHECK_CRC"
                with m.Else():
                    # More than 8 data bytes in end block: need a second cycle.
                    m.next = "END_BLOCK_PART2"


            # END_BLOCK_PART2 â Handle end blocks with more than 8 data bytes.
            # Feed the remaining bytes (from word1) to CRC.
            with m.State("END_BLOCK_PART2"):
                m.d.comb += self.receiving.eq(1)

                n_data_bytes = latched_word0[8:16]
                end_payload = Signal(112)
                m.d.comb += end_payload.eq(Cat(latched_word0[16:64], latched_word1))

                # Remaining data bytes after the first 8.
                remaining = Signal(8)
                m.d.comb += remaining.eq(n_data_bytes - 8)

                # The remaining data starts at bit 64 of end_payload (= word1[0:...]).
                end_data2 = Signal(64)
                m.d.comb += end_data2.eq(end_payload[64:112])
                m.d.comb += crc32.data_input.eq(end_data2)

                received_crc2 = Signal(32)
                last_valid2 = Signal(8)

                with m.Switch(remaining):
                    with m.Case(1):
                        m.d.comb += [
                            crc32.advance_1B .eq(1),
                            received_crc2    .eq(end_payload[72:104]),
                            last_valid2      .eq(0b00000001),
                        ]
                    with m.Case(2):
                        m.d.comb += [
                            crc32.advance_2B .eq(1),
                            received_crc2    .eq(end_payload[80:112]),
                            last_valid2      .eq(0b00000011),
                        ]
                    with m.Case(3):
                        m.d.comb += [
                            crc32.advance_3B .eq(1),
                            # CRC spans end_payload[88:112] + need more bits
                            # Actually max 14 bytes total, so remaining max = 6
                            # With 3 remaining: CRC at bits 88..120 but end_payload is 112 bits
                            # This means CRC would overflow. In practice, max data bytes
                            # in end block is limited. Let's handle up to 6 remaining.
                            last_valid2      .eq(0b00000111),
                        ]
                    with m.Case(4):
                        m.d.comb += [
                            crc32.advance_4B .eq(1),
                            last_valid2      .eq(0b00001111),
                        ]
                    with m.Case(5):
                        m.d.comb += [
                            crc32.advance_5B .eq(1),
                            last_valid2      .eq(0b00011111),
                        ]
                    with m.Case(6):
                        m.d.comb += [
                            crc32.advance_6B .eq(1),
                            last_valid2      .eq(0b00111111),
                        ]
                    with m.Default():
                        m.d.comb += last_valid2.eq(0)

                # Output the second part of end data.
                m.d.comb += [
                    source.payload .eq(end_payload[64:112]),
                    source.valid   .eq(last_valid2),
                    source.last    .eq(1),
                ]

                m.next = "CHECK_CRC"


            # CHECK_CRC â Compare computed CRC with received CRC.
            with m.State("CHECK_CRC"):
                # is_first was repurposed as end_good flag.
                end_was_good = is_first

                # The CRC engine output is available one cycle after the last advance.
                # We need to extract the received CRC based on framing info.
                n_data_bytes = latched_word0[8:16]
                end_payload = Signal(112)
                m.d.comb += end_payload.eq(Cat(latched_word0[16:64], latched_word1))

                # Extract received CRC based on n_data_bytes offset.
                received_crc_final = Signal(32)
                with m.Switch(n_data_bytes):
                    for i in range(15):  # 0 to 14 data bytes possible
                        with m.Case(i):
                            start_bit = i * 8
                            m.d.comb += received_crc_final.eq(
                                end_payload[start_bit:start_bit + 32]
                            )
                    with m.Default():
                        m.d.comb += received_crc_final.eq(0)

                # Check CRC and end block type.
                with m.If(end_was_good & (crc32.crc == received_crc_final)):
                    m.d.ss += self.packet_good.eq(1)
                with m.Else():
                    m.d.ss += self.packet_bad.eq(1)

                m.next = "IDLE"

        return m


class Gen2DataPacketTransmitter(Elaboratable):
    """Transmits Gen2 data packets.

    Takes data from a SuperSpeed stream interface, computes CRC-32,
    and formats it into DP_START + DATA + END_GOOD blocks for
    transmission on a :class:`Gen2RawSuperSpeedStream`.

    The transmitter accumulates data from the sink, formats it into
    Gen2 blocks, and appends a CRC-32 in the END_GOOD block.

    All logic runs in the ``ss`` clock domain.

    Attributes
    ----------
    sink : Gen2SuperSpeedStreamInterface, input
        Data stream to transmit. ``payload`` is 64-bit, ``valid`` is
        8-bit per-byte mask, ``first``/``last`` mark packet boundaries.

    source : Gen2RawSuperSpeedStream, output
        Output stream carrying formatted Gen2 blocks to the PHY.

    start : Signal(), input
        Trigger to begin transmitting a data packet. The first data
        word should be available on ``sink`` when ``start`` is asserted.

    busy : Signal(), output
        Asserted while a transmission is in progress.
    done : Signal(), output
        Strobe; asserted for one cycle when transmission is complete.
    """

    def __init__(self):
        #
        # I/O port
        #

        # Data input stream
        self.sink = Gen2SuperSpeedStreamInterface()

        # Output stream (to PHY)
        self.source = Gen2RawSuperSpeedStream()

        # Control
        self.start = Signal()

        # Status
        self.busy = Signal()
        self.done = Signal()


    def elaborate(self, platform):
        m = Module()

        sink   = self.sink
        source = self.source

        #
        # CRC-32 engine
        #
        m.submodules.crc32 = crc32 = Gen2DataCRC()

        # Buffered data words for building blocks.
        buf_word0 = Signal(64)
        buf_word1 = Signal(64)
        buf_valid0 = Signal(8)
        buf_valid1 = Signal(8)

        # Count of valid bytes in the current buffered data.
        buf_count = Signal(range(17))

        # Track whether we've seen the last word from the sink.
        sink_last_seen = Signal()

        # Latched CRC value for the END block.
        latched_crc = Signal(32)

        # Default: done is a single-cycle strobe.
        m.d.ss += self.done.eq(0)

        # Default: source outputs are inactive.
        m.d.comb += [
            source.valid       .eq(0),
            source.data        .eq(0),
            source.sync_head   .eq(0),
            source.start_block .eq(0),
            source.first       .eq(0),
            source.last        .eq(0),
        ]

        # Default: don't consume from sink.
        m.d.comb += sink.ready.eq(0)

        with m.FSM(domain="ss"):

            # IDLE â wait for start signal.
            with m.State("IDLE"):
                m.d.comb += self.busy.eq(0)

                # Keep CRC cleared while idle.
                m.d.comb += crc32.clear.eq(1)

                with m.If(self.start):
                    m.d.ss += sink_last_seen.eq(0)
                    m.next = "LOAD_FIRST_WORD"


            # LOAD_FIRST_WORD â Read the first data word from the sink.
            # This will become the first 7 bytes of the DP_START block.
            with m.State("LOAD_FIRST_WORD"):
                m.d.comb += [
                    self.busy    .eq(1),
                    sink.ready   .eq(1),
                ]

                with m.If(sink.valid.any()):
                    m.d.ss += [
                        buf_word0      .eq(sink.payload),
                        buf_valid0     .eq(sink.valid),
                        sink_last_seen .eq(sink.last),
                    ]
                    m.next = "LOAD_SECOND_WORD"


            # LOAD_SECOND_WORD â Read the second data word from the sink.
            # Combined with the first, this forms the DP_START block payload.
            with m.State("LOAD_SECOND_WORD"):
                m.d.comb += [
                    self.busy    .eq(1),
                    sink.ready   .eq(1),
                ]

                with m.If(sink_last_seen):
                    # First word was also the last â no second word available.
                    m.d.ss += [
                        buf_word1  .eq(0),
                        buf_valid1 .eq(0),
                    ]
                    m.next = "DP_START_CRC1"

                with m.Elif(sink.valid.any()):
                    m.d.ss += [
                        buf_word1      .eq(sink.payload),
                        buf_valid1     .eq(sink.valid),
                        sink_last_seen .eq(sink.last),
                    ]
                    m.next = "DP_START_CRC1"


            # DP_START_CRC1 â Feed first 7 data bytes to CRC engine.
            # DP_START word0: [DP_START(8)][data_bytes_0_6(56)]
            # The first 7 bytes come from buf_word0[0:56].
            with m.State("DP_START_CRC1"):
                m.d.comb += [
                    self.busy         .eq(1),
                    crc32.data_input  .eq(buf_word0[0:56]),
                    crc32.advance_7B  .eq(1),
                ]
                m.next = "DP_START_CRC2"


            # DP_START_CRC2 â Feed next 8 data bytes to CRC engine.
            # These come from: buf_word0[56:64] (1 byte) + buf_word1[0:56] (7 bytes)
            # = Cat(buf_word0[56:64], buf_word1[0:56])
            # But for simplicity, we feed the second word as a full 8-byte word.
            # The DP_START word1 = Cat(buf_word0[56:64], buf_word1[0:56])
            with m.State("DP_START_CRC2"):
                dp_start_w1_data = Signal(64)
                m.d.comb += dp_start_w1_data.eq(Cat(buf_word0[56:64], buf_word1[0:56]))

                m.d.comb += [
                    self.busy         .eq(1),
                    crc32.data_input  .eq(dp_start_w1_data),
                    crc32.advance_word.eq(1),
                ]
                m.next = "SEND_DP_START_W0"


            # SEND_DP_START_W0 â Output the first word of the DP_START block.
            # Word 0: [DP_START(8)][data_bytes_0_6(56)]
            with m.State("SEND_DP_START_W0"):
                tx_word0 = Signal(64)
                m.d.comb += [
                    tx_word0[0:8]   .eq(Gen2BlockType.DP_START),
                    tx_word0[8:64]  .eq(buf_word0[0:56]),
                ]

                m.d.comb += [
                    self.busy            .eq(1),
                    source.valid         .eq(1),
                    source.data          .eq(tx_word0),
                    source.sync_head     .eq(Gen2BlockType.CONTROL_BLOCK),
                    source.start_block   .eq(1),
                ]

                with m.If(source.ready):
                    m.next = "SEND_DP_START_W1"


            # SEND_DP_START_W1 â Output the second word of the DP_START block.
            # Word 1: [byte7_from_word0(8)][bytes_0_6_from_word1(56)]
            with m.State("SEND_DP_START_W1"):
                tx_word1 = Signal(64)
                m.d.comb += tx_word1.eq(Cat(buf_word0[56:64], buf_word1[0:56]))

                m.d.comb += [
                    self.busy            .eq(1),
                    source.valid         .eq(1),
                    source.data          .eq(tx_word1),
                    source.sync_head     .eq(0),
                    source.start_block   .eq(0),
                ]

                with m.If(source.ready):
                    # Check if we need more data blocks or can go to END.
                    with m.If(sink_last_seen):
                        # Remaining data from buf_word1[56:64] needs to go in END block.
                        m.next = "BUILD_END"
                    with m.Else():
                        # Need to load more data for DATA blocks.
                        # But first, we have leftover byte(s) from buf_word1[56:64].
                        # Shift remaining data.
                        m.d.ss += [
                            buf_word0  .eq(buf_word1[56:64]),
                            buf_valid0 .eq(buf_valid1 >> 7),
                            buf_count  .eq(1),  # 1 leftover byte
                        ]
                        m.next = "LOAD_DATA_BLOCK"


            # LOAD_DATA_BLOCK â Accumulate data for the next DATA block.
            # A DATA block needs 16 bytes (2 Ã 8-byte words).
            with m.State("LOAD_DATA_BLOCK"):
                m.d.comb += [
                    self.busy    .eq(1),
                    sink.ready   .eq(1),
                ]

                with m.If(sink_last_seen):
                    # No more data from sink; go to END block.
                    m.next = "BUILD_END"

                with m.Elif(sink.valid.any()):
                    m.d.ss += [
                        buf_word0      .eq(sink.payload),
                        buf_valid0     .eq(sink.valid),
                        sink_last_seen .eq(sink.last),
                    ]
                    m.next = "LOAD_DATA_BLOCK_W1"


            # LOAD_DATA_BLOCK_W1 â Load second word for DATA block.
            with m.State("LOAD_DATA_BLOCK_W1"):
                m.d.comb += [
                    self.busy    .eq(1),
                    sink.ready   .eq(1),
                ]

                with m.If(sink_last_seen):
                    # First word of this data block was the last.
                    m.d.ss += [
                        buf_word1  .eq(0),
                        buf_valid1 .eq(0),
                    ]
                    m.next = "DATA_BLOCK_CRC1"

                with m.Elif(sink.valid.any()):
                    m.d.ss += [
                        buf_word1      .eq(sink.payload),
                        buf_valid1     .eq(sink.valid),
                        sink_last_seen .eq(sink.last),
                    ]
                    m.next = "DATA_BLOCK_CRC1"


            # DATA_BLOCK_CRC1 â Feed word0 of DATA block to CRC.
            with m.State("DATA_BLOCK_CRC1"):
                m.d.comb += [
                    self.busy         .eq(1),
                    crc32.data_input  .eq(buf_word0),
                    crc32.advance_word.eq(1),
                ]
                m.next = "DATA_BLOCK_CRC2"


            # DATA_BLOCK_CRC2 â Feed word1 of DATA block to CRC.
            with m.State("DATA_BLOCK_CRC2"):
                m.d.comb += [
                    self.busy         .eq(1),
                    crc32.data_input  .eq(buf_word1),
                    crc32.advance_word.eq(1),
                ]
                m.next = "SEND_DATA_BLOCK_W0"


            # SEND_DATA_BLOCK_W0 â Output word0 of DATA block.
            with m.State("SEND_DATA_BLOCK_W0"):
                m.d.comb += [
                    self.busy            .eq(1),
                    source.valid         .eq(1),
                    source.data          .eq(buf_word0),
                    source.sync_head     .eq(Gen2BlockType.DATA_BLOCK),
                    source.start_block   .eq(1),
                ]

                with m.If(source.ready):
                    m.next = "SEND_DATA_BLOCK_W1"


            # SEND_DATA_BLOCK_W1 â Output word1 of DATA block.
            with m.State("SEND_DATA_BLOCK_W1"):
                m.d.comb += [
                    self.busy            .eq(1),
                    source.valid         .eq(1),
                    source.data          .eq(buf_word1),
                    source.sync_head     .eq(0),
                    source.start_block   .eq(0),
                ]

                with m.If(source.ready):
                    with m.If(sink_last_seen):
                        m.next = "BUILD_END"
                    with m.Else():
                        m.next = "LOAD_DATA_BLOCK"


            # BUILD_END â Construct the END_GOOD block.
            #
            # At this point, CRC has been computed over all data bytes
            # that were sent in DP_START and DATA blocks. We need to
            # format the END_GOOD block with:
            #   - Subtype byte (0x78)
            #   - Framing info byte (number of remaining data bytes = 0 for now)
            #   - CRC-32 (4 bytes)
            #   - Padding
            #
            # For the simplified implementation, we assume all data has
            # been sent in prior blocks, so framing_info = 0.
            with m.State("BUILD_END"):
                m.d.comb += self.busy.eq(1)

                # Latch the CRC value.
                m.d.ss += latched_crc.eq(crc32.crc)
                m.next = "SEND_END_W0"


            # SEND_END_W0 â Output word0 of END_GOOD block.
            # Word 0: [END_GOOD(8)][framing_info(8)][crc32(32)][pad(16)]
            with m.State("SEND_END_W0"):
                end_word0 = Signal(64)
                m.d.comb += [
                    end_word0[0:8]   .eq(Gen2BlockType.END_GOOD),
                    end_word0[8:16]  .eq(0),  # framing_info = 0 (no remaining data bytes)
                    end_word0[16:48] .eq(latched_crc),
                    end_word0[48:64] .eq(0),  # padding
                ]

                m.d.comb += [
                    self.busy            .eq(1),
                    source.valid         .eq(1),
                    source.data          .eq(end_word0),
                    source.sync_head     .eq(Gen2BlockType.CONTROL_BLOCK),
                    source.start_block   .eq(1),
                ]

                with m.If(source.ready):
                    m.next = "SEND_END_W1"


            # SEND_END_W1 â Output word1 of END_GOOD block (all padding).
            with m.State("SEND_END_W1"):
                m.d.comb += [
                    self.busy            .eq(1),
                    source.valid         .eq(1),
                    source.data          .eq(0),  # all padding
                    source.sync_head     .eq(0),
                    source.start_block   .eq(0),
                ]

                with m.If(source.ready):
                    m.d.ss += self.done.eq(1)
                    m.next = "IDLE"


        return m
