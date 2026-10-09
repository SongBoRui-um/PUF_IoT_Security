/*
 * puf_test.c — DE1-SoC Arbiter PUF fingerprint collector (corrected)
 *
 * FIX SUMMARY vs original:
 *
 * 1. TRIGGER TIMING (most critical):
 *    Original: trigger=0, challenge=c, trigger=1, wait 10us, read.
 *    The PUF arbiter now uses CLOCK_50 (20 ns period). A 10 us wait is
 *    500 clock cycles — plenty for the FF to latch. However, the challenge
 *    must be SET BEFORE asserting trigger, with a genuine settling delay.
 *    Order: challenge→settle→trigger_low→trigger_high→read.
 *
 * 2. MAJORITY-VOTE SAMPLING:
 *    A single read is unreliable because the PUF response sits near the
 *    metastability boundary for some challenges. We take N_SAMPLES reads
 *    per challenge and return the majority result. This does NOT defeat the
 *    PUF — it just resolves noisy borderline challenges deterministically.
 *    Increase N_SAMPLES to 31 or 63 for higher reliability in production.
 *
 * 3. RESPONSE PIO DIRECTION:
 *    puf_response is a read-only PIO. We only read from it, never write.
 *    The original code was correct here; kept unchanged.
 *
 * 4. TRIGGER HELD LOW BETWEEN SAMPLES:
 *    Between consecutive samples of the same challenge we pulse trigger
 *    low→high again. The rising-edge detector in the RTL requires a clean
 *    falling edge before re-arming.
 *
 * Register map (confirmed from Qsys screenshot):
 *   0x0000_0000  led_out      (write)
 *   0x0000_0010  puf_trigger  (write, bit 0)
 *   0x0000_0020  puf_challenge(write, bits 3:0)
 *   0x0000_0030  puf_response (read,  bit 0)
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <stdint.h>

#define HW_REGS_BASE        0xFF200000u
#define HW_REGS_SPAN        0x00010000u

#define LED_PIO_BASE        0x00000000u
#define PUF_TRIGGER_BASE    0x00000010u
#define PUF_CHALLENGE_BASE  0x00000020u
#define PUF_RESPONSE_BASE   0x00000030u

/* Number of samples per challenge for majority vote.
   Must be odd. 11 is a good balance of speed vs stability. */
#define N_SAMPLES           11

/* Microsecond delays — generous to survive AXI bus latency on a busy Linux system */
#define SETTLE_US           200   /* challenge-to-trigger delay  */
#define HOLD_US             500   /* trigger-high hold time       */
#define RESET_US            100   /* trigger-low reset time       */

static int majority_vote(volatile uint32_t *trigger_ptr,
                         volatile uint32_t *response_ptr,
                         int n)
{
    int ones = 0;
    for (int i = 0; i < n; i++) {
        /* Arm: drive trigger low (re-sets rising-edge detector) */
        *trigger_ptr = 0u;
        usleep(RESET_US);

        /* Fire: rising edge → RTL samples w_top_3 on next CLOCK_50 */
        *trigger_ptr = 1u;
        usleep(HOLD_US);

        /* Read resolved response */
        ones += (int)((*response_ptr) & 0x1u);
    }
    /* Drive trigger low after the burst so the PIO is idle */
    *trigger_ptr = 0u;

    return (ones > n / 2) ? 1 : 0;
}

int main(void)
{
    int   fd;
    void *virtual_base;

    volatile uint32_t *led_ptr;
    volatile uint32_t *puf_trigger_ptr;
    volatile uint32_t *puf_challenge_ptr;
    volatile uint32_t *puf_response_ptr;

    /* ------------------------------------------------------------------ */
    fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd == -1) {
        perror("open /dev/mem");
        return 1;
    }

    virtual_base = mmap(NULL, HW_REGS_SPAN,
                        PROT_READ | PROT_WRITE, MAP_SHARED,
                        fd, HW_REGS_BASE);
    if (virtual_base == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return 1;
    }

    led_ptr           = (volatile uint32_t *)((uintptr_t)virtual_base + LED_PIO_BASE);
    puf_trigger_ptr   = (volatile uint32_t *)((uintptr_t)virtual_base + PUF_TRIGGER_BASE);
    puf_challenge_ptr = (volatile uint32_t *)((uintptr_t)virtual_base + PUF_CHALLENGE_BASE);
    puf_response_ptr  = (volatile uint32_t *)((uintptr_t)virtual_base + PUF_RESPONSE_BASE);

    /* ------------------------------------------------------------------ */
    printf("=== DE1-SoC Zero-Trust PUF Fingerprint Collector (corrected) ===\n");
    printf("Samples per challenge: %d (majority vote)\n\n", N_SAMPLES);
    printf("Challenge (hex) | Challenge (bin) | Response\n");
    printf("-------------------------------------------------\n");

    /* Global reset: ensure trigger is low before starting */
    *puf_trigger_ptr   = 0u;
    *puf_challenge_ptr = 0u;
    usleep(1000);

    uint16_t fingerprint = 0u;   /* accumulate 16-bit CRP fingerprint */

    for (int c = 0; c < 16; c++) {
        /* Step 1: set challenge, wait for routing MUX to settle */
        *puf_challenge_ptr = (uint32_t)c;
        usleep(SETTLE_US);

        /* Step 2: majority-vote sampling */
        int response = majority_vote(puf_trigger_ptr, puf_response_ptr, N_SAMPLES);

        fingerprint |= (uint16_t)(response << c);

        printf("      0x%X       |   4'b%d%d%d%d    |    %d\n",
               c,
               (c >> 3) & 1, (c >> 2) & 1, (c >> 1) & 1, c & 1,
               response);

        /* Light up LEDs to show progress (lower 10 bits of fingerprint so far) */
        *led_ptr = (uint32_t)(fingerprint & 0x3FFu);
    }

    printf("-------------------------------------------------\n");
    printf("16-bit device fingerprint: 0x%04X\n", fingerprint);
    printf("\nNote: if all responses are still 0, verify:\n");
    printf("  1. arbiter_puf_4bit.v has clk_50 port connected in DE1_SoC_Demo.v\n");
    printf("  2. Bitstream was recompiled after Verilog changes\n");
    printf("  3. .sdc false_path constraint is applied for puf_core_inst|meta1\n");

    /* ------------------------------------------------------------------ */
    if (munmap(virtual_base, HW_REGS_SPAN) != 0)
        perror("munmap");
    close(fd);
    return 0;
}