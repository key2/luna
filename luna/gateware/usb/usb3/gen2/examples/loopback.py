#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
"""USB 3.1 Gen2 Loopback Core — PHY-agnostic top-level module.

This design implements a USB 3.1 Gen2 loopback device that exposes a
standard :class:`Gen2PIPEInterface` at its boundary.  It does **not**
instantiate any PHY IP — the user connects the PIPE ports to whatever
Gen2 PHY chip or IP core they have.

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
    │  │     Gen2PIPEInterface  (from interface/pipe.py) │  │
    │  │  pclk, tx_data[63:0], rx_data[63:0], ...       │  │
    │  └────────────────────────────────────────────────┘  │
    └──────────────────────┬───────────────────────────────┘
                           │  PIPE wires
                           ▼
              ┌────────────────────────┐
              │  External Gen2 PHY     │
              └────────────────────────┘

Top-level ports
---------------
The PIPE signals come directly from :class:`Gen2PIPEInterface`
(defined in ``luna.gateware.interface.pipe``).

Additional ports:
    rst_n                — Active-low reset for the core
    led_link_ready       — Link trained and in U0
    led_gen2_active      — Gen2 speed negotiated
    led_data_activity    — Data is being looped back
"""

from amaranth import *
from amaranth.lib.fifo import SyncFIFO

from luna.gateware.interface.pipe import Gen2PIPEInterface

from ..link.layer import Gen2LinkLayer
from ..ltssm import Gen2LTSSMController


class Gen2LoopbackTop(Elaboratable):
    """USB 3.1 Gen2 Loopback Core with :class:`Gen2PIPEInterface`.

    This is a PHY-agnostic loopback device.  The ``pipe`` attribute is a
    :class:`Gen2PIPEInterface` whose signals become the top-level PIPE
    ports in the generated Verilog.  Wire them to any USB 3.1 Gen2 PIPE
    PHY in your FPGA vendor's IDE.

    Parameters
    ----------
    fifo_depth : int
        Depth of the loopback FIFO in 72-bit entries (default 512).

    Attributes
    ----------
    pipe : Gen2PIPEInterface
        The standard Gen2 PIPE interface — connect to your external PHY.
    rst_n : Signal
        Active-low reset for the core.
    led_link_ready : Signal
        Asserted when the link is trained and in U0.
    led_gen2_active : Signal
        Asserted when Gen2 speed is negotiated.
    led_data_activity : Signal
        Asserted when data is being looped back.
    """

    def __init__(self, fifo_depth=512):
        self._fifo_depth = fifo_depth

        # ── Gen2 PIPE interface (the boundary to the external PHY) ─
        self.pipe = Gen2PIPEInterface()

        # ── Core reset ─────────────────────────────────────────────
        self.rst_n = Signal(reset=1, name="rst_n")

        # ── Status LEDs ────────────────────────────────────────────
        self.led_link_ready    = Signal(name="led_link_ready")
        self.led_gen2_active   = Signal(name="led_gen2_active")
        self.led_data_activity = Signal(name="led_data_activity")

    # ----------------------------------------------------------------
    def elaborate(self, platform):
        m = Module()

        pipe = self.pipe

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

        m.d.comb += [
            link.phy_source.payload     .eq(pipe.rx_data),
            link.phy_source.valid       .eq(pipe.rx_data_valid),
            link.phy_source.sync_head   .eq(pipe.rx_sync_head),
            link.phy_source.start_block .eq(pipe.rx_start_block),
        ]

        # ════════════════════════════════════════════════════════════
        # Link Layer → PIPE TX  (our core → external PHY)
        # ════════════════════════════════════════════════════════════

        m.d.comb += [
            pipe.tx_data        .eq(link.phy_sink.payload),
            pipe.tx_data_valid  .eq(link.phy_sink.valid),
            pipe.tx_sync_head   .eq(link.phy_sink.sync_head),
            pipe.tx_start_block .eq(link.phy_sink.start_block),
        ]

        # ════════════════════════════════════════════════════════════
        # LTSSM ↔ PIPE control / status
        # ════════════════════════════════════════════════════════════

        # LTSSM drives PIPE control outputs
        m.d.comb += [
            pipe.power_down             .eq(ltssm.power_down),
            pipe.tx_elec_idle           .eq(ltssm.tx_elec_idle),
            pipe.rx_termination         .eq(ltssm.rx_termination),
            pipe.rx_polarity            .eq(ltssm.rx_polarity),
            pipe.tx_detect_rx_loopback  .eq(ltssm.tx_detect_rx_loopback),
        ]

        # PIPE status inputs feed the LTSSM
        m.d.comb += [
            ltssm.phy_status    .eq(pipe.phy_status),
            ltssm.rx_elec_idle  .eq(pipe.rx_elec_idle),
            ltssm.rx_status     .eq(pipe.rx_status),
            ltssm.power_present .eq(pipe.power_present),
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
        """Return all top-level ports for Verilog generation.

        Includes every signal from the :class:`Gen2PIPEInterface` plus
        the core reset and status LEDs.
        """
        pipe = self.pipe
        return [
            # Core reset
            self.rst_n,

            # Gen2PIPEInterface signals (from luna.gateware.interface.pipe)
            pipe.pclk,

            # PIPE TX data (to external PHY)
            pipe.tx_data,
            pipe.tx_sync_head,
            pipe.tx_start_block,
            pipe.tx_data_valid,

            # PIPE RX data (from external PHY)
            pipe.rx_data,
            pipe.rx_sync_head,
            pipe.rx_start_block,
            pipe.rx_data_valid,

            # PIPE control (to external PHY)
            pipe.tx_detect_rx_loopback,
            pipe.tx_elec_idle,
            pipe.rx_polarity,
            pipe.rx_termination,
            pipe.power_down,
            pipe.elasticity_buf_mode,

            # PIPE status (from external PHY)
            pipe.rx_elec_idle,
            pipe.rx_status,
            pipe.phy_status,
            pipe.power_present,

            # Status LEDs
            self.led_link_ready,
            self.led_gen2_active,
            self.led_data_activity,
        ]
