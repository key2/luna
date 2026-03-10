#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""Unit tests for Gen2BlockParser."""

import unittest

from amaranth import *
from amaranth.sim import *


class TestGen2BlockParser(unittest.TestCase):
    """Tests for Gen2BlockParser."""

    def _create_dut(self):
        from luna.gateware.usb.usb3.gen2.link.block_parser import Gen2BlockParser
        return Gen2BlockParser()

    def test_elaboration(self):
        """Verify the module elaborates without errors."""
        dut = self._create_dut()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def _feed_block(self, dut, sync_head, word0_data, word1_data):
        """Generator: feed a 2-word block into the parser's sink.

        Yields the necessary signal assignments and clock ticks to
        present a complete 128-bit block (two 64-bit words) to the
        block parser.
        """
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType

        # Word 0: start of block.
        yield dut.sink.valid.eq(1)
        yield dut.sink.start_block.eq(1)
        yield dut.sink.sync_head.eq(sync_head)
        yield dut.sink.data.eq(word0_data)
        yield Tick("ss")

        # Word 1: continuation.
        yield dut.sink.start_block.eq(0)
        yield dut.sink.sync_head.eq(0)
        yield dut.sink.data.eq(word1_data)
        yield Tick("ss")

        # Deassert valid.
        yield dut.sink.valid.eq(0)
        yield dut.sink.data.eq(0)

    def test_data_block_detection(self):
        """Verify data blocks are correctly identified."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        result = {}

        def testbench():
            # Allow a few idle cycles.
            yield Tick("ss")
            yield Tick("ss")

            # Feed a data block (sync_head = DATA_BLOCK = 0x3).
            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.DATA_BLOCK,
                word0_data=0x1111111111111111,
                word1_data=0x2222222222222222,
            )

            # Wait for the parser to classify (outputs are registered).
            yield Tick("ss")

            result["block_valid"] = yield dut.block_valid
            result["is_data"] = yield dut.is_data
            result["is_control"] = yield dut.is_control

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["block_valid"], 1, "block_valid should be asserted")
        self.assertEqual(result["is_data"], 1, "is_data should be asserted for data block")
        self.assertEqual(result["is_control"], 0, "is_control should not be asserted for data block")

    def test_control_block_hp_start(self):
        """Verify HP_START control blocks are detected."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            # Build word0 with HP_START subtype in the low byte.
            word0 = Gen2BlockType.HP_START  # 0x33 in byte 0
            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.CONTROL_BLOCK,
                word0_data=word0,
                word1_data=0,
            )

            yield Tick("ss")

            result["block_valid"] = yield dut.block_valid
            result["is_control"] = yield dut.is_control
            result["hp_start"] = yield dut.hp_start
            result["control_subtype"] = yield dut.control_subtype

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["block_valid"], 1)
        self.assertEqual(result["is_control"], 1)
        self.assertEqual(result["hp_start"], 1, "hp_start strobe should fire")
        self.assertEqual(result["control_subtype"], Gen2BlockType.HP_START)

    def test_control_block_link_cmd(self):
        """Verify LINK_CMD control blocks are detected."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            word0 = Gen2BlockType.LINK_CMD  # 0x4B in byte 0
            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.CONTROL_BLOCK,
                word0_data=word0,
                word1_data=0,
            )

            yield Tick("ss")

            result["block_valid"] = yield dut.block_valid
            result["is_control"] = yield dut.is_control
            result["link_cmd"] = yield dut.link_cmd
            result["control_subtype"] = yield dut.control_subtype

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["block_valid"], 1)
        self.assertEqual(result["is_control"], 1)
        self.assertEqual(result["link_cmd"], 1, "link_cmd strobe should fire")
        self.assertEqual(result["control_subtype"], Gen2BlockType.LINK_CMD)

    def test_control_block_dp_start(self):
        """Verify DP_START control blocks are detected."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            word0 = Gen2BlockType.DP_START  # 0x66 in byte 0
            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.CONTROL_BLOCK,
                word0_data=word0,
                word1_data=0,
            )

            yield Tick("ss")

            result["block_valid"] = yield dut.block_valid
            result["is_control"] = yield dut.is_control
            result["dp_start"] = yield dut.dp_start

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["block_valid"], 1)
        self.assertEqual(result["is_control"], 1)
        self.assertEqual(result["dp_start"], 1, "dp_start strobe should fire")

    def test_end_good_detection(self):
        """Verify END_GOOD control blocks are detected."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            word0 = Gen2BlockType.END_GOOD  # 0x78 in byte 0
            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.CONTROL_BLOCK,
                word0_data=word0,
                word1_data=0,
            )

            yield Tick("ss")

            result["block_valid"] = yield dut.block_valid
            result["is_control"] = yield dut.is_control
            result["end_good"] = yield dut.end_good

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["block_valid"], 1)
        self.assertEqual(result["is_control"], 1)
        self.assertEqual(result["end_good"], 1, "end_good strobe should fire")

    def test_end_bad_detection(self):
        """Verify END_BAD control blocks are detected."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            word0 = Gen2BlockType.END_BAD  # 0x87 in byte 0
            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.CONTROL_BLOCK,
                word0_data=word0,
                word1_data=0,
            )

            yield Tick("ss")

            result["block_valid"] = yield dut.block_valid
            result["is_control"] = yield dut.is_control
            result["end_bad"] = yield dut.end_bad

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["block_valid"], 1)
        self.assertEqual(result["is_control"], 1)
        self.assertEqual(result["end_bad"], 1, "end_bad strobe should fire")

    def test_nop_detection(self):
        """Verify NOP control blocks are detected."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            word0 = Gen2BlockType.NOP  # 0x00 in byte 0
            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.CONTROL_BLOCK,
                word0_data=word0,
                word1_data=0,
            )

            yield Tick("ss")

            result["block_valid"] = yield dut.block_valid
            result["is_control"] = yield dut.is_control
            result["nop"] = yield dut.nop

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["block_valid"], 1)
        self.assertEqual(result["is_control"], 1)
        self.assertEqual(result["nop"], 1, "nop strobe should fire")

    def test_word_capture(self):
        """Verify that word0 and word1 are correctly captured."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        test_word0 = 0xDEADBEEFCAFEBABE
        test_word1 = 0x0123456789ABCDEF

        result = {}

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.DATA_BLOCK,
                word0_data=test_word0,
                word1_data=test_word1,
            )

            yield Tick("ss")

            result["word0"] = yield dut.word0
            result["word1"] = yield dut.word1

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["word0"], test_word0, "word0 should match input")
        self.assertEqual(result["word1"], test_word1, "word1 should match input")

    def test_strobe_clears_after_one_cycle(self):
        """Verify that block_valid and type strobes clear after one cycle."""
        from luna.gateware.usb.usb3.gen2.interfaces import Gen2BlockType
        dut = self._create_dut()

        results = []

        def testbench():
            yield Tick("ss")
            yield Tick("ss")

            yield from self._feed_block(
                dut,
                sync_head=Gen2BlockType.CONTROL_BLOCK,
                word0_data=Gen2BlockType.HP_START,
                word1_data=0,
            )

            # First cycle after block: strobes should be active.
            yield Tick("ss")
            bv1 = yield dut.block_valid
            hp1 = yield dut.hp_start
            results.append((bv1, hp1))

            # Second cycle: strobes should have cleared.
            yield Tick("ss")
            bv2 = yield dut.block_valid
            hp2 = yield dut.hp_start
            results.append((bv2, hp2))

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(results[0], (1, 1), "Strobes should be active on first cycle")
        self.assertEqual(results[1], (0, 0), "Strobes should clear on second cycle")


if __name__ == "__main__":
    unittest.main()
