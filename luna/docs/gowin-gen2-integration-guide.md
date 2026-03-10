# LUNA USB 3.1 Gen2 — Integration Guide

> **Target audience:** FPGA engineers integrating LUNA's USB 3.1 Gen2 (10 Gbps)
> core with **any** USB 3.1 Gen2 PIPE PHY (Gowin `usb31dec.v`, Synopsys, etc.).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Hardware Setup](#3-hardware-setup)
4. [Project Setup](#4-project-setup)
5. [Instantiation Guide — Step by Step](#5-instantiation-guide--step-by-step)
6. [SERDES Connection Details](#6-serdes-connection-details)
7. [Signal Reference](#7-signal-reference)
8. [Testing and Simulation](#8-testing-and-simulation)
9. [Module Reference](#9-module-reference)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Overview

### What is USB 3.1 Gen2?

USB 3.1 Gen2 doubles the SuperSpeed data rate from 5 Gbps (Gen1) to
**10 Gbps**. The key technical differences from Gen1 are:

| Feature | Gen1 (5 Gbps) | Gen2 (10 Gbps) |
|---------|---------------|-----------------|
| Line rate | 5 GT/s | 10 GT/s |
| Encoding | 8b/10b | **128b/132b** |
| Scrambling | LFSR-based | **LFSR-based (different polynomial)** |
| Internal data width | 32-bit @ 125 MHz | **64-bit @ ~156.25 MHz** |
| Block framing | K-character | **Sync header (4-bit)** |

### How LUNA's Gen2 Support Works

LUNA's Gen2 core is **PHY-agnostic** — it exposes a standard USB 3.1 Gen2
PIPE interface at its boundary and does **not** contain any PHY IP.  You
connect the PIPE ports to whatever Gen2 PHY your FPGA vendor provides
(Gowin `usb31dec`, Synopsys, etc.).

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LUNA Gen2 Core  (generated Verilog)               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Gen2 LTSSM   │  │ Gen2 Link    │  │ Application Logic         │  │
│  │ Controller   │  │ Layer        │  │ (loopback, endpoints,     │  │
│  │              │  │ • Block Parse│  │  protocol layer, etc.)    │  │
│  │              │  │ • Header Pkt │  │                           │  │
│  │              │  │ • Data Pkt   │  │                           │  │
│  │              │  │ • Link Cmds  │  │                           │  │
│  │              │  │ • CRC-16/32  │  │                           │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────┘  │
│         │                 │                                         │
│  ┌──────▼─────────────────▼──────────────────────────────────────┐  │
│  │              PIPE Interface Ports (top-level I/O)              │  │
│  │  pipe_tx_data[63:0], pipe_rx_data[63:0], pipe_tx_sync_head,   │  │
│  │  pipe_rx_sync_head, pipe_power_down, pipe_phy_status, ...     │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────────┘
                               │  PIPE wires (directly in FPGA IDE)
┌──────────────────────────────▼──────────────────────────────────────┐
│                    External Gen2 PHY IP                              │
│  (Gowin usb31dec.v, Synopsys, or any PIPE-compliant Gen2 PHY)      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ PIPE ↔ MAC   │  │ 128b/132b    │  │ SERDES I/O               │  │
│  │ Interface    │  │ Encode/Decode│  │ (10 GT/s)                │  │
│  │              │  │ + Scrambling │  │                           │  │
│  │              │  │ + Block Align│  │                           │  │
│  │              │  │ + LFPS       │  │                           │  │
│  │              │  │ + Elastic Buf│  │                           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**The external PHY handles** (not part of LUNA):
- 128b/132b encoding and decoding
- Gen2 scrambling and descrambling
- Block alignment
- LFPS signaling
- SERDES register initialization
- Elastic buffering

**LUNA's Gen2 core handles:**
- Block-type framing (data vs. control blocks)
- Header and data packet parsing/generation
- CRC-16 (headers) and CRC-32 (data) computation
- Link command processing
- Link training state machine (LTSSM)
- Speed negotiation (Gen1 ↔ Gen2)

### Loopback Example and Verilog Generation

A ready-to-use loopback example is provided that generates a single Verilog
file with PIPE interface ports:

```bash
pdm run python -m luna.gateware.usb.usb3.gen2.examples.generate_verilog
```

This produces `gen2_loopback_top.v` — import it into your FPGA IDE and wire
the `pipe_*` ports to your Gen2 PHY IP block.  No SERDES wiring needed in
the generated Verilog; that's between the PHY IP and the SERDES primitive.

---

## 2. Prerequisites

### Hardware

- **Gowin FPGA** with high-speed SERDES capable of 10 GT/s
  - Recommended: **GW5A** series (e.g., GW5A-25, GW5A-138)
  - The SERDES must support 10 Gbps line rate with 128b/132b encoding
- **USB 3.1 Gen2 Type-C or Type-A connector** with SuperSpeed+ pins
- **Reference clock source** — typically 100 MHz or 156.25 MHz differential
- **SERDES lane** — at least one TX/RX pair routed to the USB connector

### Software

| Tool | Purpose |
|------|---------|
| **Gowin EDA** (≥ V1.9.9) | FPGA synthesis, place & route, bitstream generation |
| **Python** ≥ 3.9 | Runtime for Amaranth HDL and LUNA |
| **PDM** | Dependency management (replaces pip) |
| **Amaranth HDL** | Hardware description language |
| **LUNA** | USB gateware framework |

### IP Core

- **`usb31dec.v`** — Gowin's USB 3.1 Gen2 PHY IP core
  - Located at [`usb31dec.v`](../usb31dec.v) in this repository
  - Requires companion include files:
    - `static_macro_define.v`
    - `usb3_1_phy_name.v`
    - `usb3_1_phy_top_define.vh`

---

## 3. Hardware Setup

### FPGA Requirements

| Resource | Requirement |
|----------|-------------|
| SERDES lanes | ≥ 1 TX + 1 RX (10 GT/s capable) |
| Reference clock | 100 MHz or 156.25 MHz differential |
| Fabric clock | ~156.25 MHz (derived from SERDES `pclk`) |
| Block RAM | ~20 KB (elastic buffers, FIFOs) |
| LUTs | ~5,000–8,000 (PHY + link layer) |

### USB 3.1 Connector Pinout

For a USB Type-C connector with SuperSpeed+ support:

| Pin | Signal | Direction | Description |
|-----|--------|-----------|-------------|
| A2/B2 | SSTX+ | FPGA → Connector | SuperSpeed TX positive |
| A3/B3 | SSTX− | FPGA → Connector | SuperSpeed TX negative |
| A10/B10 | SSRX+ | Connector → FPGA | SuperSpeed RX positive |
| A11/B11 | SSRX− | Connector → FPGA | SuperSpeed RX negative |
| — | REFCLK+ | — | Reference clock positive |
| — | REFCLK− | — | Reference clock negative |

### Reference Clock Requirements

- **Frequency:** 100 MHz (typical) or 156.25 MHz
- **Type:** Differential LVDS or LVPECL
- **Jitter:** < 1 ps RMS (for reliable 10 GT/s operation)
- **Source:** On-board oscillator or recovered from SERDES PLL

### SERDES Configuration

The Gowin SERDES must be configured for:

- **Line rate:** 10 Gbps
- **Data width:** 80-bit TX / 88-bit RX (internal SERDES interface)
- **PLL reference:** Matched to your reference clock frequency
- **TX pre-emphasis:** Per USB 3.1 Gen2 electrical spec
- **RX equalization:** Adaptive or fixed per channel characteristics

---

## 4. Project Setup

### Directory Structure

```
my-usb31-project/
├── pyproject.toml          # PDM project configuration
├── pdm.lock                # PDM lock file
├── usb31dec.v              # Gowin PHY IP core
├── static_macro_define.v   # PHY include file
├── usb3_1_phy_name.v       # PHY include file
├── usb3_1_phy_top_define.vh # PHY include file
├── platform/
│   └── gowin_gw5a.py       # Gowin platform definition
├── gateware/
│   └── top.py              # Top-level design
└── tests/
    └── test_top.py          # Simulation tests
```

### PDM Configuration

Initialize a new project with PDM:

```bash
pdm init
```

Add LUNA and Amaranth as dependencies in `pyproject.toml`:

```toml
[project]
name = "my-usb31-project"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = [
    "amaranth>=0.5",
    "amaranth-boards",
    "luna-usb",
]

[tool.pdm.scripts]
test = "python -m unittest discover -s tests -v"
build = "python gateware/top.py"
```

Install dependencies:

```bash
pdm install
```

---

## 5. Instantiation Guide — Step by Step

### Step A: Creating a Gowin Platform Class

Create a platform class that provides the SERDES resources for the Gowin GW5A:

```python
# platform/gowin_gw5a.py

from amaranth import *
from amaranth.build import *
from amaranth_boards.resources import *

from luna.gateware.platform.core import LUNAPlatform


class GowinGW5AGen2Platform(LUNAPlatform):
    """Gowin GW5A platform with USB 3.1 Gen2 SERDES resources."""

    name = "Gowin GW5A Gen2"

    # Default clock frequency (fabric clock from SERDES pclk)
    default_clk_frequency = 156.25e6

    # SERDES resources for USB 3.1 Gen2
    resources = [
        # Reference clock input (100 MHz differential)
        Resource("refclk", 0,
            Subsignal("p", Pins("XX", dir="i")),   # Replace XX with actual pin
            Subsignal("n", Pins("XX", dir="i")),   # Replace XX with actual pin
        ),

        # USB 3.1 SERDES lane
        Resource("usb31_serdes", 0,
            Subsignal("tx_p", Pins("XX", dir="o")),  # Replace with actual pin
            Subsignal("tx_n", Pins("XX", dir="o")),  # Replace with actual pin
            Subsignal("rx_p", Pins("XX", dir="i")),  # Replace with actual pin
            Subsignal("rx_n", Pins("XX", dir="i")),  # Replace with actual pin
        ),

        # Status LEDs (optional)
        Resource("led", 0, Pins("XX", dir="o")),
        Resource("led", 1, Pins("XX", dir="o")),
    ]

    connectors = []

    def toolchain_generate(self, products, name, **kwargs):
        """Override to add Gowin-specific synthesis settings."""
        # Add the usb31dec.v Verilog file to the build
        products.add_file("usb31dec.v", open("usb31dec.v", "rb").read())
        products.add_file("static_macro_define.v",
                          open("static_macro_define.v", "rb").read())
        products.add_file("usb3_1_phy_name.v",
                          open("usb3_1_phy_name.v", "rb").read())
        products.add_file("usb3_1_phy_top_define.vh",
                          open("usb3_1_phy_top_define.vh", "rb").read())
```

### Step B: Instantiating the Gen2 PHY

The [`USB31DecPHY`](../gateware/usb/usb3/gen2/phy.py) class wraps the Gowin
`usb3_1_phy` Verilog module and bridges its PIPE interface to LUNA's Gen2
stream types:

```python
from luna.gateware.usb.usb3.gen2 import USB31DecPHY

# Inside your Elaboratable.elaborate():
m.submodules.phy = phy = USB31DecPHY()
```

This creates:
- [`phy.pipe`](../gateware/usb/usb3/gen2/interfaces.py:37) — the
  `Gen2PIPEInterface` signal bundle (64-bit PIPE signals)
- [`phy.source`](../gateware/usb/usb3/gen2/phy.py:56) — RX stream
  (`Gen2RawSuperSpeedStream`, PHY → LUNA)
- [`phy.sink`](../gateware/usb/usb3/gen2/phy.py:57) — TX stream
  (`Gen2RawSuperSpeedStream`, LUNA → PHY)
- SERDES interface signals (directly connected to FPGA primitives)

### Step C: Connecting SERDES Signals to FPGA Primitives

The `USB31DecPHY` exposes raw SERDES signals that must be connected to the
Gowin SERDES hard macro. The exact primitive name depends on your GW5A variant:

```python
# Connect SERDES signals from USB31DecPHY to Gowin SERDES primitive.
# This is a simplified example — adapt to your specific GW5A SERDES primitive.

m.submodules.serdes = Instance("GW5A_SERDES_10G",
    # Reference clock
    i_REFCLK       = refclk,

    # TX data path (from PHY to SERDES)
    i_TXDATA       = phy.serdes_txdata,          # 80-bit TX data
    o_PCS_TX_CLK   = phy.serdes_pcs_tx_clk,      # TX PCS clock

    # RX data path (from SERDES to PHY)
    o_RXDATA       = phy.serdes_rxdata,           # 88-bit RX data
    o_PCS_RX_CLK   = phy.serdes_pcs_rx_clk,      # RX PCS clock
    o_PMA_RX_LOCK  = phy.serdes_pma_rx_lock,      # PMA lock indicator

    # FIFO status
    o_TX_FIFO_WRUSEWD = phy.serdes_tx_fifo_wrusewd,  # 5-bit TX FIFO usage
    o_RX_FIFO_RDUSEWD = phy.serdes_rx_fifo_rdusewd,  # 5-bit RX FIFO usage
    o_RXFIFO_AEMPTY   = phy.serdes_rxfifo_aempty,     # RX FIFO almost empty
    o_RX_VLD          = phy.serdes_rx_vld,             # RX data valid
    o_RXELECIDLE      = phy.serdes_rxelecidle,         # RX electrical idle
    o_ASTAT           = phy.serdes_astat,              # 6-bit alignment status

    # UPAR (User Parameter Access Register) interface
    i_UPAR_CLK     = phy.serdes_upar_clk,
    o_UPAR_WREN    = phy.serdes_upar_wren,
    o_UPAR_ADDR    = phy.serdes_upar_addr,        # 24-bit address
    o_UPAR_WRDATA  = phy.serdes_upar_wrdata,      # 32-bit write data
    o_UPAR_RDEN    = phy.serdes_upar_rden,
    i_UPAR_RDDATA  = phy.serdes_upar_rddata,      # 32-bit read data
    i_UPAR_RDVLD   = phy.serdes_upar_rdvld,
    i_UPAR_READY   = phy.serdes_upar_ready,

    # PLL status
    o_Q0_QPLL0_OK = phy.q0_qpll0_ok,
    o_Q0_QPLL1_OK = phy.q0_qpll1_ok,
    o_Q1_QPLL0_OK = phy.q1_qpll0_ok,
    o_Q1_QPLL1_OK = phy.q1_qpll1_ok,
    o_CPLL_OK      = phy.cpll_ok,
)
```

### Step D: Instantiating the Gen2 Link Layer

The [`Gen2LinkLayer`](../gateware/usb/usb3/gen2/link/layer.py:43) wires
together the block parser, header/data/link-command receivers and transmitters:

```python
from luna.gateware.usb.usb3.gen2 import Gen2LinkLayer

m.submodules.link = link = Gen2LinkLayer(ss_clock_frequency=156.25e6)

# Connect PHY streams to link layer
m.d.comb += [
    link.phy_source.stream_eq(phy.source),   # RX: PHY → Link
    phy.sink.stream_eq(link.phy_sink),        # TX: Link → PHY
]
```

The link layer provides these interfaces to the protocol layer:

- **Header RX:** `link.header_source_valid`, `link.header_source_data` (96-bit),
  `link.header_source_crc_good`
- **Data RX:** `link.data_source` (64-bit `Gen2SuperSpeedStreamInterface`),
  `link.data_packet_good`, `link.data_packet_bad`
- **Link Commands RX:** `link.link_command_valid`, `link.link_command` (11-bit)
- **Header TX:** `link.header_sink_data` (96-bit), `link.header_sink_send`,
  `link.header_sink_busy`, `link.header_sink_done`
- **Data TX:** `link.data_sink` (64-bit `Gen2SuperSpeedStreamInterface`),
  `link.data_sink_start`, `link.data_sink_busy`, `link.data_sink_done`
- **Link Commands TX:** `link.link_command_to_send` (11-bit),
  `link.link_command_send`, `link.link_command_busy`

### Step E: Connecting the LTSSM

The [`Gen2LTSSMController`](../gateware/usb/usb3/gen2/ltssm.py:22) manages
link training and speed negotiation:

```python
from luna.gateware.usb.usb3.gen2 import Gen2LTSSMController

m.submodules.ltssm = ltssm = Gen2LTSSMController(ss_clock_frequency=156.25e6)

# Connect LTSSM outputs to PHY control signals
m.d.comb += [
    phy.pipe.power_down             .eq(ltssm.power_down),
    phy.pipe.tx_elec_idle           .eq(ltssm.tx_elec_idle),
    phy.pipe.rx_termination         .eq(ltssm.rx_termination),
    phy.pipe.rx_polarity            .eq(ltssm.rx_polarity),
    phy.pipe.tx_detect_rx_loopback  .eq(ltssm.tx_detect_rx_loopback),
]

# Connect PHY status signals to LTSSM inputs
m.d.comb += [
    ltssm.phy_status     .eq(phy.pipe.phy_status),
    ltssm.rx_elec_idle   .eq(phy.pipe.rx_elec_idle),
    ltssm.rx_status      .eq(phy.pipe.rx_status),
    ltssm.power_present  .eq(phy.pipe.power_present),
]
```

The LTSSM goes through these states:

```
INACTIVE → RX_DETECT → GEN1_WAIT → GEN1_ACTIVE
                                        │
                                        ▼ (speed change requested)
                              SPEED_CHANGE_INIT
                                        │
                                        ▼
                            SPEED_CHANGE_RECOVERY
                                        │
                                        ▼
                            SPEED_CHANGE_TRAINING
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                        GEN2_ACTIVE          GEN1_ACTIVE
                              │              (fallback)
                              ▼
                        GEN2_RECOVERY → GEN2_RECOVERY_CONFIG
                                              │
                                              ▼
                                      GEN2_RECOVERY_IDLE
                                              │
                                              ▼
                                        GEN2_ACTIVE
```

### Step F: Using the Speed Mux for Gen1/Gen2 Coexistence

The [`SpeedMux`](../gateware/usb/usb3/gen2/speed_mux.py:31) selects between
Gen1 and Gen2 link layer paths based on the negotiated speed:

```python
from luna.gateware.usb.usb3.gen2 import SpeedMux

m.submodules.speed_mux = mux = SpeedMux()

# Control: select Gen2 when LTSSM says so
m.d.comb += mux.use_gen2.eq(ltssm.use_gen2)

# Connect Gen2 link layer to the mux
m.d.comb += [
    # Gen2 status
    mux.gen2_link_ready             .eq(link.link_ready),

    # Gen2 header RX
    mux.gen2_header_source_valid    .eq(link.header_source_valid),
    mux.gen2_header_source_data     .eq(link.header_source_data),
    mux.gen2_header_source_crc_good .eq(link.header_source_crc_good),

    # Gen2 data RX
    mux.gen2_data_source.payload    .eq(link.data_source.payload),
    mux.gen2_data_source.valid      .eq(link.data_source.valid),
    mux.gen2_data_source.first      .eq(link.data_source.first),
    mux.gen2_data_source.last       .eq(link.data_source.last),
    mux.gen2_data_packet_good       .eq(link.data_packet_good),
    mux.gen2_data_packet_bad        .eq(link.data_packet_bad),

    # Gen2 header TX
    link.header_sink_data           .eq(mux.gen2_header_sink_data),
    link.header_sink_send           .eq(mux.gen2_header_sink_send),
    mux.gen2_header_sink_busy       .eq(link.header_sink_busy),

    # Gen2 data TX
    link.data_sink.payload          .eq(mux.gen2_data_sink.payload),
    link.data_sink.valid            .eq(mux.gen2_data_sink.valid),
    link.data_sink.first            .eq(mux.gen2_data_sink.first),
    link.data_sink.last             .eq(mux.gen2_data_sink.last),

    # Gen2 link commands RX
    mux.gen2_link_command_valid     .eq(link.link_command_valid),
    mux.gen2_link_command           .eq(link.link_command),

    # Gen2 link commands TX
    link.link_command_to_send       .eq(mux.gen2_link_command_to_send),
    link.link_command_send          .eq(mux.gen2_link_command_send),
    mux.gen2_link_command_busy      .eq(link.link_command_busy),
]

# The mux exposes unified interfaces to the protocol layer:
#   mux.link_ready           — active link layer is ready
#   mux.header_rx_valid      — header packet available
#   mux.header_rx_data       — 96-bit header payload
#   mux.header_rx_crc_good   — header CRC OK
#   mux.header_tx_data       — header to transmit (from protocol layer)
#   mux.header_tx_send       — trigger header TX
#   mux.header_tx_busy       — header TX busy
#   mux.gen1_data_rx         — Gen1 32-bit data stream (active when use_gen2=0)
#   mux.gen2_data_rx         — Gen2 64-bit data stream (active when use_gen2=1)
#   mux.link_command_rx      — received link command (11-bit)
#   mux.link_command_tx      — link command to send (from protocol layer)
```

### Step G: Complete Top-Level Design

Here is a complete top-level design that ties everything together:

```python
# gateware/top.py

from amaranth import *

from luna.gateware.usb.usb3.gen2 import (
    USB31DecPHY,
    Gen2LinkLayer,
    Gen2LTSSMController,
    SpeedMux,
)


class USB31Gen2Device(Elaboratable):
    """Complete USB 3.1 Gen2 device top-level.

    This module instantiates the Gowin Gen2 PHY, link layer, LTSSM,
    and speed mux, providing a ready-to-use Gen2 USB device core.
    """

    def __init__(self, ss_clock_frequency=156.25e6):
        self._ss_clock_frequency = ss_clock_frequency

        # Status outputs
        self.link_ready = Signal()
        self.use_gen2   = Signal()
        self.in_reset   = Signal()

    def elaborate(self, platform):
        m = Module()

        # ──────────────────────────────────────────────────────────
        # 1. Instantiate the Gowin Gen2 PHY
        # ──────────────────────────────────────────────────────────
        m.submodules.phy = phy = USB31DecPHY()

        # Connect SERDES signals to platform resources.
        # (Platform-specific — see Step C above for details.)
        #
        # In a real design, you would connect phy.serdes_* signals
        # to the Gowin SERDES primitive here. For example:
        #
        #   serdes = platform.request("usb31_serdes", 0)
        #   m.submodules.serdes_inst = Instance("GW5A_SERDES_10G",
        #       i_TXDATA      = phy.serdes_txdata,
        #       o_RXDATA      = phy.serdes_rxdata,
        #       o_PCS_TX_CLK  = phy.serdes_pcs_tx_clk,
        #       o_PCS_RX_CLK  = phy.serdes_pcs_rx_clk,
        #       ...
        #   )

        # ──────────────────────────────────────────────────────────
        # 2. Create the "ss" clock domain from the PHY's pclk
        # ──────────────────────────────────────────────────────────
        m.domains += ClockDomain("ss")
        m.d.comb += [
            ClockSignal("ss").eq(phy.pipe.pclk),
        ]

        # ──────────────────────────────────────────────────────────
        # 3. Instantiate the Gen2 Link Layer
        # ──────────────────────────────────────────────────────────
        m.submodules.link = link = Gen2LinkLayer(
            ss_clock_frequency=self._ss_clock_frequency
        )

        # Connect PHY ↔ Link Layer streams
        m.d.comb += [
            link.phy_source.stream_eq(phy.source),  # RX: PHY → Link
            phy.sink.stream_eq(link.phy_sink),       # TX: Link → PHY
        ]

        # ──────────────────────────────────────────────────────────
        # 4. Instantiate the Gen2 LTSSM Controller
        # ──────────────────────────────────────────────────────────
        m.submodules.ltssm = ltssm = Gen2LTSSMController(
            ss_clock_frequency=self._ss_clock_frequency
        )

        # Connect LTSSM ↔ PHY control/status
        m.d.comb += [
            # LTSSM → PHY control
            phy.pipe.power_down             .eq(ltssm.power_down),
            phy.pipe.tx_elec_idle           .eq(ltssm.tx_elec_idle),
            phy.pipe.rx_termination         .eq(ltssm.rx_termination),
            phy.pipe.rx_polarity            .eq(ltssm.rx_polarity),
            phy.pipe.tx_detect_rx_loopback  .eq(ltssm.tx_detect_rx_loopback),

            # PHY → LTSSM status
            ltssm.phy_status                .eq(phy.pipe.phy_status),
            ltssm.rx_elec_idle              .eq(phy.pipe.rx_elec_idle),
            ltssm.rx_status                 .eq(phy.pipe.rx_status),
            ltssm.power_present             .eq(phy.pipe.power_present),
        ]

        # ──────────────────────────────────────────────────────────
        # 5. Instantiate the Speed Mux
        # ──────────────────────────────────────────────────────────
        m.submodules.speed_mux = mux = SpeedMux()

        # Speed selection from LTSSM
        m.d.comb += mux.use_gen2.eq(ltssm.use_gen2)

        # Connect Gen2 link layer ↔ Speed Mux
        m.d.comb += [
            # Gen2 status
            mux.gen2_link_ready             .eq(link.link_ready),

            # Gen2 header RX
            mux.gen2_header_source_valid    .eq(link.header_source_valid),
            mux.gen2_header_source_data     .eq(link.header_source_data),
            mux.gen2_header_source_crc_good .eq(link.header_source_crc_good),

            # Gen2 data RX
            mux.gen2_data_source.payload    .eq(link.data_source.payload),
            mux.gen2_data_source.valid      .eq(link.data_source.valid),
            mux.gen2_data_source.first      .eq(link.data_source.first),
            mux.gen2_data_source.last       .eq(link.data_source.last),
            mux.gen2_data_packet_good       .eq(link.data_packet_good),
            mux.gen2_data_packet_bad        .eq(link.data_packet_bad),

            # Gen2 header TX
            link.header_sink_data           .eq(mux.gen2_header_sink_data),
            link.header_sink_send           .eq(mux.gen2_header_sink_send),
            mux.gen2_header_sink_busy       .eq(link.header_sink_busy),

            # Gen2 data TX
            link.data_sink.payload          .eq(mux.gen2_data_sink.payload),
            link.data_sink.valid            .eq(mux.gen2_data_sink.valid),
            link.data_sink.first            .eq(mux.gen2_data_sink.first),
            link.data_sink.last             .eq(mux.gen2_data_sink.last),

            # Gen2 link commands RX
            mux.gen2_link_command_valid     .eq(link.link_command_valid),
            mux.gen2_link_command           .eq(link.link_command),

            # Gen2 link commands TX
            link.link_command_to_send       .eq(mux.gen2_link_command_to_send),
            link.link_command_send          .eq(mux.gen2_link_command_send),
            mux.gen2_link_command_busy      .eq(link.link_command_busy),
        ]

        # ──────────────────────────────────────────────────────────
        # 6. Export status signals
        # ──────────────────────────────────────────────────────────
        m.d.comb += [
            self.link_ready .eq(mux.link_ready),
            self.use_gen2   .eq(ltssm.use_gen2),
            self.in_reset   .eq(ltssm.in_reset),
        ]

        # ──────────────────────────────────────────────────────────
        # 7. Connect protocol layer to the speed mux
        # ──────────────────────────────────────────────────────────
        # The protocol layer connects to the unified mux outputs:
        #
        #   mux.header_rx_valid / mux.header_rx_data / mux.header_rx_crc_good
        #   mux.header_tx_data  / mux.header_tx_send / mux.header_tx_busy
        #   mux.gen2_data_rx    (64-bit, active when use_gen2=1)
        #   mux.gen1_data_rx    (32-bit, active when use_gen2=0)
        #   mux.link_command_rx / mux.link_command_tx
        #
        # Connect these to your protocol layer as needed.

        return m
```

---

## 6. SERDES Connection Details

### Clock Domain Setup

The Gen2 PHY outputs a `pclk` signal at ~156.25 MHz. This clock drives the
`ss` (SuperSpeed) clock domain used by all Gen2 link layer logic:

```python
# Create the "ss" clock domain from the PHY's pclk output
m.domains += ClockDomain("ss")
m.d.comb += ClockSignal("ss").eq(phy.pipe.pclk)
```

All Gen2 modules ([`Gen2LinkLayer`](../gateware/usb/usb3/gen2/link/layer.py),
[`Gen2LTSSMController`](../gateware/usb/usb3/gen2/ltssm.py),
[`Gen2HeaderCRC`](../gateware/usb/usb3/gen2/crc.py:126),
[`Gen2DataCRC`](../gateware/usb/usb3/gen2/crc.py:202)) operate in the `ss`
domain.

### SERDES Signal Mapping

The [`USB31DecPHY`](../gateware/usb/usb3/gen2/phy.py:13) exposes these SERDES
signals that must be connected to the Gowin SERDES hard macro:

| USB31DecPHY Signal | Width | Dir | SERDES Connection |
|---|---|---|---|
| `serdes_upar_clk` | 1 | in | UPAR clock (fabric clock ÷ 8) |
| `serdes_upar_wren` | 1 | out | UPAR write enable |
| `serdes_upar_addr` | 24 | out | UPAR address bus |
| `serdes_upar_wrdata` | 32 | out | UPAR write data |
| `serdes_upar_rden` | 1 | out | UPAR read enable |
| `serdes_upar_rddata` | 32 | in | UPAR read data |
| `serdes_upar_rdvld` | 1 | in | UPAR read data valid |
| `serdes_upar_ready` | 1 | in | UPAR ready |
| `serdes_txdata` | 80 | out | TX data to SERDES |
| `serdes_rxdata` | 88 | in | RX data from SERDES |
| `serdes_pcs_tx_clk` | 1 | in | PCS TX clock |
| `serdes_pcs_rx_clk` | 1 | in | PCS RX clock |
| `serdes_pma_rx_lock` | 1 | in | PMA RX lock indicator |
| `serdes_tx_fifo_wrusewd` | 5 | in | TX FIFO write usage |
| `serdes_rx_fifo_rdusewd` | 5 | in | RX FIFO read usage |
| `serdes_rxfifo_aempty` | 1 | in | RX FIFO almost empty |
| `serdes_rx_vld` | 1 | in | RX data valid |
| `serdes_rxelecidle` | 1 | in | RX electrical idle |
| `serdes_astat` | 6 | in | Alignment status |
| `q0_qpll0_ok` | 1 | in | Quad 0 QPLL0 lock |
| `q0_qpll1_ok` | 1 | in | Quad 0 QPLL1 lock |
| `q1_qpll0_ok` | 1 | in | Quad 1 QPLL0 lock |
| `q1_qpll1_ok` | 1 | in | Quad 1 QPLL1 lock |
| `cpll_ok` | 1 | in | Channel PLL lock |

### Reset Sequencing

The PHY requires a specific reset sequence:

1. **Assert reset** — hold `phy.rst_n` low for at least 10 µs after power-up
2. **Wait for PLL lock** — monitor `phy.cpll_ok` and `phy.q0_qpll0_ok`
3. **Release reset** — deassert `phy.rst_n` (drive high)
4. **Wait for PHY ready** — the PHY will assert `phy.pipe.phy_status` when
   initialization is complete

```python
# Example reset sequencing (simplified)
reset_counter = Signal(range(int(156.25e6 * 20e-6)))  # 20 µs counter

with m.FSM(domain="sync"):
    with m.State("RESET"):
        m.d.comb += phy.rst_n.eq(0)
        m.d.sync += reset_counter.eq(reset_counter + 1)
        with m.If(reset_counter == int(156.25e6 * 10e-6)):
            m.next = "WAIT_PLL"

    with m.State("WAIT_PLL"):
        m.d.comb += phy.rst_n.eq(0)
        with m.If(phy.cpll_ok & phy.q0_qpll0_ok):
            m.next = "RELEASE"

    with m.State("RELEASE"):
        m.d.comb += phy.rst_n.eq(1)
        # PHY is now initializing; LTSSM will handle the rest
```

---

## 7. Signal Reference

### Gen2PIPEInterface Signals

Source: [`gateware/usb/usb3/gen2/interfaces.py`](../gateware/usb/usb3/gen2/interfaces.py:37)

| Signal | Width | Direction | Description |
|--------|-------|-----------|-------------|
| `pclk` | 1 | PHY → MAC | PIPE clock (~156.25 MHz) |
| `tx_data` | 64 | MAC → PHY | Transmit data bus |
| `tx_sync_head` | 4 | MAC → PHY | TX sync header (DATA=0x3, CONTROL=0xC) |
| `tx_start_block` | 1 | MAC → PHY | Start of new TX block |
| `tx_data_valid` | 1 | MAC → PHY | TX data valid |
| `rx_data` | 64 | PHY → MAC | Receive data bus |
| `rx_sync_head` | 4 | PHY → MAC | RX sync header |
| `rx_start_block` | 1 | PHY → MAC | Start of new RX block |
| `rx_data_valid` | 1 | PHY → MAC | RX data valid |
| `tx_detect_rx_loopback` | 1 | MAC → PHY | Receiver detection / loopback |
| `tx_elec_idle` | 1 | MAC → PHY | TX electrical idle (reset=1) |
| `rx_polarity` | 1 | MAC → PHY | RX polarity inversion |
| `rx_termination` | 1 | MAC → PHY | RX termination enable |
| `power_down` | 2 | MAC → PHY | Power state (P0=00, P1=01, P2=10, P3=11) |
| `elasticity_buf_mode` | 1 | MAC → PHY | Elastic buffer mode |
| `rx_elec_idle` | 1 | PHY → MAC | RX electrical idle detected |
| `rx_status` | 3 | PHY → MAC | RX status indication |
| `phy_status` | 1 | PHY → MAC | PHY operation completion |
| `power_present` | 1 | PHY → MAC | VBUS voltage present |

### Gen2BlockType Constants

Source: [`gateware/usb/usb3/gen2/interfaces.py`](../gateware/usb/usb3/gen2/interfaces.py:13)

| Constant | Value | Description |
|----------|-------|-------------|
| `DATA_BLOCK` | `0x3` | Data block sync header |
| `CONTROL_BLOCK` | `0xC` | Control block sync header |
| `HP_START` | `0x33` | Header Packet Start (control subtype) |
| `DP_START` | `0x66` | Data Packet Start (control subtype) |
| `END_GOOD` | `0x78` | End Good — CRC valid (control subtype) |
| `END_BAD` | `0x87` | End Bad — CRC invalid (control subtype) |
| `LINK_CMD` | `0x4B` | Link Command (control subtype) |
| `NOP` | `0x00` | No Operation (control subtype) |

### Gen2RawSuperSpeedStream Fields

Source: [`gateware/usb/usb3/gen2/interfaces.py`](../gateware/usb/usb3/gen2/interfaces.py:140)

| Field | Width | Description |
|-------|-------|-------------|
| `payload` / `data` | 64 | 64-bit data word |
| `sync_head` | 4 | 128b/132b sync header |
| `start_block` | 1 | Start of new block marker |
| `valid` | 1 | Stream valid |
| `ready` | 1 | Stream ready (backpressure) |
| `first` | 1 | First word of packet |
| `last` | 1 | Last word of packet |

### Gen2SuperSpeedStreamInterface Fields

Source: [`gateware/usb/usb3/gen2/interfaces.py`](../gateware/usb/usb3/gen2/interfaces.py:180)

| Field | Width | Description |
|-------|-------|-------------|
| `payload` | 64 | 64-bit data payload |
| `valid` | 8 | Per-byte valid indicators |
| `ready` | 1 | Stream ready (backpressure) |
| `first` | 1 | First word of packet |
| `last` | 1 | Last word of packet |

---

## 8. Testing and Simulation

### Running Unit Tests

The Gen2 modules include comprehensive unit tests. Run them with PDM:

```bash
pdm run python -m unittest discover -s luna/gateware/usb/usb3/gen2/test -v
```

Individual test modules:

```bash
# CRC-16 and CRC-32 engine tests
pdm run python -m unittest luna.gateware.usb.usb3.gen2.test.test_crc -v

# Block parser tests
pdm run python -m unittest luna.gateware.usb.usb3.gen2.test.test_block_parser -v

# Header packet receiver/transmitter tests
pdm run python -m unittest luna.gateware.usb.usb3.gen2.test.test_header -v

# Link command receiver/transmitter tests
pdm run python -m unittest luna.gateware.usb.usb3.gen2.test.test_link_command -v

# Integration tests (full link layer)
pdm run python -m unittest luna.gateware.usb.usb3.gen2.test.test_integration -v
```

### Simulating the Gen2 Link Layer

Use Amaranth's built-in simulator to test the Gen2 link layer:

```python
from amaranth import *
from amaranth.sim import Simulator

from luna.gateware.usb.usb3.gen2 import Gen2LinkLayer, Gen2BlockType


def test_link_layer_nop():
    """Verify the link layer outputs NOP blocks when idle."""

    dut = Gen2LinkLayer()

    sim = Simulator(dut)
    sim.add_clock(1 / 156.25e6, domain="ss")

    def process():
        # Let the link layer run for a few cycles
        for _ in range(20):
            yield Tick("ss")

        # Check that the PHY sink is outputting NOP blocks
        valid = yield dut.phy_sink.valid
        assert valid == 1, "PHY sink should be valid (NOP output)"

        sync_head = yield dut.phy_sink.sync_head
        assert sync_head == Gen2BlockType.CONTROL_BLOCK, \
            f"Expected CONTROL_BLOCK sync header, got {sync_head:#x}"

    sim.add_process(process)

    with sim.write_vcd("link_layer_nop.vcd"):
        sim.run()
```

### VCD Output for Debugging

Generate VCD waveform files for analysis with GTKWave:

```python
from amaranth.sim import Simulator

sim = Simulator(dut)
sim.add_clock(1 / 156.25e6, domain="ss")
sim.add_process(your_test_process)

# Write VCD file for waveform viewing
with sim.write_vcd("gen2_debug.vcd", "gen2_debug.gtkw"):
    sim.run()
```

Then open with GTKWave:

```bash
gtkwave gen2_debug.vcd
```

Key signals to monitor:
- `phy_source.valid`, `phy_source.data`, `phy_source.sync_head` — RX from PHY
- `phy_sink.valid`, `phy_sink.data`, `phy_sink.sync_head` — TX to PHY
- `block_parser.block_valid`, `block_parser.is_data`, `block_parser.is_control`
- `header_rx.new_header`, `header_rx.crc_good`
- `data_rx.packet_good`, `data_rx.packet_bad`
- `link_cmd_rx.new_command`, `link_cmd_rx.command`

---

## 9. Module Reference

### Core Modules

| Module | File | Description |
|--------|------|-------------|
| [`USB31DecPHY`](../gateware/usb/usb3/gen2/phy.py:13) | `gateware/usb/usb3/gen2/phy.py` | Amaranth wrapper for the Gowin `usb31dec.v` PHY. Instantiates the Verilog module and bridges PIPE signals to LUNA stream types. |
| [`Gen2PIPEInterface`](../gateware/usb/usb3/gen2/interfaces.py:37) | `gateware/usb/usb3/gen2/interfaces.py` | Signal bundle for the Gen2 PIPE interface (64-bit data + sync headers + control/status). |
| [`Gen2RawSuperSpeedStream`](../gateware/usb/usb3/gen2/interfaces.py:140) | `gateware/usb/usb3/gen2/interfaces.py` | Stream interface for raw PHY-level Gen2 data (64-bit + sync header + start_block). |
| [`Gen2SuperSpeedStreamInterface`](../gateware/usb/usb3/gen2/interfaces.py:180) | `gateware/usb/usb3/gen2/interfaces.py` | Stream interface for application-layer Gen2 data (64-bit payload + 8-bit per-byte valid). |

### Link Layer Modules

| Module | File | Description |
|--------|------|-------------|
| [`Gen2LinkLayer`](../gateware/usb/usb3/gen2/link/layer.py:43) | `gateware/usb/usb3/gen2/link/layer.py` | Top-level Gen2 link layer. Wires together block parser, receivers, transmitters, and TX arbiter. |
| [`Gen2BlockParser`](../gateware/usb/usb3/gen2/link/block_parser.py:14) | `gateware/usb/usb3/gen2/link/block_parser.py` | Parses 128b/132b blocks from the raw PHY stream. Accumulates two 64-bit words per block and classifies by sync header and control subtype. |
| [`Gen2HeaderPacketReceiver`](../gateware/usb/usb3/gen2/link/header.py:26) | `gateware/usb/usb3/gen2/link/header.py` | Receives and CRC-16 validates Gen2 header packets (12-byte payload in HP_START blocks). |
| [`Gen2HeaderPacketTransmitter`](../gateware/usb/usb3/gen2/link/header.py:177) | `gateware/usb/usb3/gen2/link/header.py` | Formats and transmits Gen2 header packets with computed CRC-16. |
| [`Gen2DataPacketReceiver`](../gateware/usb/usb3/gen2/link/data.py:35) | `gateware/usb/usb3/gen2/link/data.py` | Receives Gen2 data packets (DP_START + DATA blocks + END), validates CRC-32. |
| [`Gen2DataPacketTransmitter`](../gateware/usb/usb3/gen2/link/data.py:475) | `gateware/usb/usb3/gen2/link/data.py` | Formats and transmits Gen2 data packets with computed CRC-32. |
| [`Gen2LinkCommandReceiver`](../gateware/usb/usb3/gen2/link/command.py:14) | `gateware/usb/usb3/gen2/link/command.py` | Receives and validates Gen2 link commands (11-bit payload + CRC-5, dual-redundant). |
| [`Gen2LinkCommandTransmitter`](../gateware/usb/usb3/gen2/link/command.py:102) | `gateware/usb/usb3/gen2/link/command.py` | Formats and transmits Gen2 link commands as LINK_CMD control blocks. |

### CRC Modules

| Module | File | Description |
|--------|------|-------------|
| [`Gen2HeaderCRC`](../gateware/usb/usb3/gen2/crc.py:126) | `gateware/usb/usb3/gen2/crc.py` | CRC-16 engine for header packets. Supports 64-bit and 32-bit word advances. Uses `amaranth.lib.crc` for matrix generation. |
| [`Gen2DataCRC`](../gateware/usb/usb3/gen2/crc.py:202) | `gateware/usb/usb3/gen2/crc.py` | CRC-32 engine for data packets. Supports partial-word advances from 1 to 8 bytes. Uses `amaranth.lib.crc` for matrix generation. |

### Control Modules

| Module | File | Description |
|--------|------|-------------|
| [`Gen2LTSSMController`](../gateware/usb/usb3/gen2/ltssm.py:22) | `gateware/usb/usb3/gen2/ltssm.py` | Gen2 Link Training and Status State Machine. Manages PHY power states, speed negotiation (Gen1 → Gen2), and link recovery. |
| [`SpeedMux`](../gateware/usb/usb3/gen2/speed_mux.py:31) | `gateware/usb/usb3/gen2/speed_mux.py` | Multiplexes between Gen1 (32-bit) and Gen2 (64-bit) link layer paths. Routes headers, data, and link commands based on `use_gen2` signal. |

### Coding Utilities

| Function | File | Description |
|----------|------|-------------|
| [`is_data_block()`](../gateware/usb/usb3/gen2/coding.py:23) | `gateware/usb/usb3/gen2/coding.py` | Returns true when sync header indicates a data block (0x3). |
| [`is_control_block()`](../gateware/usb/usb3/gen2/coding.py:39) | `gateware/usb/usb3/gen2/coding.py` | Returns true when sync header indicates a control block (0xC). |
| [`get_control_subtype()`](../gateware/usb/usb3/gen2/coding.py:55) | `gateware/usb/usb3/gen2/coding.py` | Extracts the control block subtype from the first byte of a 64-bit word. |
| [`stream_matches_block_type()`](../gateware/usb/usb3/gen2/coding.py:74) | `gateware/usb/usb3/gen2/coding.py` | Checks if a Gen2 raw stream word matches a specific block type. |

### Class Hierarchy

```
Elaboratable
├── USB31DecPHY                    # PHY wrapper (Verilog instance)
├── Gen2LinkLayer                  # Top-level link layer
│   ├── Gen2BlockParser            # Block classification
│   ├── Gen2HeaderPacketReceiver   # Header RX + CRC-16
│   ├── Gen2HeaderPacketTransmitter # Header TX + CRC-16
│   ├── Gen2DataPacketReceiver     # Data RX + CRC-32
│   ├── Gen2DataPacketTransmitter  # Data TX + CRC-32
│   ├── Gen2LinkCommandReceiver    # Link command RX + CRC-5
│   └── Gen2LinkCommandTransmitter # Link command TX + CRC-5
├── Gen2LTSSMController            # Link training FSM
├── SpeedMux                       # Gen1/Gen2 path selection
├── Gen2HeaderCRC                  # CRC-16 engine (64-bit datapath)
└── Gen2DataCRC                    # CRC-32 engine (64-bit datapath)

Signal Bundles (not Elaboratable):
├── Gen2PIPEInterface              # PIPE signal bundle
├── Gen2RawSuperSpeedStream        # Raw PHY stream (extends StreamInterface)
└── Gen2SuperSpeedStreamInterface  # Application data stream (extends StreamInterface)
```

---

## 10. Troubleshooting

### Common Issues

#### PHY Does Not Initialize

**Symptoms:** `phy_status` never asserts; `pclk` is not toggling.

**Possible causes:**
1. **Reset not held long enough** — ensure `rst_n` is held low for ≥ 10 µs
   after power-up.
2. **PLL not locking** — check `cpll_ok`, `q0_qpll0_ok` signals. Verify the
   reference clock frequency and quality.
3. **SERDES not configured** — ensure the Gowin SERDES primitive is correctly
   instantiated with the right parameters for 10 GT/s operation.
4. **Missing Verilog includes** — the `usb31dec.v` file requires
   `static_macro_define.v`, `usb3_1_phy_name.v`, and
   `usb3_1_phy_top_define.vh`.

#### Link Does Not Train

**Symptoms:** LTSSM stays in `RX_DETECT` or `GEN1_WAIT`; `link_ready` never
asserts.

**Possible causes:**
1. **No link partner** — verify the USB cable is connected and the host
   supports USB 3.1 Gen2.
2. **RX termination not enabled** — the LTSSM should assert `rx_termination`
   during training. Check the LTSSM state.
3. **Signal integrity** — check SERDES eye diagrams. Gen2 at 10 GT/s requires
   good signal integrity.
4. **Power state incorrect** — verify `power_down` transitions through the
   correct sequence (P3 → P2 → P0).

#### CRC Errors on Received Packets

**Symptoms:** `header_source_crc_good` is never asserted; `data_packet_bad`
fires instead of `data_packet_good`.

**Possible causes:**
1. **Byte ordering mismatch** — Gen2 CRC is computed over bytes in
   little-endian order. Verify the byte layout matches the USB 3.2 spec §7.2.1.2.
2. **Block alignment issue** — the block parser may be misaligned. Check
   `block_parser.block_valid` and `block_parser.is_control` signals.
3. **Scrambling not handled** — the Gowin PHY should handle descrambling
   internally. If using a different PHY, ensure descrambling is applied before
   the link layer.

#### Speed Negotiation Fails (Stays at Gen1)

**Symptoms:** `use_gen2` never asserts; LTSSM falls back to `GEN1_ACTIVE`.

**Possible causes:**
1. **`request_speed_change` not asserted** — the Gen2 LTSSM requires an
   explicit speed change request. Connect this signal from your application
   logic or the Gen1 LTSSM.
2. **Gen1 LTSSM not coordinating** — the Gen2 LTSSM expects
   `gen1_link_ready` and `gen1_in_recovery` signals from the Gen1 LTSSM.
3. **PHY does not support Gen2** — verify the Gowin PHY IP is configured for
   Gen2 operation (10 GT/s line rate).
4. **Training timeout** — the speed change has a 20 ms timeout. Check if the
   PHY reports `phy_status` within this window.

#### TX Arbiter Starvation

**Symptoms:** Data packets are delayed or dropped; link commands are not sent.

**Possible causes:**
1. **Priority inversion** — the TX arbiter in
   [`Gen2LinkLayer`](../gateware/usb/usb3/gen2/link/layer.py:196) uses fixed
   priority: link commands > headers > data. If link commands are sent
   continuously, data packets will be starved.
2. **Backpressure from PHY** — if `phy_sink.ready` is deasserted, all
   transmitters will stall. Check the PHY's TX FIFO usage
   (`serdes_tx_fifo_wrusewd`).

### PHY Initialization Sequence

The Gowin `usb31dec.v` PHY follows this initialization sequence:

```
1. Power-on reset (phy_resetn = 0)
2. SERDES PLL lock (cpll_ok = 1, q0_qpll0_ok = 1)
3. Release reset (phy_resetn = 1)
4. PHY internal initialization:
   a. SERDES register configuration via UPAR interface
   b. RX alignment and elastic buffer setup
   c. LFPS detection circuitry enable
5. PHY ready (PhyStatus pulse)
6. LTSSM begins: INACTIVE → RX_DETECT → ...
```

### Clock Domain Considerations

| Clock Domain | Frequency | Source | Used By |
|---|---|---|---|
| `sync` | Board-specific (e.g., 50 MHz) | On-board oscillator | Reset logic, slow control |
| `ss` | ~156.25 MHz | `phy.pipe.pclk` | All Gen2 link layer modules, LTSSM, CRC engines |
| `serdes_tx` | Internal | `serdes_pcs_tx_clk` | SERDES TX path (internal to PHY) |
| `serdes_rx` | Internal | `serdes_pcs_rx_clk` | SERDES RX path (internal to PHY) |

**Important:** All Gen2 modules use `m.d.ss` for registered logic. If you need
to cross between `sync` and `ss` domains, use proper CDC (clock domain
crossing) techniques such as Amaranth's `FFSynchronizer` or async FIFOs.

```python
from amaranth.lib.cdc import FFSynchronizer

# Example: synchronize a status signal from ss → sync domain
link_ready_sync = Signal()
m.submodules += FFSynchronizer(
    i=ltssm.link_ready,
    o=link_ready_sync,
    o_domain="sync"
)
```

---

## Appendix: Import Quick Reference

All Gen2 public classes can be imported from the top-level package:

```python
from luna.gateware.usb.usb3.gen2 import (
    # Interfaces and types
    Gen2BlockType,
    Gen2PIPEInterface,
    Gen2RawSuperSpeedStream,
    Gen2SuperSpeedStreamInterface,

    # Coding utilities
    is_data_block,
    is_control_block,
    get_control_subtype,
    stream_matches_block_type,

    # PHY wrapper
    USB31DecPHY,

    # CRC engines
    Gen2HeaderCRC,
    Gen2DataCRC,

    # Link layer
    Gen2BlockParser,
    Gen2LinkCommandReceiver,
    Gen2LinkCommandTransmitter,
    Gen2HeaderPacketReceiver,
    Gen2HeaderPacketTransmitter,
    Gen2DataPacketReceiver,
    Gen2DataPacketTransmitter,
    Gen2LinkLayer,

    # Speed mux and LTSSM
    SpeedMux,
    Gen2LTSSMController,
)
```

Source: [`gateware/usb/usb3/gen2/__init__.py`](../gateware/usb/usb3/gen2/__init__.py)