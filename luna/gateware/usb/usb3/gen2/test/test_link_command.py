#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""Unit tests for Gen2 Link Command Receiver and Transmitter."""

import unittest

from amaranth import *
from amaranth.sim import *


# ---------------------------------------------------------------------------
# Software CRC-5 matching the hardware compute_usb_crc5()
# ---------------------------------------------------------------------------

def _hw_crc5(data_11bit):
    """Compute CRC-5 matching the hardware ``compute_usb_crc5()`` function.

    This replicates the exact polynomial expansion from
    :func:`luna.gateware.usb.usb3.link.crc.compute_usb_crc5`.
    """
    # Extract bits (MSB-first indexing as used in the hardware).
    def bit(i):
        return (data_11bit >> (10 - i)) & 1

    # Replicate the Cat() expression from compute_usb_crc5.
    # Cat builds LSB-first, so bit 0 of the result is the first entry.
    b0 =  (bit(10) ^ bit(9) ^ bit(8) ^ bit(5) ^ bit(4) ^ bit(2)) & 1
    b1 = ~(bit(10) ^ bit(9) ^ bit(8) ^ bit(7) ^ bit(4) ^ bit(3) ^ bit(1)) & 1
    b2 =  (bit(10) ^ bit(9) ^ bit(8) ^ bit(7) ^ bit(6) ^ bit(3) ^ bit(2) ^ bit(0)) & 1
    b3 =  (bit(10) ^ bit(7) ^ bit(6) ^ bit(4) ^ bit(1)) & 1
    b4 =  (bit(10) ^ bit(9) ^ bit(6) ^ bit(5) ^ bit(3) ^ bit(0)) & 1

    return (b4 << 4) | (b3 << 3) | (b2 << 2) | (b1 << 1) | b0


class TestGen2LinkCommandReceiver(unittest.TestCase):
    """Tests for Gen2LinkCommandReceiver."""

    def test_elaboration(self):
        """Verify the module elaborates without errors."""
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandReceiver
        dut = Gen2LinkCommandReceiver()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_valid_link_command(self):
        """Feed a valid link command block and verify extraction.

        Build a word0 with:
          - byte 0: LINK_CMD subtype (0x4B)
          - bytes 1-2: first 16-bit link command word
          - bytes 3-4: duplicate link command word
          - bytes 5-7: padding (zeros)

        The 16-bit link command word has:
          - bits [10:0]: 11-bit payload
          - bits [15:11]: 5-bit CRC-5
        """
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandReceiver
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        dut = Gen2LinkCommandReceiver()

        # Choose a test payload.
        test_payload = 0x123  # 11-bit value
        crc5 = _hw_crc5(test_payload)

        result = {}

        def testbench():
            # Build the 16-bit link command word.
            lc_word = (test_payload & 0x7FF) | ((crc5 & 0x1F) << 11)

            # Build word0: [subtype(8)][lc_word(16)][lc_word(16)][padding(24)]
            word0 = (
                Gen2BlockType.LINK_CMD
                | (lc_word << 8)
                | (lc_word << 24)
            )

            yield Tick("ss")
            yield Tick("ss")

            # Present the link command block.
            yield dut.word0.eq(word0)
            yield dut.link_cmd_strobe.eq(1)
            yield Tick("ss")
            yield dut.link_cmd_strobe.eq(0)
            yield Tick("ss")

            # Read outputs (registered, so available one cycle after strobe).
            result["new_command"] = yield dut.new_command
            result["command"] = yield dut.command
            result["crc_good"] = yield dut.crc_good

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["new_command"], 1, "new_command should be asserted")
        self.assertEqual(result["command"], test_payload, "command payload should match")
        self.assertEqual(result["crc_good"], 1, "crc_good should be asserted")

    def test_invalid_crc_rejected(self):
        """Verify that a link command with bad CRC is rejected."""
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandReceiver
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        dut = Gen2LinkCommandReceiver()

        test_payload = 0x123
        bad_crc = 0x00  # Intentionally wrong CRC

        result = {}

        def testbench():
            lc_word = (test_payload & 0x7FF) | ((bad_crc & 0x1F) << 11)
            word0 = (
                Gen2BlockType.LINK_CMD
                | (lc_word << 8)
                | (lc_word << 24)
            )

            yield Tick("ss")
            yield Tick("ss")

            yield dut.word0.eq(word0)
            yield dut.link_cmd_strobe.eq(1)
            yield Tick("ss")
            yield dut.link_cmd_strobe.eq(0)
            yield Tick("ss")

            result["new_command"] = yield dut.new_command
            result["crc_good"] = yield dut.crc_good

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["new_command"], 0, "new_command should NOT be asserted for bad CRC")

    def test_redundancy_mismatch_rejected(self):
        """Verify that mismatched duplicate link command words are rejected."""
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandReceiver
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        dut = Gen2LinkCommandReceiver()

        test_payload = 0x123
        crc5 = _hw_crc5(test_payload)
        lc_word_good = (test_payload & 0x7FF) | ((crc5 & 0x1F) << 11)
        lc_word_bad = lc_word_good ^ 0x0001  # Flip one bit in the duplicate

        result = {}

        def testbench():
            word0 = (
                Gen2BlockType.LINK_CMD
                | (lc_word_good << 8)
                | (lc_word_bad << 24)  # Mismatched duplicate
            )

            yield Tick("ss")
            yield Tick("ss")

            yield dut.word0.eq(word0)
            yield dut.link_cmd_strobe.eq(1)
            yield Tick("ss")
            yield dut.link_cmd_strobe.eq(0)
            yield Tick("ss")

            result["new_command"] = yield dut.new_command

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["new_command"], 0, "new_command should NOT be asserted for mismatched words")

    def test_multiple_payloads(self):
        """Verify CRC-5 validation for several different payloads."""
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandReceiver
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        for test_payload in [0x000, 0x7FF, 0x2AB, 0x555, 0x001]:
            with self.subTest(payload=hex(test_payload)):
                dut = Gen2LinkCommandReceiver()
                crc5 = _hw_crc5(test_payload)

                result = {}

                def testbench():
                    lc_word = (test_payload & 0x7FF) | ((crc5 & 0x1F) << 11)
                    word0 = (
                        Gen2BlockType.LINK_CMD
                        | (lc_word << 8)
                        | (lc_word << 24)
                    )

                    yield Tick("ss")
                    yield Tick("ss")

                    yield dut.word0.eq(word0)
                    yield dut.link_cmd_strobe.eq(1)
                    yield Tick("ss")
                    yield dut.link_cmd_strobe.eq(0)
                    yield Tick("ss")

                    result["new_command"] = yield dut.new_command
                    result["command"] = yield dut.command

                sim = Simulator(dut)
                sim.add_clock(1 / 156.25e6, domain="ss")
                sim.add_process(testbench)
                with sim.write_vcd("/dev/null"):
                    sim.run()

                self.assertEqual(result["new_command"], 1, f"new_command should be asserted for payload {hex(test_payload)}")
                self.assertEqual(result["command"], test_payload)


class TestGen2LinkCommandTransmitter(unittest.TestCase):
    """Tests for Gen2LinkCommandTransmitter."""

    def test_elaboration(self):
        """Verify the module elaborates without errors."""
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandTransmitter
        dut = Gen2LinkCommandTransmitter()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_link_command_format(self):
        """Verify transmitted link command block format.

        Trigger a send, assert ready on the source, and verify:
        - Word 0 has CONTROL_BLOCK sync header and start_block=1
        - Word 0 contains LINK_CMD subtype and two copies of the LC word
        - Word 1 has start_block=0
        """
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandTransmitter
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        dut = Gen2LinkCommandTransmitter()

        test_payload = 0x2AB  # 11-bit value

        result = {}

        def testbench():
            yield Tick("ss")

            # Trigger send.
            yield dut.command.eq(test_payload)
            yield dut.send.eq(1)
            yield Tick("ss")
            yield dut.send.eq(0)

            # Wait for TRANSMIT_WORD0 state.
            yield Tick("ss")

            # Assert ready to accept word 0.
            yield dut.source.ready.eq(1)
            yield Tick("ss")

            # Capture word 0 outputs.
            result["w0_valid"] = yield dut.source.valid
            result["w0_sync_head"] = yield dut.source.sync_head
            result["w0_start_block"] = yield dut.source.start_block
            result["w0_data"] = yield dut.source.data

            yield Tick("ss")

            # Capture word 1 outputs.
            result["w1_valid"] = yield dut.source.valid
            result["w1_start_block"] = yield dut.source.start_block

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
        self.assertEqual(subtype, Gen2BlockType.LINK_CMD, "Subtype should be LINK_CMD")

        # Verify the two LC words are identical.
        lc_word0 = (w0_data >> 8) & 0xFFFF
        lc_word1 = (w0_data >> 24) & 0xFFFF
        self.assertEqual(lc_word0, lc_word1, "Both LC words should be identical")

        # Verify the payload in the LC word.
        extracted_payload = lc_word0 & 0x7FF
        self.assertEqual(extracted_payload, test_payload, "Payload should match input")

        # Verify CRC-5 in the LC word.
        extracted_crc = (lc_word0 >> 11) & 0x1F
        expected_crc = _hw_crc5(test_payload)
        self.assertEqual(extracted_crc, expected_crc, "CRC-5 should match")

        # Verify word 1 format.
        self.assertEqual(result["w1_valid"], 1)
        self.assertEqual(result["w1_start_block"], 0)

        # Verify done strobe.
        self.assertEqual(result["done"], 1, "done should be asserted after transmission")


if __name__ == "__main__":
    unittest.main()
