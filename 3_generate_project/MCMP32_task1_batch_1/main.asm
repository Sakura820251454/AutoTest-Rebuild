 .sect ".text"
 .global MAIN_TEST
MAIN_TEST:

;************************看门狗关闭使能***************************;
reg16_config .macro regAddr, configValue
	MOVL XAR0,#0x0
	MOVL XAR1,#0x0
	MOVL XAR0,regAddr
	MOVL XAR1,configValue
	NOP
	NOP
	NOP
	MOV *XAR0,AR1
  	.endm

	EALLOW
reg16_WDCR .set 0x7029
value16_WDCR .set 0x0068
;;调用宏及变量：配置寄存器
	reg16_config #reg16_WDCR, #value16_WDCR
	NOP
	NOP
	EDIS
;************************看门狗关闭使能***************************;

;-------------------------------CLA 宏定义---------------------------;
;;CLA关键寄存器初始化
CLA_reset .macro
	EALLOW
	MOVL XAR0, #0X5D322
	MOV AL, #0X0039
	MOV AH, #0X0100
	MOVL *XAR0++, ACC		;;使能CLA时钟
	MOVL XAR0, #0X1410
	MOV AL, #0X0002
	MOV *XAR0++, AL         ;;CLA软复位，清除MIRUN和MIER
	MOVL XAR0, #0x1423
	MOV AL, #0X0000
	MOV *XAR0++, AL         ;;清除IFR
	MOVL XAR0, #0x142B
	MOV AL, #0X0000
	MOV *XAR0++, AL         ;;清除MSTF
	MOVL XAR0, #0x1428
	MOV AL, #0X0000
	MOV *XAR0++, AL         ;;清除MPC
	MOVL XAR0, #0x1410
	MOV AL, #0X0004
	MOV *XAR0++, AL         ;;使能IACKE位
	EDIS
	.endm

;;CLA后台任务设置
CLA_BGRNDSet .macro bgtaskaddr
	EALLOW
	MOVL XAR0, #0X141F
	MOVL XAR1, bgtaskaddr
	MOV *XAR0++, AR1
	EDIS
	.endm

;;任务向量写入
MVECT_wrt .macro MVECTRegaddr, taskaddr
	EALLOW
	MOVL XAR0, MVECTRegaddr
	MOVL XAR1, taskaddr
	MOV *XAR0++, AR1
	EDIS
	.endm

;;地址分配，分配CLA空间，配置CLA程序空间
mem_set .macro memdata, prgdata
	EALLOW
	MOVL XAR0, #0x5f424
	MOVL XAR1, memdata
	MOVL *XAR0++, XAR1		;;分配CLA空间
	MOVL XAR0, #0x5f426
	MOVL XAR1, prgdata
	MOVL *XAR0++, XAR1		;;分配CLA程序空间
	EDIS
	.endm

;;任务使能
IER_set .macro IFRdata
	EALLOW
	MOVL XAR0, #0X1425
	MOVL XAR1, IFRdata
	MOV *XAR0++, AR1
	EDIS
	.endm
;------------------------------------------------------------------------;

;-------------------------------CPU 程序段---------------------------;
	MOV SP, #0X1434
	ZAPA
	MOVL XAR0, #0XB000
	MOVL *XAR0++, ACC			;;初始化CLA运行结果地址
	CLA_reset					;;CLA关键寄存器初始化
	CLA_BGRNDSet #0X8000		;;后台任务设置
	MVECT_wrt #0x1400, #0x8000	;;设置任务1的入口地址为0x8000
	mem_set #0x5555, #0x001F	;;分配LS01为程序空间，LS23为数据空间
	IER_set #0x0081				;;使能任务1
	IACK #0X0001            	;;触发任务1
	NOP
	NOP
	NOP
	NOP		                    ;;IFR写
	NOP							;;任务触发第1拍，MIER和MIFR为1
	NOP							;;任务触发第2拍， 清除MIFR位， 置起MIRUN位  01
	NOP							;;cla取指触发
	NOP							;;cla第一条指令到达F1站
	NOP							;;cla第一条指令到达F2站
	NOP							;;cla第一条指令到达D1站
	MOVL XAR2, *-SP[0]							;;cla第一条指令到达D2站
	MOVL XAR3, *-SP[0]							;;cla第一条指令到达R1站
	MOVL XAR4, *-SP[0]   						;;cla第一条指令到达R2站
	MOVL XAR5, *-SP[0]							;;cla第一条指令到达E站, 第四条指令到达D2站
	MOVL XAR6, *-SP[0]							;;第五条指令到达D2站
 	MOVL XAR7, *-SP[0]				        	;;第五条指令到达R1站
	NOP							;;第五条指令到达R2站
	NOP							;;第五条指令到达E站
	NOP      					;;第五条指令到达W站


;------------------------------CLA 结果判断---------------------------;
	MOV SP, #0XBB00
	MOVL XAR1, #0X0000
PC1:
	ADDB XAR1, #0X1
	CMP AR1, #0XFFFF
	BF IDLE, EQ					;;循环0xffff次后认为执行错误
	MOVL ACC, *-SP[0]
	MOV PH, #0XAAAA
	MOV PL, #0XAAAA
	CMPL ACC, P					;;从消息空间里读出值，CLA运行正确
	BF claright, EQ
	MOVL ACC, *-SP[0]
	MOV PH, #0X5555
	MOV PL, #0X5555
	CMPL ACC, P
	BF IDLE, EQ
	BF PC1, NEQ					;;从消息空间里读出值，CLA运行错误
claright:

Right:
	ESTOP0
IDLE:
	IDLE
