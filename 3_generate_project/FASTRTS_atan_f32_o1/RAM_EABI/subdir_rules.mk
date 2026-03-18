################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
%.obj: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: C2000 Compiler'
	"C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS/bin/cl2000" -v28 -ml -mt --float_support=fpu32 -O1 --include_path="C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS/include" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/device_support/f28003x/common/include" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/driverlib/f28003x/driverlib/" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/examples/common/f28003x/" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/examples/common/" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/include" --advice:performance=all --define=RAM --define=CPU1 --define=USE_FID=0 -g --diag_warning=225 --diag_wrap=off --display_error_number --abi=eabi -k --asm_listing --c_src_interlist --preproc_with_compile --preproc_dependency="$(basename $(<F)).d_raw" $(GEN_OPTS__FLAG) "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

fastrts_examples_setup.obj: C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/examples/common/fastrts_examples_setup.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Building file: "$<"'
	@echo 'Invoking: C2000 Compiler'
	"C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS/bin/cl2000" -v28 -ml -mt --float_support=fpu32 -O1 --include_path="C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS/include" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/device_support/f28003x/common/include" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/driverlib/f28003x/driverlib/" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/examples/common/f28003x/" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/examples/common/" --include_path="C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/include" --advice:performance=all --define=RAM --define=CPU1 --define=USE_FID=0 -g --diag_warning=225 --diag_wrap=off --display_error_number --abi=eabi -k --asm_listing --c_src_interlist --preproc_with_compile --preproc_dependency="$(basename $(<F)).d_raw" $(GEN_OPTS__FLAG) "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


