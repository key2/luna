#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Interfaces and data types for USB 3.1 Gen2 (10 Gbps, 128b/132b encoding). """

from amaranth import *

from ....stream import StreamInterface

# Re-export Gen2PIPEInterface from the canonical location in gateware/interface/pipe.py.
# This keeps backward compatibility for code that imports from this module.
from ....interface.pipe import Gen2PIPEInterface


class Gen2BlockType:
    """128b/132b block type constants for USB 3.1 Gen2.

    Gen2 uses 128b/132b encoding, where each block has a 4-bit sync header
    followed by 128 bits (16 bytes) of payload. The sync header distinguishes
    data blocks from control blocks.

    At the PIPE level, the PHY presents 64-bit words with a 4-bit sync header
    field and a start-of-block indicator.
    """

    # Sync header values (2-bit logical, stored in 4-bit PHY field)
    DATA_BLOCK    = 0x3   # Data block sync header (binary: 0011)
    CONTROL_BLOCK = 0xC   # Control block sync header (binary: 1100)

    # Control block subtypes (first byte of block payload)
    HP_START   = 0x33  # Header Packet Start
    DP_START   = 0x66  # Data Packet Start
    END_GOOD   = 0x78  # End Good (CRC valid)
    END_BAD    = 0x87  # End Bad (CRC invalid)
    LINK_CMD   = 0x4B  # Link Command
    NOP        = 0x00  # No Operation


class Gen2RawSuperSpeedStream(StreamInterface):
    """Variant of StreamInterface for carrying raw USB 3.1 Gen2 data.

    Gen2 uses 128b/132b block encoding rather than 8b/10b symbol encoding.
    Each 64-bit word on the PIPE interface is accompanied by a sync header
    that indicates whether the block is a data block or a control block,
    and a start-of-block flag.

    This stream carries the raw PHY-level data including framing information,
    analogous to :class:`USBRawSuperSpeedStream` for Gen1.

    Parameters
    ----------
    None (fixed at 64-bit payload with sync_head and start_block fields)

    Attributes
    ----------
    payload : Signal(64)
        The 64-bit data word.
    sync_head : Signal(4)
        The 128b/132b sync header for this word.
    start_block : Signal(1)
        Indicates this word is the start of a new block.
    valid : Signal(1)
        Standard stream valid signal.
    ready : Signal(1)
        Standard stream ready/backpressure signal.
    first : Signal(1)
        Standard stream first-of-packet signal.
    last : Signal(1)
        Standard stream last-of-packet signal.
    """

    def __init__(self):
        super().__init__(payload_width=64, extra_fields=[
            ('sync_head',    4),
            ('start_block',  1),
        ])


class Gen2SuperSpeedStreamInterface(StreamInterface):
    """Convenience variant of StreamInterface sized for Gen2 SuperSpeed application data.

    This carries 64-bit (8-byte) application-layer data words with per-byte
    valid bits, analogous to :class:`SuperSpeedStreamInterface` for Gen1
    (which carries 32-bit / 4-byte words with 4 valid bits).

    Parameters
    ----------
    None (fixed at 64-bit payload with 8-bit valid)

    Attributes
    ----------
    payload : Signal(64)
        The 64-bit data payload.
    valid : Signal(8)
        Per-byte valid indicators (one bit per byte of payload).
    ready : Signal(1)
        Standard stream ready/backpressure signal.
    first : Signal(1)
        Standard stream first-of-packet signal.
    last : Signal(1)
        Standard stream last-of-packet signal.
    """

    def __init__(self):
        super().__init__(payload_width=64, valid_width=8)
