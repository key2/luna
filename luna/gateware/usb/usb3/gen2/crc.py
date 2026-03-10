#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" CRC computation gateware for USB 3.1 Gen2 (64-bit datapath).

Uses :mod:`amaranth.lib.crc` to generate the parallel CRC XOR matrices
instead of hand-expanded equations, while keeping the same register-
management pattern as the Gen1 CRC engines in
:mod:`luna.gateware.usb.usb3.link.crc`.
"""

from amaranth import *
from amaranth.lib.crc import Algorithm


# ---------------------------------------------------------------------------
# USB 3.1 CRC algorithm definitions (from USB 3.2 spec §7.2.1.2)
# ---------------------------------------------------------------------------

#: CRC-16 used for header packets.
USB3_CRC16 = Algorithm(
    crc_width=16,
    polynomial=0x8005,
    initial_crc=0xFFFF,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xFFFF,
)

#: CRC-32 used for data packet payloads.
USB3_CRC32 = Algorithm(
    crc_width=32,
    polynomial=0x04C11DB7,
    initial_crc=0xFFFFFFFF,
    reflect_input=True,
    reflect_output=True,
    xor_output=0xFFFFFFFF,
)


def _build_next_crc(m, *, algorithm, data_width, crc_reg, data_in):
    """Build combinational logic for the next CRC state.

    Uses the XOR matrices from :class:`amaranth.lib.crc.Parameters` to
    generate the parallel CRC computation, but operates on externally
    managed signals rather than a Processor's own register.

    Parameters
    ----------
    m : Module
        The Amaranth module to attach combinational statements to.
    algorithm : Algorithm
        The CRC algorithm definition.
    data_width : int
        Width of the data word to process (in bits).
    crc_reg : Signal
        The current CRC register value (unreflected, un-XORed internal state).
    data_in : Signal
        The input data word.

    Returns
    -------
    Signal
        A signal carrying the next CRC register value (internal state,
        before reflect/XOR output transformation).
    """
    # Obtain the precomputed matrices directly from Parameters,
    # avoiding the creation of a Processor (and its UnusedElaboratable warning).
    params = algorithm(data_width=data_width)
    matrix_f, matrix_g = params._matrices()

    crc_width = params._crc_width
    reflect_input = params._reflect_input

    # Optionally bit-reflect the input data (matching Processor behaviour).
    if reflect_input:
        reflected = Signal(data_width, name=f"reflected_{data_width}")
        m.d.comb += reflected.eq(data_in[:data_width][::-1])
        effective_data = reflected
    else:
        effective_data = data_in[:data_width]

    # Compute each bit of the next CRC state.
    next_crc = Signal(crc_width, name=f"next_crc_{data_width}")
    for i in range(crc_width):
        bit_terms = []
        for j in range(crc_width):
            if matrix_f[j][i]:
                bit_terms.append(crc_reg[j])
        for j in range(data_width):
            if matrix_g[j][i]:
                bit_terms.append(effective_data[j])

        if len(bit_terms) == 0:
            m.d.comb += next_crc[i].eq(0)
        elif len(bit_terms) == 1:
            m.d.comb += next_crc[i].eq(bit_terms[0])
        else:
            # XOR all terms together.
            expr = bit_terms[0]
            for t in bit_terms[1:]:
                expr = expr ^ t
            m.d.comb += next_crc[i].eq(expr)

    return next_crc


def _crc_output(crc_reg, *, reflect_output, xor_output, crc_width):
    """Produce the final CRC output from the internal register.

    Applies the reflect-output and XOR-output transformations that
    :class:`amaranth.lib.crc.Processor` performs combinationally.
    """
    if reflect_output:
        return crc_reg[::-1] ^ xor_output
    else:
        return crc_reg ^ xor_output


# ---------------------------------------------------------------------------
# Gen2 Header Packet CRC-16
# ---------------------------------------------------------------------------

class Gen2HeaderCRC(Elaboratable):
    """CRC-16 engine for USB 3.1 Gen2 header packets (64-bit datapath).

    Gen2 headers are 12 bytes (96 bits) = 1.5 × 64-bit words.  The CRC-16
    covers bytes 0–11 and the result is placed in bytes 12–13.

    This engine supports both full 64-bit word advances and a 32-bit
    partial-word advance for the second half of the header.

    Attributes
    ----------
    data_input : Signal(64), input
        Input data word.
    crc : Signal(16), output
        Current CRC-16 output value.
    advance_crc : Signal(), input
        Advance CRC by one full 64-bit word.
    advance_4B : Signal(), input
        Advance CRC by 4 bytes (32 bits) — for the second header word.
    clear : Signal(), input
        Reset CRC to its initial value.

    Parameters
    ----------
    initial_value : int
        Initial value of the CRC register (default: 0xFFFF).
    """

    def __init__(self, initial_value=0xFFFF):
        self._initial_value = initial_value

        #
        # I/O port
        #
        self.clear       = Signal()
        self.data_input  = Signal(64)
        self.advance_crc = Signal()
        self.advance_4B  = Signal()
        self.crc         = Signal(16, init=initial_value)

    def elaborate(self, platform):
        m = Module()

        # Internal CRC register (unreflected, un-XORed state).
        crc = Signal(16, init=self._initial_value)

        # Build combinational next-CRC for 64-bit and 32-bit widths.
        next_crc_64 = _build_next_crc(
            m, algorithm=USB3_CRC16, data_width=64,
            crc_reg=crc, data_in=self.data_input,
        )
        next_crc_32 = _build_next_crc(
            m, algorithm=USB3_CRC16, data_width=32,
            crc_reg=crc, data_in=self.data_input,
        )

        # Register update logic (ss clock domain).
        with m.If(self.clear):
            m.d.ss += crc.eq(self._initial_value)
        with m.Elif(self.advance_crc):
            m.d.ss += crc.eq(next_crc_64)
        with m.Elif(self.advance_4B):
            m.d.ss += crc.eq(next_crc_32)

        # Output: apply reflect + XOR transformation.
        m.d.comb += self.crc.eq(
            _crc_output(crc, reflect_output=True, xor_output=0xFFFF, crc_width=16)
        )

        return m


# ---------------------------------------------------------------------------
# Gen2 Data Packet Payload CRC-32
# ---------------------------------------------------------------------------

class Gen2DataCRC(Elaboratable):
    """CRC-32 engine for USB 3.1 Gen2 data packets (64-bit datapath).

    Data packets can end at any byte boundary within a 64-bit word, so
    this engine supports partial-word advances from 1 to 7 bytes in
    addition to the full 8-byte (64-bit) word advance.

    Attributes
    ----------
    data_input : Signal(64), input
        Input data word.
    crc : Signal(32), output
        Current CRC-32 output value.
    advance_word : Signal(), input
        Advance CRC by a full 64-bit word (8 bytes).
    advance_7B : Signal(), input
        Advance CRC by 7 bytes (56 bits).
    advance_6B : Signal(), input
        Advance CRC by 6 bytes (48 bits).
    advance_5B : Signal(), input
        Advance CRC by 5 bytes (40 bits).
    advance_4B : Signal(), input
        Advance CRC by 4 bytes (32 bits).
    advance_3B : Signal(), input
        Advance CRC by 3 bytes (24 bits).
    advance_2B : Signal(), input
        Advance CRC by 2 bytes (16 bits).
    advance_1B : Signal(), input
        Advance CRC by 1 byte (8 bits).
    clear : Signal(), input
        Reset CRC to its initial value.

    Parameters
    ----------
    initial_value : int
        Initial value of the CRC register (default: 0xFFFFFFFF).
    """

    def __init__(self, initial_value=0xFFFFFFFF):
        self._initial_value = initial_value

        #
        # I/O port
        #
        self.clear        = Signal()

        self.data_input   = Signal(64)
        self.advance_word = Signal()
        self.advance_7B   = Signal()
        self.advance_6B   = Signal()
        self.advance_5B   = Signal()
        self.advance_4B   = Signal()
        self.advance_3B   = Signal()
        self.advance_2B   = Signal()
        self.advance_1B   = Signal()

        self.crc          = Signal(32)

    def elaborate(self, platform):
        m = Module()

        # Internal CRC register (unreflected, un-XORed state).
        crc = Signal(32, init=self._initial_value)

        # Build combinational next-CRC for each supported data width.
        # Data widths: 64, 56, 48, 40, 32, 24, 16, 8 bits.
        next_crc = {}
        for n_bytes in [8, 7, 6, 5, 4, 3, 2, 1]:
            width = n_bytes * 8
            next_crc[n_bytes] = _build_next_crc(
                m, algorithm=USB3_CRC32, data_width=width,
                crc_reg=crc, data_in=self.data_input,
            )

        # Register update logic (ss clock domain).
        # The advance signals are mutually exclusive.
        with m.If(self.clear):
            m.d.ss += crc.eq(self._initial_value)
        with m.Elif(self.advance_word):
            m.d.ss += crc.eq(next_crc[8])
        with m.Elif(self.advance_7B):
            m.d.ss += crc.eq(next_crc[7])
        with m.Elif(self.advance_6B):
            m.d.ss += crc.eq(next_crc[6])
        with m.Elif(self.advance_5B):
            m.d.ss += crc.eq(next_crc[5])
        with m.Elif(self.advance_4B):
            m.d.ss += crc.eq(next_crc[4])
        with m.Elif(self.advance_3B):
            m.d.ss += crc.eq(next_crc[3])
        with m.Elif(self.advance_2B):
            m.d.ss += crc.eq(next_crc[2])
        with m.Elif(self.advance_1B):
            m.d.ss += crc.eq(next_crc[1])

        # Output: apply reflect + XOR transformation.
        m.d.comb += self.crc.eq(
            _crc_output(crc, reflect_output=True,
                        xor_output=0xFFFFFFFF, crc_width=32)
        )

        return m
