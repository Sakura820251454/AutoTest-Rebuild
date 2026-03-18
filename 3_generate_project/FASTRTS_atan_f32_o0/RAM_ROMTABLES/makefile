################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

CG_TOOL_ROOT := C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS

GEN_OPTS__FLAG := 
GEN_CMDS__FLAG := 

ORDERED_OBJS += \
"./fastrts_atan.obj" \
"./fastrts_examples_main.obj" \
"./fastrts_examples_setup.obj" \
"./golden.obj" \
"./input.obj" \
$(GEN_CMDS__FLAG) \
-lrts2800_fpu32_fast_supplement.lib \
-l"C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/examples/common/f28003x/fastrts_examples_lnk.cmd" \
-l"C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/lib/rts2800_fpu32_fast_supplement_coff.lib" \
-l"C:/ti/c2000/C2000Ware_6_00_01_00/libraries/boot_rom/f28003x/rev0/rom_symbol_libs/bootROM/F28003xCPU1_BootROM_Symbols_fpu32.lib" \
-l"C:/ti/c2000/C2000Ware_6_00_01_00/driverlib/f28003x/driverlib/ccs/Debug/driverlib.lib" \
-llibc.a \

-include ../makefile.init

RM := DEL /F
RMDIR := RMDIR /S/Q

# All of the sources participating in the build are defined here
-include sources.mk
-include subdir_vars.mk
-include subdir_rules.mk
-include objects.mk

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(C55_DEPS)),)
-include $(C55_DEPS)
endif
ifneq ($(strip $(C_UPPER_DEPS)),)
-include $(C_UPPER_DEPS)
endif
ifneq ($(strip $(S67_DEPS)),)
-include $(S67_DEPS)
endif
ifneq ($(strip $(S62_DEPS)),)
-include $(S62_DEPS)
endif
ifneq ($(strip $(S_DEPS)),)
-include $(S_DEPS)
endif
ifneq ($(strip $(OPT_DEPS)),)
-include $(OPT_DEPS)
endif
ifneq ($(strip $(C??_DEPS)),)
-include $(C??_DEPS)
endif
ifneq ($(strip $(ASM_UPPER_DEPS)),)
-include $(ASM_UPPER_DEPS)
endif
ifneq ($(strip $(S??_DEPS)),)
-include $(S??_DEPS)
endif
ifneq ($(strip $(C64_DEPS)),)
-include $(C64_DEPS)
endif
ifneq ($(strip $(CXX_DEPS)),)
-include $(CXX_DEPS)
endif
ifneq ($(strip $(S64_DEPS)),)
-include $(S64_DEPS)
endif
ifneq ($(strip $(INO_DEPS)),)
-include $(INO_DEPS)
endif
ifneq ($(strip $(CLA_DEPS)),)
-include $(CLA_DEPS)
endif
ifneq ($(strip $(S55_DEPS)),)
-include $(S55_DEPS)
endif
ifneq ($(strip $(SV7A_DEPS)),)
-include $(SV7A_DEPS)
endif
ifneq ($(strip $(C62_DEPS)),)
-include $(C62_DEPS)
endif
ifneq ($(strip $(C67_DEPS)),)
-include $(C67_DEPS)
endif
ifneq ($(strip $(PDE_DEPS)),)
-include $(PDE_DEPS)
endif
ifneq ($(strip $(K_DEPS)),)
-include $(K_DEPS)
endif
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
ifneq ($(strip $(CC_DEPS)),)
-include $(CC_DEPS)
endif
ifneq ($(strip $(C++_DEPS)),)
-include $(C++_DEPS)
endif
ifneq ($(strip $(C43_DEPS)),)
-include $(C43_DEPS)
endif
ifneq ($(strip $(S43_DEPS)),)
-include $(S43_DEPS)
endif
ifneq ($(strip $(ASM_DEPS)),)
-include $(ASM_DEPS)
endif
ifneq ($(strip $(S_UPPER_DEPS)),)
-include $(S_UPPER_DEPS)
endif
ifneq ($(strip $(CPP_DEPS)),)
-include $(CPP_DEPS)
endif
ifneq ($(strip $(SA_DEPS)),)
-include $(SA_DEPS)
endif
endif

-include ../makefile.defs

# Add inputs and outputs from these tool invocations to the build variables 
EXE_OUTPUTS += \
FASTRTS_atan_f32_o0.out \

EXE_OUTPUTS__QUOTED += \
"FASTRTS_atan_f32_o0.out" \

BIN_OUTPUTS += \
FASTRTS_atan_f32_o0.hex \

BIN_OUTPUTS__QUOTED += \
"FASTRTS_atan_f32_o0.hex" \


# All Target
all: FASTRTS_atan_f32_o0.out

# Tool invocations
FASTRTS_atan_f32_o0.out: $(OBJS) $(CMD_SRCS) $(GEN_CMDS)
	@echo 'Building target: "$@"'
	@echo 'Invoking: C2000 Linker'
	"C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS/bin/cl2000" -v28 -ml -mt --float_support=fpu32 --advice:performance=all --define=RAM --define=ROMTABLES --define=CPU1 --define=USE_FID=0 -g --diag_warning=225 --diag_wrap=off --display_error_number --gen_func_subsections=on --abi=coffabi -k --asm_listing --c_src_interlist -z -m"FASTRTS_atan_f32_o0.map" --heap_size=0x200 --stack_size=0x300 --warn_sections -i"C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/lib" -i"C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/examples/common/f28003x" -i"C:/ti/c2000/C2000Ware_6_00_01_00/device_support/f28003x/common/include" -i"C:/ti/c2000/C2000Ware_6_00_01_00/libraries/boot_rom/f28003x/rev0/rom_symbol_libs/bootROM" -i"C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS/lib" -i"C:/ti/c2000/C2000Ware_6_00_01_00/libraries/math/FPUfastRTS/c28/internal" -i"C:/ti/c2000/C2000Ware_6_00_01_00/driverlib/f28003x/driverlib/ccs/Debug" --priority --reread_libs --define=RAM --define=ROMTABLES --diag_wrap=off --display_error_number --xml_link_info="FASTRTS_atan_f32_o0_linkInfo.xml" --rom_model -o "FASTRTS_atan_f32_o0.out" $(ORDERED_OBJS)
	@echo 'Finished building target: "$@"'
	@echo ' '

FASTRTS_atan_f32_o0.hex: $(EXE_OUTPUTS)
	@echo 'Building secondary target: "$@"'
	@echo 'Invoking: C2000 Hex Utility'
	"C:/ti/ccs1210/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS/bin/hex2000" --diag_wrap=off -o "FASTRTS_atan_f32_o0.hex" $(EXE_OUTPUTS__QUOTED)
	@echo 'Finished building secondary target: "$@"'
	@echo ' '

# Other Targets
clean:
	-$(RM) $(BIN_OUTPUTS__QUOTED)$(EXE_OUTPUTS__QUOTED)
	-$(RM) "fastrts_atan.lst" "fastrts_examples_main.lst" "fastrts_examples_setup.lst" "golden.lst" "input.lst" 
	-$(RM) "fastrts_atan.obj" "fastrts_examples_main.obj" "fastrts_examples_setup.obj" "golden.obj" "input.obj" 
	-$(RM) "fastrts_atan.d" "fastrts_examples_main.d" "fastrts_examples_setup.d" "golden.d" "input.d" 
	-$(RM) "fastrts_atan.asm" "fastrts_examples_main.asm" "fastrts_examples_setup.asm" "golden.asm" "input.asm" 
	-@echo 'Finished clean'
	-@echo ' '

.PHONY: all clean dependents
.SECONDARY:

-include ../makefile.targets

