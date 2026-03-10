#!/usr/bin/env python3
"""Generate Verilog for the Gen2 Loopback core.

The output is a single Verilog file whose top-level ports are the
standard USB 3.1 Gen2 PIPE interface signals.  It does **not** contain
any PHY — the user wires the PIPE ports to their own Gen2 PHY IP
(Gowin usb31dec, Synopsys, etc.) inside the FPGA vendor's IDE.

Usage::

    pdm run python -m luna.gateware.usb.usb3.gen2.examples.generate_verilog

Output::

    gen2_loopback_top.v   — Verilog top module with PIPE interface ports
"""

import sys
from pathlib import Path

from amaranth import *
from amaranth.back.verilog import convert

from .loopback import Gen2LoopbackTop


def main():
    top = Gen2LoopbackTop()
    ports = top.get_ports()

    output = convert(top, ports=ports, name="gen2_loopback_top")

    out_path = Path("gen2_loopback_top.v")
    out_path.write_text(output)

    print(f"Generated: {out_path.resolve()}")
    print()
    print("Top-level PIPE ports (directly to/from external Gen2 PHY):")
    print("  INPUTS  from PHY : pipe_pclk, pipe_rx_data[63:0], pipe_rx_sync_head[3:0],")
    print("                     pipe_rx_start_block, pipe_rx_data_valid,")
    print("                     pipe_rx_elec_idle, pipe_rx_status[2:0],")
    print("                     pipe_phy_status, pipe_power_present")
    print("  OUTPUTS to PHY   : pipe_tx_data[63:0], pipe_tx_sync_head[3:0],")
    print("                     pipe_tx_start_block, pipe_tx_data_valid,")
    print("                     pipe_tx_detect_rx_loopback, pipe_tx_elec_idle,")
    print("                     pipe_rx_polarity, pipe_rx_termination,")
    print("                     pipe_power_down[1:0], pipe_elasticity_buf_mode")
    print("  OTHER            : rst_n (input), led_link_ready, led_gen2_active,")
    print("                     led_data_activity (outputs)")
    print()
    print("Import this file into your FPGA IDE and wire the pipe_* ports")
    print("to your USB 3.1 Gen2 PHY IP block.")


if __name__ == "__main__":
    main()
