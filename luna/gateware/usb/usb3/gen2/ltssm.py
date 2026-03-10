#
# This file is part of LUNA.
#
# Copyright (c) 2024 Great Scott Gadgets <info@greatscottgadgets.com>
# SPDX-License-Identifier: BSD-3-Clause
""" Gen2 Link Training and Status State Machine (LTSSM) gateware. """

#
# This module implements a Gen2-aware LTSSM controller that works alongside
# the Gen1 LTSSM to manage speed negotiation from Gen1 (5 Gbps) to Gen2
# (10 Gbps). The Gowin PHY (usb31dec.v) handles most low-level training;
# this controller manages high-level state transitions and PHY power states.
#
# Reference: USB 3.2 specification §7.5
#

import math

from amaranth import *


class Gen2LTSSMController(Elaboratable):
    """Gen2 Link Training and Status State Machine.

    This controller manages the Gen2 PHY link training and speed negotiation.
    It works alongside the Gen1 LTSSM to handle speed upgrades from Gen1 to Gen2.

    The Gen2 LTSSM handles:
    1. Initial link training at Gen1 speed (delegated to Gen1 LTSSM)
    2. Speed capability exchange via TS1/TS2 ordered sets
    3. Speed change to Gen2 via Recovery sequence
    4. Gen2 link maintenance (recovery, power management)

    For the Gowin PHY (usb31dec.v), much of the low-level training is handled
    by the PHY itself. The LTSSM primarily manages:
    - PHY power states (P0, P1, P2, P3)
    - LFPS signaling control
    - Speed negotiation decisions
    - Recovery triggers

    Parameters
    ----------
    ss_clock_frequency : float
        SuperSpeed clock frequency in Hz. Default 156.25e6 for Gen2.
    """

    def __init__(self, ss_clock_frequency=156.25e6):
        self._ss_clock_frequency = ss_clock_frequency

        #
        # I/O port.
        #

        # === PHY Control Outputs ===
        self.power_down              = Signal(2, reset=0b11)   # PIPE power state (P0=00, P1=01, P2=10, P3=11)
        self.tx_elec_idle            = Signal(reset=1)         # TX electrical idle
        self.rx_termination          = Signal()                # RX termination enable
        self.rx_polarity             = Signal()                # RX polarity inversion
        self.tx_detect_rx_loopback   = Signal()                # Receiver detection

        # === PHY Status Inputs ===
        self.phy_status              = Signal()                # PHY status (transitions)
        self.rx_elec_idle            = Signal()                # RX electrical idle
        self.rx_status               = Signal(3)               # RX status
        self.power_present           = Signal()                # VBUS present

        # === Link Status ===
        self.link_ready              = Signal()                # Link is trained and in U0
        self.use_gen2                = Signal()                # Gen2 speed active
        self.in_reset                = Signal()                # Link is in reset

        # === Gen1 LTSSM Coordination ===
        self.gen1_link_ready         = Signal()                # Gen1 LTSSM reports link ready
        self.gen1_in_recovery        = Signal()                # Gen1 LTSSM is in recovery
        self.request_speed_change    = Signal()                # Request Gen2 speed upgrade
        self.speed_change_complete   = Signal()                # Speed change completed

        # === External Triggers ===
        self.trigger_recovery        = Signal()                # External recovery trigger
        self.in_usb_reset            = Signal()                # USB bus reset detected
        self.perform_rx_detection    = Signal()                # Trigger RX detection
        self.link_partner_detected   = Signal()                # RX detection result


    def elaborate(self, platform):
        m = Module()

        #
        # Timeout tracking.
        #

        # Create a timer that can count up to at least 360mS, the largest possible timeout.
        # This mirrors the Gen1 LTSSM approach. [USB 3.2r1: 7.5]
        cycles_in_360mS = int(math.ceil(360e-3 * self._ss_clock_frequency))
        cycles_in_state = Signal(range(cycles_in_360mS + 1))

        # Count by default; this will be automatically cleared on state transitions.
        m.d.ss += cycles_in_state.eq(cycles_in_state + 1)


        #
        # FSM helpers.
        #

        # Create a list of tasks to perform on entry to a given state.
        tasks_on_entry = {}


        def transition_to_state(state):
            """ FSM helper that handles transitions to the given state.

            Automatically handles any "on entry" conditions for the given state.
            """

            # Clear our "time-in-state" counter.
            m.d.ss += cycles_in_state.eq(0)

            # If we have any additional entry conditions for the given state, apply them.
            if state in tasks_on_entry:
                m.d.ss += tasks_on_entry[state]

            m.next = state


        def transition_on_timeout(timeout, *, to):
            """ FSM helper that adds a state transition invoked after a timeout. """

            # Figure out how many cycles need to pass before we consider ourselves timed out.
            timeout_in_cycles = int(math.ceil(timeout * self._ss_clock_frequency))

            # If we've reached that many cycles, transition to the target state.
            with m.If(cycles_in_state == timeout_in_cycles):
                transition_to_state(to)


        def handle_usb_resets():
            """ FSM helper that returns to RESET state when a USB reset is detected. """

            with m.If(self.in_usb_reset):
                transition_to_state("RESET")


        #
        # PHY status edge detection.
        #

        # Track the previous value of phy_status to detect rising edges,
        # which indicate PHY operation completion (e.g. power state change done).
        phy_status_prev = Signal()
        phy_status_rose = Signal()
        m.d.ss   += phy_status_prev.eq(self.phy_status)
        m.d.comb += phy_status_rose.eq(self.phy_status & ~phy_status_prev)


        #
        # FSM entry tasks.
        #

        # On entering GEN1_ACTIVE, clear the use_gen2 flag.
        tasks_on_entry['GEN1_ACTIVE'] = [
            self.use_gen2.eq(0),
        ]

        # On entering GEN2_ACTIVE, assert the use_gen2 flag.
        tasks_on_entry['GEN2_ACTIVE'] = [
            self.use_gen2.eq(1),
        ]

        # On entering RESET, clear use_gen2 and assert in_reset.
        tasks_on_entry['RESET'] = [
            self.use_gen2.eq(0),
        ]


        #
        # Main Gen2 Link Training and Status State Machine
        #
        with m.FSM(domain="ss"):

            # ----------------------------------------------------------------
            # INACTIVE -- link is inactive or disconnected.
            # PHY is in P3 (lowest power), TX electrically idle.
            # We wait here until VBUS power is detected.
            # ----------------------------------------------------------------
            with m.State("INACTIVE"):
                m.d.comb += [
                    self.tx_elec_idle     .eq(1),
                    self.rx_termination   .eq(0),
                ]
                m.d.ss += self.power_down.eq(0b11)  # P3

                # Once VBUS is present, begin receiver detection.
                with m.If(self.power_present):
                    transition_to_state("RX_DETECT")


            # ----------------------------------------------------------------
            # RX_DETECT -- attempt to detect a link partner.
            # PHY is in P2, we assert receiver detection and wait for a result.
            # ----------------------------------------------------------------
            with m.State("RX_DETECT"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle            .eq(1),
                    self.perform_rx_detection    .eq(1),
                    self.tx_detect_rx_loopback   .eq(1),
                    self.rx_termination          .eq(0),
                ]
                m.d.ss += self.power_down.eq(0b10)  # P2

                # If a link partner is detected, proceed to wait for Gen1 training.
                with m.If(self.link_partner_detected):
                    transition_to_state("GEN1_WAIT")

                # If no partner detected within 12ms, go back to INACTIVE.
                transition_on_timeout(12e-3, to="INACTIVE")


            # ----------------------------------------------------------------
            # GEN1_WAIT -- waiting for the Gen1 LTSSM to complete link training.
            # The Gen1 LTSSM handles the full Polling sequence (LFPS, RxEQ,
            # Active, Configuration, Idle) and reports gen1_link_ready when
            # the link reaches U0 at Gen1 speed.
            # ----------------------------------------------------------------
            with m.State("GEN1_WAIT"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0

                # When Gen1 link is ready, check if we should attempt Gen2.
                with m.If(self.gen1_link_ready):
                    with m.If(self.request_speed_change):
                        transition_to_state("SPEED_CHANGE_INIT")
                    with m.Else():
                        transition_to_state("GEN1_ACTIVE")

                # If Gen1 training takes too long (360ms), something is wrong.
                transition_on_timeout(360e-3, to="RESET")


            # ----------------------------------------------------------------
            # GEN1_ACTIVE -- link is operating at Gen1 speed (5 Gbps).
            # We report link_ready and monitor for speed change requests.
            # ----------------------------------------------------------------
            with m.State("GEN1_ACTIVE"):
                handle_usb_resets()

                m.d.comb += [
                    self.link_ready       .eq(1),
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0

                # If a speed change to Gen2 is requested, initiate the process.
                with m.If(self.request_speed_change):
                    transition_to_state("SPEED_CHANGE_INIT")

                # If the Gen1 LTSSM enters recovery (e.g. link error), track it.
                with m.If(self.gen1_in_recovery):
                    transition_to_state("GEN1_WAIT")


            # ----------------------------------------------------------------
            # SPEED_CHANGE_INIT -- initiating speed change from Gen1 to Gen2.
            # We signal the Gen1 LTSSM to enter recovery, which is the
            # mechanism used for speed negotiation per USB 3.2 §7.5.
            # ----------------------------------------------------------------
            with m.State("SPEED_CHANGE_INIT"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0

                # Wait for the Gen1 LTSSM to enter recovery.
                with m.If(self.gen1_in_recovery):
                    transition_to_state("SPEED_CHANGE_RECOVERY")

                # If recovery doesn't happen within 20ms, fall back to Gen1.
                transition_on_timeout(20e-3, to="GEN1_ACTIVE")


            # ----------------------------------------------------------------
            # SPEED_CHANGE_RECOVERY -- PHY is changing speed.
            # The PIPE PHY transitions through power states during the speed
            # change. We wait for the PHY to signal completion via phy_status.
            # ----------------------------------------------------------------
            with m.State("SPEED_CHANGE_RECOVERY"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle     .eq(1),
                    self.rx_termination   .eq(1),
                ]
                # Request PHY to change speed by transitioning power state.
                m.d.ss += self.power_down.eq(0b01)  # P1 — intermediate state for speed change

                # When PHY signals completion, move to training.
                with m.If(phy_status_rose):
                    transition_to_state("SPEED_CHANGE_TRAINING")

                # If speed change doesn't complete within 20ms, fall back.
                transition_on_timeout(20e-3, to="GEN1_ACTIVE")


            # ----------------------------------------------------------------
            # SPEED_CHANGE_TRAINING -- Gen2 training sequences are being
            # exchanged. The Gowin PHY handles the actual TS1/TS2 exchange
            # at Gen2 speed. We wait for the PHY to report success or failure.
            # ----------------------------------------------------------------
            with m.State("SPEED_CHANGE_TRAINING"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0 — active training

                # PHY reports training complete via phy_status and rx_status.
                # rx_status == 0b000 indicates successful decode/training.
                with m.If(phy_status_rose):
                    with m.If(self.rx_status == 0b000):
                        # Training succeeded — link is now at Gen2 speed.
                        transition_to_state("GEN2_ACTIVE")
                    with m.Else():
                        # Training failed — fall back to Gen1.
                        transition_to_state("GEN1_ACTIVE")

                # If training doesn't complete within 20ms, fall back.
                transition_on_timeout(20e-3, to="GEN1_ACTIVE")


            # ----------------------------------------------------------------
            # GEN2_ACTIVE -- link is operating at Gen2 speed (10 Gbps).
            # This is the primary active state for Gen2 operation.
            # ----------------------------------------------------------------
            with m.State("GEN2_ACTIVE"):
                handle_usb_resets()

                m.d.comb += [
                    self.link_ready       .eq(1),
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0

                # If an external recovery trigger fires, enter Gen2 recovery.
                with m.If(self.trigger_recovery):
                    transition_to_state("GEN2_RECOVERY")

                # If the PHY detects RX electrical idle (link partner went away
                # or entered low-power), also enter recovery.
                with m.If(self.rx_elec_idle):
                    transition_to_state("GEN2_RECOVERY")


            # ----------------------------------------------------------------
            # GEN2_RECOVERY -- Gen2 link recovery.
            # The link has encountered an error or trigger requiring
            # re-training at Gen2 speed. The PHY handles the TS1/TS2
            # exchange; we manage the high-level state.
            # ----------------------------------------------------------------
            with m.State("GEN2_RECOVERY"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0

                # Wait for PHY to report recovery complete.
                with m.If(phy_status_rose):
                    transition_to_state("GEN2_RECOVERY_CONFIG")

                # If recovery doesn't complete within 12ms, the link is lost.
                transition_on_timeout(12e-3, to="RESET")


            # ----------------------------------------------------------------
            # GEN2_RECOVERY_CONFIG -- Gen2 recovery configuration phase.
            # TS2 handshake at Gen2 speed to confirm both sides are ready.
            # ----------------------------------------------------------------
            with m.State("GEN2_RECOVERY_CONFIG"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0

                # PHY signals configuration complete.
                with m.If(phy_status_rose):
                    transition_to_state("GEN2_RECOVERY_IDLE")

                # Timeout — link is not recoverable at Gen2.
                transition_on_timeout(12e-3, to="RESET")


            # ----------------------------------------------------------------
            # GEN2_RECOVERY_IDLE -- Gen2 recovery idle handshake.
            # Final synchronization before returning to GEN2_ACTIVE.
            # ----------------------------------------------------------------
            with m.State("GEN2_RECOVERY_IDLE"):
                handle_usb_resets()

                m.d.comb += [
                    self.tx_elec_idle     .eq(0),
                    self.rx_termination   .eq(1),
                ]
                m.d.ss += self.power_down.eq(0b00)  # P0

                # Speed change complete signal indicates idle handshake done.
                with m.If(self.speed_change_complete):
                    transition_to_state("GEN2_ACTIVE")

                # PHY status can also indicate completion.
                with m.If(phy_status_rose):
                    transition_to_state("GEN2_ACTIVE")

                # Timeout — link is not recoverable at Gen2, fall back.
                transition_on_timeout(12e-3, to="RESET")


            # ----------------------------------------------------------------
            # RESET -- return to Gen1 speed and restart link training.
            # We clear the Gen2 flag and signal the Gen1 LTSSM to restart.
            # ----------------------------------------------------------------
            with m.State("RESET"):
                m.d.comb += [
                    self.in_reset         .eq(1),
                    self.tx_elec_idle     .eq(1),
                    self.rx_termination   .eq(0),
                ]
                m.d.ss += self.power_down.eq(0b11)  # P3

                # After a brief hold (2ms), transition back to wait for Gen1.
                transition_on_timeout(2e-3, to="GEN1_WAIT")

        return m
