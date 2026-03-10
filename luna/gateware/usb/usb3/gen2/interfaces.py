#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Interfaces and data types for USB 3.1 Gen2 (10 Gbps, 128b/132b encoding). """

from amaranth import *

from ....stream import StreamInterface


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


class Gen2PIPEInterface:
    """PIPE interface for USB 3.1 Gen2 (64-bit @ ~156.25 MHz).

    This is a signal bundle (not Elaboratable) that mirrors the signals
    exposed by a Gen2 PHY such as the usb31dec hard IP. The interface
    carries 64-bit data words with 128b/132b block framing instead of
    the 8b/10b symbol encoding used by Gen1.

    The signal directions are given from the MAC perspective:
    TX signals are driven by the MAC toward the PHY, and RX signals
    are driven by the PHY toward the MAC.

    Parameters
    ----------
    None

    Attributes
    ----------
    pclk : Signal(), output from PHY
        PIPE clock output from the PHY (~156.25 MHz for Gen2).

    tx_data : Signal(64), input to PHY
        Transmit data bus (64-bit).
    tx_sync_head : Signal(4), input to PHY
        Transmit sync header (DATA=0x3, CONTROL=0xC).
    tx_start_block : Signal(), input to PHY
        Indicates the start of a new 128b/132b block on the TX path.
    tx_data_valid : Signal(), input to PHY
        Indicates that the TX data bus carries valid data.

    rx_data : Signal(64), output from PHY
        Receive data bus (64-bit).
    rx_sync_head : Signal(4), output from PHY
        Receive sync header (DATA=0x3, CONTROL=0xC).
    rx_start_block : Signal(), output from PHY
        Indicates the start of a new 128b/132b block on the RX path.
    rx_data_valid : Signal(), output from PHY
        Indicates that the RX data bus carries valid data.

    tx_detect_rx_loopback : Signal(), input to PHY
        Directs the PHY to perform receiver detection or loopback.
    tx_elec_idle : Signal(reset=1), input to PHY
        Directs the PHY transmitter into Electrical Idle.
    rx_polarity : Signal(), input to PHY
        If asserted, the PHY receiver inverts the received data.
    rx_termination : Signal(), input to PHY
        If asserted, the PHY presents receiver terminations.
    power_down : Signal(2, reset=0b11), input to PHY
        Power management state (P0=0b00, P1=0b01, P2=0b10, P3=0b11).
    elasticity_buf_mode : Signal(), input to PHY
        Elastic buffer operating mode.

    rx_elec_idle : Signal(), output from PHY
        Indicates detection of Electrical Idle on the receive path.
    rx_status : Signal(3), output from PHY
        Receive status indication.
    phy_status : Signal(), output from PHY
        PHY operation completion status.
    power_present : Signal(), output from PHY
        Indicates voltage is present on Vbus.
    """

    def __init__(self):
        #
        # Clock
        #
        self.pclk                   = Signal()

        #
        # TX data path
        #
        self.tx_data                = Signal(64)
        self.tx_sync_head           = Signal(4)
        self.tx_start_block         = Signal()
        self.tx_data_valid          = Signal()

        #
        # RX data path
        #
        self.rx_data                = Signal(64)
        self.rx_sync_head           = Signal(4)
        self.rx_start_block         = Signal()
        self.rx_data_valid          = Signal()

        #
        # Control signals
        #
        self.tx_detect_rx_loopback  = Signal()
        self.tx_elec_idle           = Signal(reset=1)
        self.rx_polarity            = Signal()
        self.rx_termination         = Signal()
        self.power_down             = Signal(2, reset=0b11)  # P3 default
        self.elasticity_buf_mode    = Signal()

        #
        # Status signals
        #
        self.rx_elec_idle           = Signal()
        self.rx_status              = Signal(3)
        self.phy_status             = Signal()
        self.power_present          = Signal()


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
