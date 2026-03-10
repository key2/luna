#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Coding utilities for USB 3.1 Gen2 128b/132b block encoding.

Gen2 replaces the 8b/10b symbol encoding of Gen1 with 128b/132b block
encoding. Each block consists of a 4-bit sync header followed by 128 bits
of payload. The sync header distinguishes data blocks (sync=0x3) from
control blocks (sync=0xC). Control blocks carry a subtype byte in the
first byte of the payload that identifies the block's purpose.

This module provides helper functions for working with Gen2 block types,
analogous to :mod:`luna.gateware.usb.usb3.physical.coding` for Gen1.
"""

from amaranth import *

from .interfaces import Gen2BlockType


def is_data_block(sync_head):
    """Return an Amaranth expression that is true when *sync_head* indicates a data block.

    Parameters
    ----------
    sync_head : Signal(4) or int
        The 4-bit sync header value from the PIPE interface.

    Returns
    -------
    Value
        Amaranth comparison expression (``sync_head == 0x3``).
    """
    return sync_head == Gen2BlockType.DATA_BLOCK


def is_control_block(sync_head):
    """Return an Amaranth expression that is true when *sync_head* indicates a control block.

    Parameters
    ----------
    sync_head : Signal(4) or int
        The 4-bit sync header value from the PIPE interface.

    Returns
    -------
    Value
        Amaranth comparison expression (``sync_head == 0xC``).
    """
    return sync_head == Gen2BlockType.CONTROL_BLOCK


def get_control_subtype(data):
    """Extract the control block subtype from the first byte of a 64-bit data word.

    In a control block, the first byte of the payload identifies the block
    subtype (e.g. HP_START, DP_START, END_GOOD, LINK_CMD, etc.).

    Parameters
    ----------
    data : Signal(64)
        The 64-bit data word from the PIPE interface.

    Returns
    -------
    Value
        The low 8 bits of *data* (``data[0:8]``).
    """
    return data[0:8]


def stream_matches_block_type(stream, block_type):
    """Check if a Gen2 raw stream word matches a specific block type.

    For control blocks (block_type is one of the control subtypes like
    ``Gen2BlockType.HP_START``), this checks that:
      1. The stream is valid,
      2. The sync header indicates a control block, and
      3. The first byte of the payload matches *block_type*.

    For data blocks (``block_type == Gen2BlockType.DATA_BLOCK``), this
    checks that:
      1. The stream is valid, and
      2. The sync header indicates a data block.

    Parameters
    ----------
    stream : Gen2RawSuperSpeedStream
        A Gen2 raw stream carrying ``sync_head`` and ``payload`` fields.
    block_type : int
        One of the :class:`Gen2BlockType` constants.

    Returns
    -------
    Value
        Amaranth expression that is true when the stream matches.

    Notes
    -----
    The stream must have ``valid``, ``sync_head``, and ``payload`` (or
    ``data``) attributes, as provided by :class:`Gen2RawSuperSpeedStream`.
    """
    if block_type == Gen2BlockType.DATA_BLOCK:
        return (
            stream.valid &
            is_data_block(stream.sync_head)
        )
    else:
        # For control subtypes, match the sync header AND the first payload byte.
        return (
            stream.valid &
            is_control_block(stream.sync_head) &
            (get_control_subtype(stream.data) == block_type)
        )
