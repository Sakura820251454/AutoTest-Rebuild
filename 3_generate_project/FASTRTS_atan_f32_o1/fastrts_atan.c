//#############################################################################
//
//! \file   fastrts_atan.c
//!
//! \brief  Runs the atan routine
//! \author Vishal Coelho
//! \date   Sep 21, 2016
//
//  Group:          C2000
//  Target Device:  TMS320F28004x
//
//#############################################################################
//
//
// $Copyright: Copyright (C) 2025 Texas Instruments Incorporated -
//             http://www.ti.com/ ALL RIGHTS RESERVED $
//#############################################################################

//*****************************************************************************
// the includes
//*****************************************************************************
#include "fastrts_examples_setup.h"
#include "fastrts.h"
#include "fpu32/C28x_FPU_FastRTS.h"

//*****************************************************************************
// the defines
//*****************************************************************************
#define TEST_SIZE   (256U)
//*****************************************************************************
// the globals
//*****************************************************************************
// The global pass, fail values
uint16_t pass = 0U, fail = 0U;
// The absolute error between the result and expected values
float32_t tolerance = 1.3e-7;

float32_t test_output[TEST_SIZE];
float32_t test_error[TEST_SIZE];

extern const unsigned short expected_data[];

int compare_memory_blocks(const void *block1, const void *block2, int size)
{
    int i;

    const unsigned short *p1 = (const unsigned short*) block1;
    const unsigned short *p2 = (const unsigned short*) block2;

    for (i = 0; i < size; i++)
    {
        unsigned short a;
        unsigned short b;
        a = p1[i];
        b = p2[i];
        if (p1[i] != p2[i])
        {
            asm(" ESTOP0");
            return 0; // ʧ
        }
    }
    return 1; // ɹ
}

//*****************************************************************************
// the function definitions
//*****************************************************************************
void FastRTS_runTest(void)
{
    // Locals
    uint16_t i;
    float32u_t in, out, gold, err;

    //<<VC160921: cant check ulp error as this only applies to
    // fixed point representation of the same set of numbers
    //
    //float32u_t errulp;
    //
    // VC160921>>

    for (i = 0U; i < TEST_SIZE; i++)
    {
        out.f32 = FLT_MAX;
        in.f32 = test_input[i];

        // Run the calculation function
        out.f32 = atanf(in.f32);

        test_output[i] = out.f32;
//        gold.f32 = test_golden[i];
//        err.f32  = fabsf(out.f32 - gold.f32);
//        if(err.f32 < tolerance)
//        {
//            pass++;
//        }
//        else
//        {
//            fail++;
//        }
//        test_error[i] = err.f32;
    }

    int memory_match = compare_memory_blocks(&test_output, expected_data,
                                             sizeof(test_output));

    // ڱȽϽת
    if (memory_match)
    {
        goto true_label;
    }
    else
    {
        goto false_label;
    }

    false_label: asm("IDLE:");
    asm(" NOP");
    asm(" IDLE");
//        return 0;  // ִ

    true_label: asm("Right:");
    asm(" NOP");
    asm(" ESTOP0");

}

// End of File
