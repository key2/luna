#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""Integration tests for the Gen2 data path modules."""

import unittest

from amaranth import *
from amaranth.sim import *


class TestGen2ModuleElaboration(unittest.TestCase):
    """Verify that all Gen2 modules elaborate without errors.

    Elaboration tests catch import errors, signal naming conflicts,
    missing submodule wiring, and other structural issues early.
    """

    def test_gen2_header_crc_elaborates(self):
        """Gen2HeaderCRC elaborates."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2HeaderCRC
        dut = Gen2HeaderCRC()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_data_crc_elaborates(self):
        """Gen2DataCRC elaborates."""
        from luna.gateware.usb.usb3.gen2.crc import Gen2DataCRC
        dut = Gen2DataCRC()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_block_parser_elaborates(self):
        """Gen2BlockParser elaborates."""
        from luna.gateware.usb.usb3.gen2.link.block_parser import Gen2BlockParser
        dut = Gen2BlockParser()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_link_command_receiver_elaborates(self):
        """Gen2LinkCommandReceiver elaborates."""
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandReceiver
        dut = Gen2LinkCommandReceiver()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_link_command_transmitter_elaborates(self):
        """Gen2LinkCommandTransmitter elaborates."""
        from luna.gateware.usb.usb3.gen2.link.command import Gen2LinkCommandTransmitter
        dut = Gen2LinkCommandTransmitter()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_header_packet_receiver_elaborates(self):
        """Gen2HeaderPacketReceiver elaborates."""
        from luna.gateware.usb.usb3.gen2.link.header import Gen2HeaderPacketReceiver
        dut = Gen2HeaderPacketReceiver()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_header_packet_transmitter_elaborates(self):
        """Gen2HeaderPacketTransmitter elaborates."""
        from luna.gateware.usb.usb3.gen2.link.header import Gen2HeaderPacketTransmitter
        dut = Gen2HeaderPacketTransmitter()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_data_packet_receiver_elaborates(self):
        """Gen2DataPacketReceiver elaborates."""
        from luna.gateware.usb.usb3.gen2.link.data import Gen2DataPacketReceiver
        dut = Gen2DataPacketReceiver()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_data_packet_transmitter_elaborates(self):
        """Gen2DataPacketTransmitter elaborates."""
        from luna.gateware.usb.usb3.gen2.link.data import Gen2DataPacketTransmitter
        dut = Gen2DataPacketTransmitter()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_link_layer_elaborates(self):
        """Gen2LinkLayer elaborates with all submodules."""
        from luna.gateware.usb.usb3.gen2.link.layer import Gen2LinkLayer
        dut = Gen2LinkLayer()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_speed_mux_elaborates(self):
        """SpeedMux elaborates."""
        from luna.gateware.usb.usb3.gen2.speed_mux import SpeedMux
        dut = SpeedMux()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()

    def test_gen2_ltssm_controller_elaborates(self):
        """Gen2LTSSMController elaborates."""
        from luna.gateware.usb.usb3.gen2.ltssm import Gen2LTSSMController
        dut = Gen2LTSSMController()
        sim = Simulator(dut)
        with sim.write_vcd("/dev/null"):
            sim.run()


class TestGen2SpeedMux(unittest.TestCase):
    """Functional tests for SpeedMux.

    SpeedMux is purely combinational (no clock domain), so we use
    ``Settle()`` to evaluate combinational logic in the testbench.
    """

    def test_gen1_path_routes_header(self):
        """Verify that with use_gen2=0, Gen1 header signals are routed."""
        from amaranth.sim import Settle
        from luna.gateware.usb.usb3.gen2.speed_mux import SpeedMux
        dut = SpeedMux()

        result = {}

        def testbench():
            yield dut.use_gen2.eq(0)
            yield dut.gen1_header_source_valid.eq(1)
            yield dut.gen1_header_source_data.eq(0xDEADBEEF)
            yield dut.gen1_header_source_crc_good.eq(1)
            yield Settle()

            result["header_rx_valid"] = yield dut.header_rx_valid
            result["header_rx_data"] = yield dut.header_rx_data
            result["header_rx_crc_good"] = yield dut.header_rx_crc_good

        sim = Simulator(dut)
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["header_rx_valid"], 1)
        self.assertEqual(result["header_rx_data"], 0xDEADBEEF)
        self.assertEqual(result["header_rx_crc_good"], 1)

    def test_gen2_path_routes_header(self):
        """Verify that with use_gen2=1, Gen2 header signals are routed."""
        from amaranth.sim import Settle
        from luna.gateware.usb.usb3.gen2.speed_mux import SpeedMux
        dut = SpeedMux()

        result = {}

        def testbench():
            yield dut.use_gen2.eq(1)
            yield dut.gen2_header_source_valid.eq(1)
            yield dut.gen2_header_source_data.eq(0xCAFEBABE)
            yield dut.gen2_header_source_crc_good.eq(1)
            yield Settle()

            result["header_rx_valid"] = yield dut.header_rx_valid
            result["header_rx_data"] = yield dut.header_rx_data
            result["header_rx_crc_good"] = yield dut.header_rx_crc_good

        sim = Simulator(dut)
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["header_rx_valid"], 1)
        self.assertEqual(result["header_rx_data"], 0xCAFEBABE)
        self.assertEqual(result["header_rx_crc_good"], 1)

    def test_gen1_link_ready_routed(self):
        """Verify link_ready is routed from Gen1 when use_gen2=0."""
        from amaranth.sim import Settle
        from luna.gateware.usb.usb3.gen2.speed_mux import SpeedMux
        dut = SpeedMux()

        result = {}

        def testbench():
            yield dut.use_gen2.eq(0)
            yield dut.gen1_link_ready.eq(1)
            yield dut.gen2_link_ready.eq(0)
            yield Settle()

            result["link_ready"] = yield dut.link_ready

        sim = Simulator(dut)
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["link_ready"], 1)

    def test_gen2_link_ready_routed(self):
        """Verify link_ready is routed from Gen2 when use_gen2=1."""
        from amaranth.sim import Settle
        from luna.gateware.usb.usb3.gen2.speed_mux import SpeedMux
        dut = SpeedMux()

        result = {}

        def testbench():
            yield dut.use_gen2.eq(1)
            yield dut.gen1_link_ready.eq(0)
            yield dut.gen2_link_ready.eq(1)
            yield Settle()

            result["link_ready"] = yield dut.link_ready

        sim = Simulator(dut)
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["link_ready"], 1)

    def test_header_tx_routed_to_gen2(self):
        """Verify header TX signals are routed to Gen2 when use_gen2=1."""
        from amaranth.sim import Settle
        from luna.gateware.usb.usb3.gen2.speed_mux import SpeedMux
        dut = SpeedMux()

        result = {}

        def testbench():
            yield dut.use_gen2.eq(1)
            yield dut.header_tx_data.eq(0x123456)
            yield dut.header_tx_send.eq(1)
            yield Settle()

            result["gen2_header_sink_data"] = yield dut.gen2_header_sink_data
            result["gen2_header_sink_send"] = yield dut.gen2_header_sink_send
            # Gen1 should be deasserted.
            result["gen1_header_sink_send"] = yield dut.gen1_header_sink_send

        sim = Simulator(dut)
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["gen2_header_sink_data"], 0x123456)
        self.assertEqual(result["gen2_header_sink_send"], 1)
        self.assertEqual(result["gen1_header_sink_send"], 0, "Gen1 TX should be deasserted")


class TestGen2LTSSMController(unittest.TestCase):
    """Functional tests for Gen2LTSSMController."""

    def test_initial_state_inactive(self):
        """Verify the LTSSM starts in INACTIVE state with correct defaults."""
        from luna.gateware.usb.usb3.gen2.ltssm import Gen2LTSSMController
        dut = Gen2LTSSMController()

        result = {}

        def testbench():
            # Allow a few cycles for initialization.
            for _ in range(3):
                yield Tick("ss")

            result["link_ready"] = yield dut.link_ready
            result["use_gen2"] = yield dut.use_gen2
            result["tx_elec_idle"] = yield dut.tx_elec_idle

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(result["link_ready"], 0, "link_ready should be 0 in INACTIVE")
        self.assertEqual(result["use_gen2"], 0, "use_gen2 should be 0 initially")
        self.assertEqual(result["tx_elec_idle"], 1, "tx_elec_idle should be 1 in INACTIVE")

    def test_power_present_triggers_rx_detect(self):
        """Verify that asserting power_present transitions from INACTIVE to RX_DETECT."""
        from luna.gateware.usb.usb3.gen2.ltssm import Gen2LTSSMController
        dut = Gen2LTSSMController()

        result = {}

        def testbench():
            # Start in INACTIVE.
            for _ in range(3):
                yield Tick("ss")

            # Assert power_present.
            yield dut.power_present.eq(1)
            yield Tick("ss")
            yield Tick("ss")

            # In RX_DETECT, tx_detect_rx_loopback should be asserted.
            result["tx_detect_rx_loopback"] = yield dut.tx_detect_rx_loopback

        sim = Simulator(dut)
        sim.add_clock(1 / 156.25e6, domain="ss")
        sim.add_process(testbench)
        with sim.write_vcd("/dev/null"):
            sim.run()

        self.assertEqual(
            result["tx_detect_rx_loopback"], 1,
            "tx_detect_rx_loopback should be asserted in RX_DETECT",
        )


if __name__ == "__main__":
    unittest.main()
