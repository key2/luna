#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Amaranth wrapper for the Gowin usb31dec.v USB 3.1 Gen2 PHY. """

from amaranth import *

from .interfaces import Gen2PIPEInterface, Gen2RawSuperSpeedStream


class USB31DecPHY(Elaboratable):
    """Amaranth wrapper for the Gowin usb31dec.v USB 3.1 Gen2 PHY.

    This module instantiates the Verilog ``usb3_1_phy`` module and bridges its
    PIPE interface to LUNA's Gen2 stream types.

    The PHY handles:
    - 128b/132b encoding/decoding
    - Gen2 scrambling/descrambling
    - Block alignment
    - LFPS signaling
    - SERDES register initialization
    - Elastic buffering

    LUNA only needs to handle:
    - Block-type framing (data vs control blocks)
    - Header/data packet parsing
    - CRC computation
    - Link layer protocol

    Attributes
    ----------
    pipe : Gen2PIPEInterface
        The PIPE interface signals (directly connected to the Verilog instance).
    source : Gen2RawSuperSpeedStream
        RX stream — data from PHY to LUNA link layer.
    sink : Gen2RawSuperSpeedStream
        TX stream — data from LUNA link layer to PHY.

    SERDES signals (directly connected to FPGA SERDES primitives):
        serdes_upar_clk, serdes_upar_wren, serdes_upar_addr, serdes_upar_wrdata,
        serdes_upar_rden, serdes_upar_rddata, serdes_upar_rdvld, serdes_upar_ready,
        serdes_txdata, serdes_rxdata, serdes_pcs_tx_clk, serdes_pcs_rx_clk,
        serdes_pma_rx_lock, serdes_tx_fifo_wrusewd, serdes_rx_fifo_rdusewd,
        serdes_rxfifo_aempty, serdes_rx_vld, serdes_rxelecidle, serdes_astat,
        q0_qpll0_ok, q0_qpll1_ok, q1_qpll0_ok, q1_qpll1_ok, cpll_ok
    """

    def __init__(self):
        # PIPE interface (LUNA-facing)
        self.pipe = Gen2PIPEInterface()

        # Stream interfaces for LUNA link layer
        self.source = Gen2RawSuperSpeedStream()  # RX: PHY → LUNA
        self.sink = Gen2RawSuperSpeedStream()     # TX: LUNA → PHY

        # SERDES interface signals (directly to FPGA primitives)
        self.serdes_upar_clk        = Signal()
        self.serdes_upar_wren       = Signal()
        self.serdes_upar_addr       = Signal(24)
        self.serdes_upar_wrdata     = Signal(32)
        self.serdes_upar_rden       = Signal()
        self.serdes_upar_rddata     = Signal(32)
        self.serdes_upar_rdvld      = Signal()
        self.serdes_upar_ready      = Signal()
        self.serdes_txdata          = Signal(80)
        self.serdes_rxdata          = Signal(88)
        self.serdes_pcs_tx_clk      = Signal()
        self.serdes_pcs_rx_clk      = Signal()
        self.serdes_pma_rx_lock     = Signal()
        self.serdes_tx_fifo_wrusewd = Signal(5)
        self.serdes_rx_fifo_rdusewd = Signal(5)
        self.serdes_rxfifo_aempty   = Signal()
        self.serdes_rx_vld          = Signal()
        self.serdes_rxelecidle      = Signal()
        self.serdes_astat           = Signal(6)
        self.q0_qpll0_ok            = Signal()
        self.q0_qpll1_ok            = Signal()
        self.q1_qpll0_ok            = Signal()
        self.q1_qpll1_ok            = Signal()
        self.cpll_ok                = Signal()

        # Reset (active-low to the PHY)
        self.rst_n = Signal(reset=1)

    def elaborate(self, platform):
        m = Module()

        pipe = self.pipe

        # Instantiate the Verilog PHY
        m.submodules.phy = Instance("usb3_1_phy",
            # Reset
            i_rst_n=self.rst_n,

            # PIPE clock
            o_pclk=pipe.pclk,

            # PIPE TX data path
            i_PipeTxData=pipe.tx_data,
            i_PipeTxSyncHead=pipe.tx_sync_head,
            i_PipeTxStartBlock=pipe.tx_start_block,
            i_PipeTxDataValid=pipe.tx_data_valid,

            # PIPE RX data path
            o_PipeRxData=pipe.rx_data,
            o_PipeRxSyncHead=pipe.rx_sync_head,
            o_PipeRxStartBlock=pipe.rx_start_block,
            o_PipeRxDataValid=pipe.rx_data_valid,

            # PIPE control
            i_TxDetectRx_loopback=pipe.tx_detect_rx_loopback,
            i_TxElecIdle=pipe.tx_elec_idle,
            i_RxPolarity=pipe.rx_polarity,
            i_RxTermination=pipe.rx_termination,
            i_PowerDown=pipe.power_down,
            i_ElasticityBufferMode=pipe.elasticity_buf_mode,

            # PIPE status
            o_RxElecIdle=pipe.rx_elec_idle,
            o_RxStatus=pipe.rx_status,
            o_PhyStatus=pipe.phy_status,
            o_PowerPresent=pipe.power_present,

            # SERDES interface
            i_serdes_upar_clk_i=self.serdes_upar_clk,
            o_serdes_upar_wren_o=self.serdes_upar_wren,
            o_serdes_upar_addr_o=self.serdes_upar_addr,
            o_serdes_upar_wrdata_o=self.serdes_upar_wrdata,
            o_serdes_upar_rden_o=self.serdes_upar_rden,
            i_serdes_upar_rddata_i=self.serdes_upar_rddata,
            i_serdes_upar_rdvld_i=self.serdes_upar_rdvld,
            i_serdes_upar_ready_i=self.serdes_upar_ready,
            o_serdes_txdata_o=self.serdes_txdata,
            i_serdes_rxdata_i=self.serdes_rxdata,
            i_serdes_pcs_tx_clk_i=self.serdes_pcs_tx_clk,
            i_serdes_pcs_rx_clk_i=self.serdes_pcs_rx_clk,
            i_serdes_pma_rx_lock_i=self.serdes_pma_rx_lock,
            i_serdes_tx_fifo_wrusewd_i=self.serdes_tx_fifo_wrusewd,
            i_serdes_rx_fifo_rdusewd_i=self.serdes_rx_fifo_rdusewd,
            i_serdes_rxfifo_aempty_i=self.serdes_rxfifo_aempty,
            i_serdes_rx_vld_i=self.serdes_rx_vld,
            i_serdes_rxelecidle_i=self.serdes_rxelecidle,
            i_serdes_astat_i=self.serdes_astat,
            i_q0_qpll0_ok=self.q0_qpll0_ok,
            i_q0_qpll1_ok=self.q0_qpll1_ok,
            i_q1_qpll0_ok=self.q1_qpll0_ok,
            i_q1_qpll1_ok=self.q1_qpll1_ok,
            i_cpll_ok=self.cpll_ok,
        )

        # Bridge PIPE RX → source stream
        # The source stream carries data from the PHY to the LUNA link layer.
        # The PHY outputs data at line rate — no backpressure is supported,
        # so source.ready is ignored by the PHY.
        m.d.comb += [
            self.source.payload.eq(pipe.rx_data),
            self.source.sync_head.eq(pipe.rx_sync_head),
            self.source.start_block.eq(pipe.rx_start_block),
            self.source.valid.eq(pipe.rx_data_valid),
            # first/last are not directly available from PIPE —
            # the link layer block parser will determine packet boundaries.
        ]

        # Bridge sink stream → PIPE TX
        # The sink stream carries data from the LUNA link layer to the PHY.
        m.d.comb += [
            pipe.tx_data.eq(self.sink.payload),
            pipe.tx_sync_head.eq(self.sink.sync_head),
            pipe.tx_start_block.eq(self.sink.start_block),
            pipe.tx_data_valid.eq(self.sink.valid),
        ]

        return m
