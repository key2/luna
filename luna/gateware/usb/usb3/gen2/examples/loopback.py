#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""USB 3.1 Gen2 Loopback Core — PHY-agnostic top-level module.

This design implements a USB 3.1 Gen2 loopback device that exposes a
standard Gen2 PIPE interface at its boundary.  It does **not** instantiate
any PHY IP — the user connects the PIPE ports to whatever Gen2 PHY chip
or IP core they have (Gowin usb31dec, Synopsys, etc.).

Architecture::

    ┌──────────────────────────────────────────────────────┐
    │  gen2_loopback_top  (this module)                    │
    │                                                      │
    │  ┌──────────┐   ┌──────────────┐   ┌──────────┐     │
    │  │  LTSSM   │──▶│  Link Layer  │──▶│ Loopback │     │
    │  │Controller│   │  (block      │   │  FIFO    │     │
    │  └────┬─────┘   │   parser,    │   └──────────┘     │
    │       │         │   CRC, hdr,  │                     │
    │       │         │   data Rx/Tx)│                     │
    │       ▼         └──────┬───────┘                     │
    │  ┌─────────────────────┴──────────────────────────┐  │
    │  │          PIPE Interface Ports                   │  │
    │  │  pclk, tx_data[63:0], rx_data[63:0], ...       │  │
    │  └────────────────────────────────────────────────┘  │
    └──────────────────────┬───────────────────────────────┘
                           │  PIPE wires
                           ▼
              ┌────────────────────────┐
              │  External Gen2 PHY     │
              │  (usb31dec, etc.)      │
              └────────────────────────┘

Top-level ports
---------------
PIPE data (directly to/from external PHY):
    pipe_pclk            — PIPE clock input from PHY (~156.25 MHz)
    pipe_tx_data[63:0]   — TX data to PHY
    pipe_tx_sync_head[3:0]
    pipe_tx_start_block
    pipe_tx_data_valid
    pipe_rx_data[63:0]   — RX data from PHY
    pipe_rx_sync_head[3:0]
    pipe_rx_start_block
    pipe_rx_data_valid

PIPE control (directly to/from external PHY):
    pipe_tx_detect_rx_loopback
    pipe_tx_elec_idle
    pipe_rx_polarity
    pipe_rx_termination
    pipe_power_down[1:0]
    pipe_elasticity_buf_mode

PIPE status (from external PHY):
    pipe_rx_elec_idle
    pipe_rx_status[2:0]
    pipe_phy_status
    pipe_power_present

Core infrastructure:
    rst_n                — Active-low reset for the core

Status outputs:
    led_link_ready       — Link trained and in U0
    led_gen2_active      — Gen2 speed negotiated
    led_data_activity    — Data is being looped back
"""

from amaranth import *
from amaranth.lib.fifo import SyncFIFO

from ..link.layer import Gen2LinkLayer
from ..ltssm import Gen2LTSSMController
from ..interfaces import Gen2RawSuperSpeedStream


class Gen2LoopbackTop(Elaboratable):
    """USB 3.1 Gen2 Loopback Core with PIPE interface.

    This is a PHY-agnostic loopback device.  All PIPE signals are exposed
    as top-level ports so the generated Verilog can be wired to any
    USB 3.1 Gen2 PIPE PHY in the FPGA vendor's IDE.

    Parameters
    ----------
    fifo_depth : int
        Depth of the loopback FIFO in 72-bit entries (default 512).
    """

    def __init__(self, fifo_depth=512):
        self._fifo_depth = fifo_depth

        # ── Core reset ─────────────────────────────────────────────
        self.rst_n = Signal(reset=1, name="rst_n")

        # ── PIPE clock (input from external PHY) ──────────────────
        self.pipe_pclk = Signal(name="pipe_pclk")

        # ── PIPE TX data path (outputs to external PHY) ───────────
        self.pipe_tx_data        = Signal(64, name="pipe_tx_data")
        self.pipe_tx_sync_head   = Signal(4,  name="pipe_tx_sync_head")
        self.pipe_tx_start_block = Signal(name="pipe_tx_start_block")
        self.pipe_tx_data_valid  = Signal(name="pipe_tx_data_valid")

        # ── PIPE RX data path (inputs from external PHY) ──────────
        self.pipe_rx_data        = Signal(64, name="pipe_rx_data")
        self.pipe_rx_sync_head   = Signal(4,  name="pipe_rx_sync_head")
        self.pipe_rx_start_block = Signal(name="pipe_rx_start_block")
        self.pipe_rx_data_valid  = Signal(name="pipe_rx_data_valid")

        # ── PIPE control (outputs to external PHY) ────────────────
        self.pipe_tx_detect_rx_loopback = Signal(name="pipe_tx_detect_rx_loopback")
        self.pipe_tx_elec_idle          = Signal(reset=1, name="pipe_tx_elec_idle")
        self.pipe_rx_polarity           = Signal(name="pipe_rx_polarity")
        self.pipe_rx_termination        = Signal(name="pipe_rx_termination")
        self.pipe_power_down            = Signal(2, reset=0b11, name="pipe_power_down")
        self.pipe_elasticity_buf_mode   = Signal(name="pipe_elasticity_buf_mode")

        # ── PIPE status (inputs from external PHY) ────────────────
        self.pipe_rx_elec_idle  = Signal(name="pipe_rx_elec_idle")
        self.pipe_rx_status     = Signal(3, name="pipe_rx_status")
        self.pipe_phy_status    = Signal(name="pipe_phy_status")
        self.pipe_power_present = Signal(name="pipe_power_present")

        # ── Status LEDs ────────────────────────────────────────────
        self.led_link_ready    = Signal(name="led_link_ready")
        self.led_gen2_active   = Signal(name="led_gen2_active")
        self.led_data_activity = Signal(name="led_data_activity")

    # ----------------------------------------------------------------
    def elaborate(self, platform):
        m = Module()

        # ════════════════════════════════════════════════════════════
        # Submodules
        # ════════════════════════════════════════════════════════════

        m.submodules.link  = link  = Gen2LinkLayer()
        m.submodules.ltssm = ltssm = Gen2LTSSMController()

        # Loopback FIFO: 64-bit payload + 8-bit valid mask = 72 bits
        m.submodules.loopback_fifo = fifo = SyncFIFO(
            width=72, depth=self._fifo_depth
        )

        # ════════════════════════════════════════════════════════════
        # PIPE RX → Link Layer  (external PHY → our core)
        # ════════════════════════════════════════════════════════════
        # Convert the flat PIPE RX signals into the Gen2RawSuperSpeedStream
        # that the link layer expects.

        m.d.comb += [
            link.phy_source.payload     .eq(self.pipe_rx_data),
            link.phy_source.valid       .eq(self.pipe_rx_data_valid),
            link.phy_source.sync_head   .eq(self.pipe_rx_sync_head),
            link.phy_source.start_block .eq(self.pipe_rx_start_block),
        ]

        # ════════════════════════════════════════════════════════════
        # Link Layer → PIPE TX  (our core → external PHY)
        # ════════════════════════════════════════════════════════════

        m.d.comb += [
            self.pipe_tx_data        .eq(link.phy_sink.payload),
            self.pipe_tx_data_valid  .eq(link.phy_sink.valid),
            self.pipe_tx_sync_head   .eq(link.phy_sink.sync_head),
            self.pipe_tx_start_block .eq(link.phy_sink.start_block),
        ]

        # ════════════════════════════════════════════════════════════
        # LTSSM ↔ PIPE control / status
        # ════════════════════════════════════════════════════════════

        # LTSSM drives PIPE control outputs
        m.d.comb += [
            self.pipe_power_down             .eq(ltssm.power_down),
            self.pipe_tx_elec_idle           .eq(ltssm.tx_elec_idle),
            self.pipe_rx_termination         .eq(ltssm.rx_termination),
            self.pipe_rx_polarity            .eq(ltssm.rx_polarity),
            self.pipe_tx_detect_rx_loopback  .eq(ltssm.tx_detect_rx_loopback),
        ]

        # PIPE status inputs feed the LTSSM
        m.d.comb += [
            ltssm.phy_status    .eq(self.pipe_phy_status),
            ltssm.rx_elec_idle  .eq(self.pipe_rx_elec_idle),
            ltssm.rx_status     .eq(self.pipe_rx_status),
            ltssm.power_present .eq(self.pipe_power_present),
        ]

        # ════════════════════════════════════════════════════════════
        # LTSSM ↔ Link Layer
        # ════════════════════════════════════════════════════════════

        m.d.comb += link.link_ready.eq(ltssm.link_ready)

        # ════════════════════════════════════════════════════════════
        # Loopback: data_source → FIFO → data_sink
        # ════════════════════════════════════════════════════════════

        # RX side: link layer data_source → FIFO write port
        m.d.comb += [
            fifo.w_data .eq(Cat(link.data_source.payload,
                                link.data_source.valid)),
            fifo.w_en   .eq(link.data_source.valid.any() & fifo.w_rdy),
            link.data_source.ready .eq(fifo.w_rdy),
        ]

        # TX side: FIFO read port → link layer data_sink
        m.d.comb += [
            link.data_sink.payload .eq(fifo.r_data[0:64]),
            link.data_sink.valid   .eq(fifo.r_data[64:72]),
            link.data_sink.first   .eq(0),
            link.data_sink.last    .eq(0),
        ]

        # Start a data-packet TX when the FIFO has data and the link is up.
        m.d.comb += link.data_sink_start.eq(fifo.r_rdy & ltssm.link_ready)

        # Consume from FIFO when the link layer accepts the word.
        m.d.comb += fifo.r_en.eq(link.data_sink.ready & fifo.r_rdy)

        # ════════════════════════════════════════════════════════════
        # Status LEDs
        # ════════════════════════════════════════════════════════════

        m.d.comb += [
            self.led_link_ready    .eq(ltssm.link_ready),
            self.led_gen2_active   .eq(ltssm.use_gen2),
            self.led_data_activity .eq(link.receiving_data),
        ]

        return m

    # ----------------------------------------------------------------
    def get_ports(self):
        """Return all top-level ports for Verilog generation."""
        return [
            # Core reset
            self.rst_n,

            # PIPE clock
            self.pipe_pclk,

            # PIPE TX data (to external PHY)
            self.pipe_tx_data,
            self.pipe_tx_sync_head,
            self.pipe_tx_start_block,
            self.pipe_tx_data_valid,

            # PIPE RX data (from external PHY)
            self.pipe_rx_data,
            self.pipe_rx_sync_head,
            self.pipe_rx_start_block,
            self.pipe_rx_data_valid,

            # PIPE control (to external PHY)
            self.pipe_tx_detect_rx_loopback,
            self.pipe_tx_elec_idle,
            self.pipe_rx_polarity,
            self.pipe_rx_termination,
            self.pipe_power_down,
            self.pipe_elasticity_buf_mode,

            # PIPE status (from external PHY)
            self.pipe_rx_elec_idle,
            self.pipe_rx_status,
            self.pipe_phy_status,
            self.pipe_power_present,

            # Status LEDs
            self.led_link_ready,
            self.led_gen2_active,
            self.led_data_activity,
        ]
