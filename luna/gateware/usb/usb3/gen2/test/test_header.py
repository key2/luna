#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""Unit tests for Gen2 Header Packet Receiver and Transmitter."""

import unittest

from amaranth import *
from amaranth.sim import *


# ---------------------------------------------------------------------------
# Software CRC-16 reference
# ---------------------------------------------------------------------------

def _reflect_bits(value, width):
    """Reflect (bit-reverse) *value* over *width* bits."""
    result = 0
    for i in range(width):
        if value & (1 << i):
            result |= 1 << (width - 1 - i)
    return result


def _sw_crc16_usb3(data_bytes):
    """Software USB 3 CRC-16 (poly=0x8005, init=0xFFFF, refin/refout, xorout=0xFFFF)."""
    crc = 0xFFFF
    poly = 0x8005
    for byte in data_bytes:
        byte = _reflect_bits(byte, 8)
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    crc = _reflect_bits(crc, 16)
    crc ^= 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# Header Packet Receiver Tests
# ---------------------------------------------------------------------------

class TestGen2HeaderPacketReceiver(unittest.TestCase):
    """Tests for Gen2HeaderPacketReceiver."""

    def test_elaboration(self):
        """Verify the module elaborates without errors."""
        from luna.gateware.usb.usb3.gen2.link.header import Gen2HeaderPacketReceiver
        dut = Gen2HeaderPacketReceiver()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_valid_header_reception(self):
        """Verify reception of a header packet with valid CRC-16.

        Build an HP_START block with a 12-byte header and correct CRC-16,
        feed it to the receiver, and verify the header is extracted and
        CRC is reported as good.
        """
        from luna.gateware.usb.usb3.gen2.link.header import Gen2HeaderPacketReceiver
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        dut = Gen2HeaderPacketReceiver()

        # 12-byte test header.
        header_bytes = bytes(range(12))  # 0x00..0x0B
        crc16 = _sw_crc16_usb3(header_bytes)

        # Build the HP_START block words.
        # Word 0: [HP_START(8)][header_bytes_0_6(56)]
        word0 = Gen2BlockType.HP_START
        for i in range(7):
            word0 |= header_bytes[i] << (8 + i * 8)

        # Word 1: [header_bytes_7_11(40)][crc16(16)][padding(8)]
        word1 = 0
        for i in range(5):
            word1 |= header_bytes[7 + i] << (i * 8)
        word1 |= (crc16 & 0xFFFF) << 40
        # padding byte at bits 56-63 is zero

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            # Present the HP_START block.
            yield dut.word0.eq(word0)
            yield dut.word1.eq(word1)
            yield dut.hp_start_strobe.eq(1)
            yield Tick("ss")
            yield dut.hp_start_strobe.eq(0)

            # Wait for the CRC pipeline (IDLE → CRC_CYCLE1 → CRC_CYCLE2 → CRC_CYCLE3 → CHECK_CRC).
            for _ in range(5):
                yield Tick("ss")

            result["new_header"] = yield dut.new_header
            result["crc_good"] = yield dut.crc_good
            result["crc_bad"] = yield dut.crc_bad
            result["header_data"] = yield dut.header_data

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["new_header"], 1, "new_header should be asserted")
        self.assertEqual(result["crc_good"], 1, "crc_good should be asserted")
        self.assertEqual(result["crc_bad"], 0, "crc_bad should not be asserted")

        # Verify the extracted header data matches.
        # header_data = Cat(header_bytes_0_6, header_bytes_7_11)
        expected_header = int.from_bytes(header_bytes, "little")
        # The header_data is 96 bits; mask to 96 bits.
        self.assertEqual(
            result["header_data"] & ((1 << 96) - 1),
            expected_header & ((1 << 96) - 1),
            "Header data should match input",
        )

    def test_bad_crc_detected(self):
        """Verify that a header with bad CRC-16 is flagged."""
        from luna.gateware.usb.usb3.gen2.link.header import Gen2HeaderPacketReceiver
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        dut = Gen2HeaderPacketReceiver()

        header_bytes = bytes(range(12))
        bad_crc = 0xBEEF  # Intentionally wrong

        word0 = Gen2BlockType.HP_START
        for i in range(7):
            word0 |= header_bytes[i] << (8 + i * 8)

        word1 = 0
        for i in range(5):
            word1 |= header_bytes[7 + i] << (i * 8)
        word1 |= (bad_crc & 0xFFFF) << 40

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            yield dut.word0.eq(word0)
            yield dut.word1.eq(word1)
            yield dut.hp_start_strobe.eq(1)
            yield Tick("ss")
            yield dut.hp_start_strobe.eq(0)

            for _ in range(5):
                yield Tick("ss")

            result["new_header"] = yield dut.new_header
            result["crc_good"] = yield dut.crc_good
            result["crc_bad"] = yield dut.crc_bad

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["new_header"], 1, "new_header should still be asserted")
        self.assertEqual(result["crc_good"], 0, "crc_good should NOT be asserted")
        self.assertEqual(result["crc_bad"], 1, "crc_bad should be asserted")


# ---------------------------------------------------------------------------
# Header Packet Transmitter Tests
# ---------------------------------------------------------------------------

class TestGen2HeaderPacketTransmitter(unittest.TestCase):
    """Tests for Gen2HeaderPacketTransmitter."""

    def test_elaboration(self):
        """Verify the module elaborates without errors."""
        from luna.gateware.usb.usb3.gen2.link.header import Gen2HeaderPacketTransmitter
        dut = Gen2HeaderPacketTransmitter()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_header_transmission_format(self):
        """Verify the transmitted HP_START block format.

        Trigger a send with a known 12-byte header, assert ready on the
        source, and verify:
        - Word 0 has CONTROL_BLOCK sync header and start_block=1
        - Word 0 contains HP_START subtype + header bytes 0-6
        - Word 1 contains header bytes 7-11 + CRC-16 + padding
        """
        from luna.gateware.usb.usb3.gen2.link.header import Gen2HeaderPacketTransmitter
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        dut = Gen2HeaderPacketTransmitter()

        header_bytes = bytes(range(12))
        header_data = int.from_bytes(header_bytes, "little")

        result = {}

        def testbench():
            yield Tick("ss")

            # Trigger send.
            yield dut.header_data.eq(header_data)
            yield dut.send.eq(1)
            yield Tick("ss")
            yield dut.send.eq(0)

            # Wait for CRC computation (COMPUTE_CRC1 → COMPUTE_CRC2 → COMPUTE_CRC3).
            yield Tick("ss")
            yield Tick("ss")
            yield Tick("ss")

            # SEND_WORD0 state: assert ready.
            yield dut.source.ready.eq(1)
            yield Tick("ss")

            result["w0_valid"] = yield dut.source.valid
            result["w0_sync_head"] = yield dut.source.sync_head
            result["w0_start_block"] = yield dut.source.start_block
            result["w0_data"] = yield dut.source.data

            yield Tick("ss")

            # SEND_WORD1 state.
            result["w1_valid"] = yield dut.source.valid
            result["w1_start_block"] = yield dut.source.start_block
            result["w1_data"] = yield dut.source.data

            yield Tick("ss")

            result["done"] = yield dut.done

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        # Verify word 0 format.
        self.assertEqual(result["w0_valid"], 1)
        self.assertEqual(result["w0_sync_head"], Gen2BlockType.CONTROL_BLOCK)
        self.assertEqual(result["w0_start_block"], 1)

        # Verify subtype byte.
        w0_data = result["w0_data"]
        subtype = w0_data & 0xFF
        self.assertEqual(subtype, Gen2BlockType.HP_START, "Subtype should be HP_START")

        # Verify header bytes 0-6 in word0[8:64].
        for i in range(7):
            extracted_byte = (w0_data >> (8 + i * 8)) & 0xFF
            self.assertEqual(
                extracted_byte, header_bytes[i],
                f"Header byte {i} mismatch in word0",
            )

        # Verify word 1 format.
        self.assertEqual(result["w1_valid"], 1)
        self.assertEqual(result["w1_start_block"], 0)

        # Verify header bytes 7-11 in word1[0:40].
        w1_data = result["w1_data"]
        for i in range(5):
            extracted_byte = (w1_data >> (i * 8)) & 0xFF
            self.assertEqual(
                extracted_byte, header_bytes[7 + i],
                f"Header byte {7 + i} mismatch in word1",
            )

        # Verify CRC-16 in word1[40:56].
        expected_crc = _sw_crc16_usb3(header_bytes)
        extracted_crc = (w1_data >> 40) & 0xFFFF
        self.assertEqual(
            extracted_crc, expected_crc,
            f"CRC-16 mismatch: got 0x{extracted_crc:04X}, expected 0x{expected_crc:04X}",
        )

        # Verify done strobe.
        self.assertEqual(result["done"], 1, "done should be asserted after transmission")


if __name__ == "__main__":
    unittest.main()
