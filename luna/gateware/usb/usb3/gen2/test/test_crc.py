#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""Unit tests for Gen2 CRC engines (CRC-16 and CRC-32, 64-bit datapath)."""

import unittest

from amaranth import *
from amaranth.sim import *


# ---------------------------------------------------------------------------
# Software CRC reference implementations
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


def _sw_crc32_usb3(data_bytes):
    """Software USB 3 CRC-32 (poly=0x04C11DB7, init=0xFFFFFFFF, refin/refout, xorout=0xFFFFFFFF)."""
    crc = 0xFFFFFFFF
    poly = 0x04C11DB7
    for byte in data_bytes:
        byte = _reflect_bits(byte, 8)
        crc ^= byte << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ poly) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
    crc = _reflect_bits(crc, 32)
    crc ^= 0xFFFFFFFF
    return crc


# ---------------------------------------------------------------------------
# CRC-16 Tests
# ---------------------------------------------------------------------------

class TestGen2HeaderCRC(unittest.TestCase):
    """Tests for Gen2HeaderCRC (CRC-16, 64-bit input)."""

    def test_elaboration(self):
        """Verify the module elaborates without errors."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2HeaderCRC
        dut = Gen2HeaderCRC()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_known_crc16_value(self):
        """Verify CRC-16 against a known 8-byte test vector."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2HeaderCRC
        dut = Gen2HeaderCRC()

        # Test vector: 8 bytes of data (little-endian 64-bit word).
        test_bytes = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
        test_data = int.from_bytes(test_bytes, "little")
        expected_crc = _sw_crc16_usb3(test_bytes)

        result = []

        def testbench():
            # Clear CRC.
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            # Feed 8 bytes (64 bits).
            yield dut.data_input.eq(test_data)
            yield dut.advance_crc.eq(1)
            yield Tick("ss")
            yield dut.advance_crc.eq(0)
            yield Tick("ss")

            # Read CRC.
            crc_val = yield dut.crc
            result.append(crc_val)

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result[0], expected_crc,
            f"CRC-16 mismatch: got 0x{result[0]:04X}, expected 0x{expected_crc:04X}",
        )

    def test_crc16_clear_resets(self):
        """Verify that clear resets CRC to its initial value."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2HeaderCRC
        dut = Gen2HeaderCRC()

        results = []

        def testbench():
            # Read initial CRC (should be the identity CRC output).
            yield Tick("ss")
            initial_crc = yield dut.crc
            results.append(("initial", initial_crc))

            # Feed some data.
            yield dut.data_input.eq(0xDEADBEEFCAFEBABE)
            yield dut.advance_crc.eq(1)
            yield Tick("ss")
            yield dut.advance_crc.eq(0)
            yield Tick("ss")

            after_data = yield dut.crc
            results.append(("after_data", after_data))

            # Clear.
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            after_clear = yield dut.crc
            results.append(("after_clear", after_clear))

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        initial_crc = results[0][1]
        after_data = results[1][1]
        after_clear = results[2][1]

        # After feeding data, CRC should differ from initial.
        self.assertNotEqual(after_data, initial_crc, "CRC should change after data")
        # After clear, CRC should return to initial value.
        self.assertEqual(after_clear, initial_crc, "CRC should reset after clear")

    def test_crc16_partial_word(self):
        """Verify CRC-16 with a 4-byte (32-bit) partial advance."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2HeaderCRC
        dut = Gen2HeaderCRC()

        # Test vector: 4 bytes.
        test_bytes = bytes([0xAA, 0xBB, 0xCC, 0xDD])
        test_data = int.from_bytes(test_bytes, "little")
        expected_crc = _sw_crc16_usb3(test_bytes)

        result = []

        def testbench():
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            # Feed 4 bytes via advance_4B.
            yield dut.data_input.eq(test_data)
            yield dut.advance_4B.eq(1)
            yield Tick("ss")
            yield dut.advance_4B.eq(0)
            yield Tick("ss")

            crc_val = yield dut.crc
            result.append(crc_val)

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result[0], expected_crc,
            f"CRC-16 (4B) mismatch: got 0x{result[0]:04X}, expected 0x{expected_crc:04X}",
        )

    def test_crc16_multi_word(self):
        """Verify CRC-16 over 8 bytes + 4 bytes (12-byte header)."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2HeaderCRC
        dut = Gen2HeaderCRC()

        # 12-byte test vector (typical header size).
        test_bytes = bytes(range(12))  # 0x00..0x0B
        word0 = int.from_bytes(test_bytes[0:8], "little")
        word1 = int.from_bytes(test_bytes[8:12], "little")
        expected_crc = _sw_crc16_usb3(test_bytes)

        result = []

        def testbench():
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            # Feed first 8 bytes.
            yield dut.data_input.eq(word0)
            yield dut.advance_crc.eq(1)
            yield Tick("ss")
            yield dut.advance_crc.eq(0)
            yield Tick("ss")

            # Feed next 4 bytes.
            yield dut.data_input.eq(word1)
            yield dut.advance_4B.eq(1)
            yield Tick("ss")
            yield dut.advance_4B.eq(0)
            yield Tick("ss")

            crc_val = yield dut.crc
            result.append(crc_val)

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result[0], expected_crc,
            f"CRC-16 (12B) mismatch: got 0x{result[0]:04X}, expected 0x{expected_crc:04X}",
        )


# ---------------------------------------------------------------------------
# CRC-32 Tests
# ---------------------------------------------------------------------------

class TestGen2DataCRC(unittest.TestCase):
    """Tests for Gen2DataCRC (CRC-32, 64-bit input with partial-word support)."""

    def test_elaboration(self):
        """Verify the module elaborates without errors."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC
        dut = Gen2DataCRC()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_known_crc32_value(self):
        """Verify CRC-32 against a known 8-byte test vector."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC
        dut = Gen2DataCRC()

        test_bytes = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
        test_data = int.from_bytes(test_bytes, "little")
        expected_crc = _sw_crc32_usb3(test_bytes)

        result = []

        def testbench():
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            yield dut.data_input.eq(test_data)
            yield dut.advance_word.eq(1)
            yield Tick("ss")
            yield dut.advance_word.eq(0)
            yield Tick("ss")

            crc_val = yield dut.crc
            result.append(crc_val)

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result[0], expected_crc,
            f"CRC-32 mismatch: got 0x{result[0]:08X}, expected 0x{expected_crc:08X}",
        )

    def test_partial_word_3B(self):
        """Verify CRC-32 with a 3-byte partial advance."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC
        dut = Gen2DataCRC()

        test_bytes = bytes([0xAA, 0xBB, 0xCC])
        test_data = int.from_bytes(test_bytes, "little")
        expected_crc = _sw_crc32_usb3(test_bytes)

        result = []

        def testbench():
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            yield dut.data_input.eq(test_data)
            yield dut.advance_3B.eq(1)
            yield Tick("ss")
            yield dut.advance_3B.eq(0)
            yield Tick("ss")

            crc_val = yield dut.crc
            result.append(crc_val)

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result[0], expected_crc,
            f"CRC-32 (3B) mismatch: got 0x{result[0]:08X}, expected 0x{expected_crc:08X}",
        )

    def test_partial_word_1B(self):
        """Verify CRC-32 with a 1-byte partial advance."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC
        dut = Gen2DataCRC()

        test_bytes = bytes([0x42])
        test_data = int.from_bytes(test_bytes, "little")
        expected_crc = _sw_crc32_usb3(test_bytes)

        result = []

        def testbench():
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            yield dut.data_input.eq(test_data)
            yield dut.advance_1B.eq(1)
            yield Tick("ss")
            yield dut.advance_1B.eq(0)
            yield Tick("ss")

            crc_val = yield dut.crc
            result.append(crc_val)

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result[0], expected_crc,
            f"CRC-32 (1B) mismatch: got 0x{result[0]:08X}, expected 0x{expected_crc:08X}",
        )

    def test_multi_word_crc(self):
        """Verify CRC-32 over two consecutive 64-bit words (16 bytes)."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC
        dut = Gen2DataCRC()

        test_bytes = bytes(range(16))  # 0x00..0x0F
        word0 = int.from_bytes(test_bytes[0:8], "little")
        word1 = int.from_bytes(test_bytes[8:16], "little")
        expected_crc = _sw_crc32_usb3(test_bytes)

        result = []

        def testbench():
            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            # Feed first 8 bytes.
            yield dut.data_input.eq(word0)
            yield dut.advance_word.eq(1)
            yield Tick("ss")
            yield dut.advance_word.eq(0)
            yield Tick("ss")

            # Feed next 8 bytes.
            yield dut.data_input.eq(word1)
            yield dut.advance_word.eq(1)
            yield Tick("ss")
            yield dut.advance_word.eq(0)
            yield Tick("ss")

            crc_val = yield dut.crc
            result.append(crc_val)

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result[0], expected_crc,
            f"CRC-32 (16B) mismatch: got 0x{result[0]:08X}, expected 0x{expected_crc:08X}",
        )

    def test_crc32_clear_resets(self):
        """Verify that clear resets CRC-32 to its initial value."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC
        dut = Gen2DataCRC()

        results = []

        def testbench():
            yield Tick("ss")
            initial_crc = yield dut.crc
            results.append(("initial", initial_crc))

            yield dut.data_input.eq(0xDEADBEEFCAFEBABE)
            yield dut.advance_word.eq(1)
            yield Tick("ss")
            yield dut.advance_word.eq(0)
            yield Tick("ss")

            after_data = yield dut.crc
            results.append(("after_data", after_data))

            yield dut.clear.eq(1)
            yield Tick("ss")
            yield dut.clear.eq(0)
            yield Tick("ss")

            after_clear = yield dut.crc
            results.append(("after_clear", after_clear))

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        initial_crc = results[0][1]
        after_data = results[1][1]
        after_clear = results[2][1]

        self.assertNotEqual(after_data, initial_crc, "CRC-32 should change after data")
        self.assertEqual(after_clear, initial_crc, "CRC-32 should reset after clear")

    def test_all_partial_widths(self):
        """Verify CRC-32 for all partial-word widths (1B through 7B)."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC

        for n_bytes in range(1, 8):
            with self.subTest(n_bytes=n_bytes):
                dut = Gen2DataCRC()

                test_bytes = bytes(range(n_bytes))
                test_data = int.from_bytes(test_bytes, "little")
                expected_crc = _sw_crc32_usb3(test_bytes)

                advance_signals = {
                    1: "advance_1B",
                    2: "advance_2B",
                    3: "advance_3B",
                    4: "advance_4B",
                    5: "advance_5B",
                    6: "advance_6B",
                    7: "advance_7B",
                }
                advance_name = advance_signals[n_bytes]

                result = []

                def testbench():
                    yield dut.clear.eq(1)
                    yield Tick("ss")
                    yield dut.clear.eq(0)
                    yield Tick("ss")

                    yield dut.data_input.eq(test_data)
                    yield getattr(dut, advance_name).eq(1)
                    yield Tick("ss")
                    yield getattr(dut, advance_name).eq(0)
                    yield Tick("ss")

                    crc_val = yield dut.crc
                    result.append(crc_val)

                sim = Simulator(dut)
                sim.add_clock(1 / 156.25e6, domain="ss")
                sim.add_process(testbench)
                with sim.write_vcd("/dev/null"):
                    sim.run()

                self.assertEqual(
                    result[0], expected_crc,
                    f"CRC-32 ({n_bytes}B) mismatch: got 0x{result[0]:08X}, "
                    f"expected 0x{expected_crc:08X}",
                )


if __name__ == "__main__":
    unittest.main()
