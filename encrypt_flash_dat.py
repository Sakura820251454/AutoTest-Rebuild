#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# encrypt_flash_dat.py — FLASH / OTP 线性镜像拆分 + 阵列加密 (dat/Memory/)
#
# 两个数据集, 拆分与加密规则完全相同 (线性行 q → 实例 q&3、实例内行 q>>2):
#   ① FLASH.dat —— 整片 512KB 线性镜像 (65536 行 × 64-bit; 行 q 含字地址
#      W = 4q..4q+3 四个 16-bit 半字, 半字 lane = W&3, w0 = 低 16 位)。
#      输出 FLASH0.dat ~ FLASH3.dat (各 16384 行 × 64-bit) = 4 个 S40NEF16KX72_S0 宏的初始化数据。
#   ② otp.dat  —— OTP 整片线性镜像 (512 行 × 64-bit; 行 0~255 = TOTP 窗
#      0x8_0000~0x8_03FF 共 1024 字, 行 256~511 = UOTP 窗 0x8_0400~0x8_07FF 共 1024 字)。
#      输出 OTP0.dat ~ OTP3.dat (各 128 行 × 64-bit; 每实例行 0~63 = TOTP、64~127 = UOTP)。
# 输出为 64 位密文 (16 hex/行; 与模型 flash_mem/otp_mem 的 64 位存储及读回时的 ECC 重建一致),
# 可直接作为对应存储实例的初始化数据。
# FPGA 模型 (rtl/flash_bram_half.v ×4) 只实现每实例最后 0x800 行 (= C28x 0x338000~0x33FFFF 区):
#   由 sim/Makefile 的 stage_mem 目标取 FLASH{N}.dat 末 2048 行派生为 flash_win{N}.dat。
#
# 拆分规则 (与 RTL 交错布局一致; 纯 4 路交叉去交织, 整行搬运):
#       实例 sel   = (W>>2) & 3      → 线性行 q 的去向: sel = q & 3
#       实例内行 a = W>>4            → 行号 a = q >> 2
#       半字 lane  = W & 3           → w0 在行内 bit[15:0], w3 在 bit[63:48]
#   同一行四个半字 (W=4q..4q+3) 的 (W>>2)&3 恒等于 q&3 —— 即四个半字必然同属一个
#   实例、同一行, 故 64 位整行原样搬运, **不做半字重排**。
#
# RTL 锚点 (rtl/flashctrl_inf.v, flash_araddr = C28x 字地址 - 0x300000):
#   :59       flash_sel = flash_araddr[19:18]==0            → flash 窗口 = 0x40000 字
#   :174-177  host_arrayN_addr = buffer_araddr[17:4]        → 实例内行 a = W>>4
#   :276      case(buffer_araddr[3:2]) 四选一 direct_data   → 实例 sel = (W>>2)&3
#   :314      case({buffer_araddr[1:0], buffer_arsize})     → 半字 lane = W&3
#   同构旁证: sim/gen_flash_data_hex.py 的 W = 16*i + 4*bank + k。
#   注意: 旧的「2 字母文件 = 两个 64KB 扇区首尾拼接」布局与上述交错不符, 已废弃。
#
# OTP 锚点 (同一模块; araddr = C28x 字地址 = 0x8_0000 + k, k = 窗内字偏移):
#   :60-62    totp_sel = araddr[19:10]==10'h200  (0x8_0000~0x8_03FF, 1024 字)
#             uotp_sel = araddr[19:10]==10'h201  (0x8_0400~0x8_07FF, 1024 字)
#   :174-177  host_arrayN_addr = araddr[17:4]    (0x8_0000 的 bit[17:4] 全 0 → 行号 = k>>4)
#   :276      case(araddr[3:2]) 四选一           → 实例 sel = (k>>2)&3
#   即 otp.dat 行 q 与 FLASH 走同一规则: sel = q&3、实例内行 a = q>>2 (0~127)。
#   模型侧: rtl/flash_bram_half.v otp_mem 为 64 位 ×128 (索引 A[6:0], 擦除游标 0~0x7F),
#   读回时重建 ECC → {4'hF, hi, 4'hF, lo} → 初始化文件须为 16 hex/行 (64 位密文)。
#   注意: nvr_cfg 区 (REGSEL[1]=1) 的密钥屏蔽 A[6] (rtl/flashctrl_array.v:45-55) 只在
#   冗余配置字访问路径生效; 本工具按普通 OTP 窗访问加密 (a = 行号 0~127)。
#
# 加密算法 (与 RTL flashctrl_encrypt.v / tb_uvm.sv enc_ref 一致, KEY=0x5A5A):
#     aw = {a[13:0], sel[1:0]};  scramble {w2,w1,w3,w0}; 奇数位置 ^ aw; 全位 ^ 5A5A
#     逐半字双点修正 (B 方案): 半字为 FFFF 或 z=k^FFFF 时直通, 其余走上述仿射
#     (k = 5A5A 或 5A5A^aw); 64 位全 1 由四个半字固定自然保持。
#   加密地址 a = 实例内行号 (FLASH: 0~16383; OTP: 0~127), sel = 实例号 (= 输出文件名的数字)。
#
# 输入文件永不被改写; 输出为派生物, 可反复重跑 (幂等)。
#
# 用法:
#     python3 encrypt_flash_dat.py [path] [--out-dir D] [--verify] [--no-encrypt] [--selftest]
# 参数:
#     path          FLASH.dat 或 otp.dat 文件, 或包含它们的目录 (目录则递归查找);
#                   默认脚本所在目录 (两个数据集都会被处理)
#     --out-dir     输出目录 (默认与输入同目录)
#     --verify      写完后回读 4 个输出, 解密并重组为线性镜像, 与输入逐行比对
#     --no-encrypt  输出明文 (仅供肉眼核对布局, 不得作为烧写数据)
#     --selftest    已知向量 + 拆分链路自检 (不读输入文件)
#
# 示例:
#     python3 dat/encrypt_flash_dat.py                              # 拆分 FLASH.dat + otp.dat
#     python3 dat/encrypt_flash_dat.py --verify                     # 同上, 加端到端回读校验
#     python3 dat/encrypt_flash_dat.py dat/Memory/otp.dat --verify  # 只处理 OTP
#     python3 dat/encrypt_flash_dat.py /tmp/mem/FLASH.dat --out-dir /tmp/out --verify
#
# Windows 注意 (输出为 ASCII, 编码无关):
#     在 cmd / PowerShell 中运行, 勿双击 (双击无控制台, 输出不可见):
#         python encrypt_flash_dat.py
#         python encrypt_flash_dat.py D:\path\to\FLASH.dat --verify
# ============================================================================

import argparse
import os
import sys

try:    # Python 3.7+: 控制台编码兜底 (Windows GBK/cp1252 下中文输出可能异常)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

KEY = 0x5A5A

N_INST = 4                  # 实例数 (= RTL array0~3 / 加密 sel 取值数)

# 数据集表: 线性镜像 → N_INST 个实例文件 (rows_in 必须是 N_INST 的整数倍)
DATASETS = (
    {
        'name':     'FLASH',
        'in_name':  'FLASH.dat',        # 入口文件名 (精确匹配; FLASH0~3.dat 不会被误当输入)
        'rows_in':  65536,              # 线性镜像行数 (512KB / 64bit = 整片 flash)
        'rows_out': 16384,              # 每实例行数 (S40 模型 14 位地址全量)
        'out_fmt':  'FLASH%d.dat',
    },
    {
        'name':     'OTP',
        'in_name':  'otp.dat',          # OTP 整片线性镜像 (TOTP 窗 + UOTP 窗)
        'rows_in':  512,                # (1024 字 TOTP + 1024 字 UOTP) / 4 字每行
        'rows_out': 128,                # 每实例行数 (行 0~63 = TOTP, 64~127 = UOTP)
        'out_fmt':  'OTP%d.dat',
    },
)
BY_NAME = {s['in_name']: s for s in DATASETS}
for _s in DATASETS:
    assert _s['rows_in'] == _s['rows_out'] * N_INST, _s['name']


def enc_word(din, a, sel):
    """加密单个 64-bit 词 (与 tb_uvm.sv enc_ref / RTL flashctrl_encrypt.v 写通路一致)"""
    aw = ((a & 0x3FFF) << 2) | (sel & 0x3)          # {a[13:0], sel[1:0]} 16 bit
    w0 = (din >> 0) & 0xFFFF
    w1 = (din >> 16) & 0xFFFF
    w2 = (din >> 32) & 0xFFFF
    w3 = (din >> 48) & 0xFFFF
    a5  = KEY ^ 0xFFFF                              # 0xA5A5
    zk  = a5                                        # k = KEY 时的固定点
    zaw = a5 ^ aw                                   # k = KEY ^ aw 时的固定点
    # 逐半字双点修正 (B 方案): {FFFF, z} 直通, 其余走仿射 x ^ k
    s0 = w2 if (w2 == 0xFFFF or w2 == zk)  else (w2 ^ KEY)
    s1 = w1 if (w1 == 0xFFFF or w1 == zaw) else (w1 ^ KEY ^ aw)
    s2 = w3 if (w3 == 0xFFFF or w3 == zk)  else (w3 ^ KEY)
    s3 = w0 if (w0 == 0xFFFF or w0 == zaw) else (w0 ^ KEY ^ aw)
    return (s3 << 48) | (s2 << 32) | (s1 << 16) | s0


def dec_word(din, a, sel):
    """解密单个 64-bit 词 (与 RTL flashctrl_encrypt.v 解密通路一致)"""
    aw = ((a & 0x3FFF) << 2) | (sel & 0x3)
    w0 = (din >> 0) & 0xFFFF
    w1 = (din >> 16) & 0xFFFF
    w2 = (din >> 32) & 0xFFFF
    w3 = (din >> 48) & 0xFFFF
    a5  = KEY ^ 0xFFFF                              # 0xA5A5
    zk  = a5                                        # k = KEY 时的固定点
    zaw = a5 ^ aw                                   # k = KEY ^ aw 时的固定点
    # 解密源映射: out0<-w3, out1<-w1, out2<-w0, out3<-w2
    o0 = w3 if (w3 == 0xFFFF or w3 == zaw) else (w3 ^ KEY ^ aw)
    o1 = w1 if (w1 == 0xFFFF or w1 == zaw) else (w1 ^ KEY ^ aw)
    o2 = w0 if (w0 == 0xFFFF or w0 == zk)  else (w0 ^ KEY)
    o3 = w2 if (w2 == 0xFFFF or w2 == zk)  else (w2 ^ KEY)
    return (o3 << 48) | (o2 << 32) | (o1 << 16) | o0


def deinterleave(rows, n=N_INST):
    """线性行序列 → n 路 (整行搬运, 不重排半字): out[i][j] = rows[i + n*j]"""
    return [rows[i::n] for i in range(n)]


def interleave(inst_rows, n=N_INST):
    """deinterleave 的逆变换 (供 --verify 回读重组): rows[i + n*j] = inst_rows[i][j]"""
    rows = [0] * sum(len(r) for r in inst_rows)
    for i, r in enumerate(inst_rows):
        for j, v in enumerate(r):
            rows[i + n * j] = v
    return rows


def read_rows(path, expect):
    """读 64-bit/行十六进制文件, 返回 (词列表, 行尾); 行数与格式不符即退出"""
    with open(path, 'rb') as f:
        raw = f.read()
    # 检测行尾: 首个换行符前的 \r 决定 CRLF/LF (默认 LF)
    nl = raw.find(b'\n')
    eol = b'\r\n' if (nl > 0 and raw[nl - 1] == 0x0D) else b'\n'

    lines = [ln.strip() for ln in raw.decode('ascii').splitlines()]
    words = [ln for ln in lines if ln]              # 容忍空行 (末尾换行等)
    if len(words) != expect:
        print("ERROR: %s has %d rows, expected %d" % (path, len(words), expect))
        sys.exit(1)

    out = []
    for i, ln in enumerate(words):
        if len(ln) != 16 or not all(c in '0123456789abcdefABCDEF' for c in ln):
            print("ERROR: %s:%d not a 64-bit hex line (%s)" % (path, i + 1, ln))
            sys.exit(1)
        out.append(int(ln, 16))
    return out, eol


def write_tmp(path, words, eol):
    """写临时文件 (原子写的一半), 返回临时文件路径; 调用方决定何时 os.replace"""
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(eol.join(('%016X' % w).encode('ascii') for w in words))
        f.write(eol)
    return tmp


def split_file(src, spec, out_dir=None, verify=False, encrypt=True):
    """线性镜像 → 4 个实例文件: 4 路去交织 + 按实例 sel 加密; 输入文件不改写"""
    rows, eol = read_rows(src, spec['rows_in'])
    inst_rows = deinterleave(rows)

    d = out_dir or os.path.dirname(os.path.abspath(src))
    if not os.path.isdir(d):
        os.makedirs(d)

    paths, tmps = [], []
    for inst, plain in enumerate(inst_rows):
        # 实例内第 a 行 → 加密地址 a, 模式 sel = inst
        data = [enc_word(v, a, inst) for a, v in enumerate(plain)] if encrypt else list(plain)
        p = os.path.join(d, spec['out_fmt'] % inst)
        paths.append(p)
        tmps.append(write_tmp(p, data, eol))        # 4 个 .tmp 全部就绪后才统一替换

    if verify:
        # 端到端: 回读 4 个输出 → 解密 → 重组线性镜像 → 与输入逐行比对
        back = []
        for inst, t in enumerate(tmps):
            words, _ = read_rows(t, spec['rows_out'])
            back.append([dec_word(v, a, inst) for a, v in enumerate(words)] if encrypt
                        else list(words))
        for q, (x, y) in enumerate(zip(rows, interleave(back))):
            if x != y:
                for t in tmps:                      # 校验失败: 清掉 .tmp, 不动已存在的输出
                    try:
                        os.remove(t)
                    except OSError:
                        pass
                print("ERROR: %s roundtrip mismatch at linear row %d: got %016X, want %016X"
                      % (src, q, y, x))
                sys.exit(1)

    for p, t in zip(paths, tmps):
        os.replace(t, p)                            # 原子覆盖

    for inst, p in enumerate(paths):
        print("OK: %s sel=%d rows=%d%s%s" % (os.path.basename(p), inst, spec['rows_out'],
              " (plain)" if not encrypt else "", " (verify OK)" if verify else ""))
    return paths


def find_targets(path):
    """定位输入文件: 具名文件直接用; 目录则递归查找 (默认脚本所在目录)"""
    if path is None:
        path = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(path):
        spec = BY_NAME.get(os.path.basename(path))
        if spec is None:
            print("ERROR: %s is not a known input (expected: %s)"
                  % (path, ' / '.join(s['in_name'] for s in DATASETS)))
            sys.exit(1)
        return [(path, spec)]
    if not os.path.isdir(path):
        print("ERROR: path not found: %s" % path)
        sys.exit(1)
    found = []
    for root, dirs, files in os.walk(path):         # 递归遍历指定目录及其子目录
        for f in files:
            if f in BY_NAME:
                found.append((os.path.join(root, f), BY_NAME[f]))
    return sorted(found, key=lambda t: t[0])


def selftest():
    """已知向量自检 + 拆分链路自检 (不读输入文件)"""
    nfail = 0
    vectors = [
        # (din, a, sel, 期望 64 位密文) — 参考脚本 pack72 后 ECC 剥离
        (0x0000000000000000, 0x3FFE, 3, 0xA5A15A5AA5A15A5A),
        (0x0000000000000000, 0x3FFF, 3, 0xA5A55A5AA5A55A5A),
        # 64 位全1: 四个半字均为固定点 → 直通
        (0xFFFFFFFFFFFFFFFF, 0x0000, 0, 0xFFFFFFFFFFFFFFFF),
        # otp_bank0.dat 首行: 低半字 FFFF 为固定点, 3A48 正常加密
        (0x3A483A48FFFFFFFF, 0x0000, 0, 0xFFFF6012FFFF6012),
        # OTP 段 (含 UOTP 行号 a>=64) — 独立参考脚本 encrypt_otp_dat.py 算出
        (0x123456789ABCDEF0, 0x0040, 1, 0x85AB486EC1E70C22),
        # 高半字 FFFF 为固定点, 低半字全 0 正常加密
        (0xFFFFFFFF00000000, 0x007F, 2, 0x5BA4FFFF5BA4FFFF),
        (0x1AE31AE300000000, 0x0002, 2, 0x5A5040B95A5040B9),
    ]
    for din, a, sel, exp in vectors:
        got = enc_word(din, a, sel)
        if got != exp:
            print("SELFTEST FAIL: enc(%016X, %04X, %d) = %016X, 期望 %016X"
                  % (din, a, sel, got, exp))
            nfail += 1
        else:
            print("SELFTEST PASS: enc(%016X, %04X, %d) = %016X" % (din, a, sel, got))
    # 自反: dec(enc(x)) == x (B 方案为双射; 全1/固定点两侧均直通)
    for x in (0x0000000000000000, 0xFFFFFFFFFFFFFFFF, 0x3A483A48FFFFFFFF,
              0x123456789ABCDEF0, 0x0001000000040004, 0x1B4F1B4F00000000):
        for a in (0x0000, 0x0040, 0x007F, 0x0100, 0x03FE, 0x3FFF):
            for s in (0, 1, 3):
                if dec_word(enc_word(x, a, s), a, s) != x:
                    print("SELFTEST FAIL: 自反破坏 x=%016X a=%04X sel=%d" % (x, a, s))
                    nfail += 1

    # 拆分链路: 每个数据集合成一份线性图样 (标记值 0x1111~0xEEEE, 含全1固定点),
    # 走完整 去交织 → 逐行加密 → 解密 → 重组
    for spec in DATASETS:
        rows = [((q % 15) + 1) * 0x1111111111111111 for q in range(spec['rows_in'])]
        inst_plain = deinterleave(rows)
        inst_enc = [[enc_word(v, a, i) for a, v in enumerate(p)]
                    for i, p in enumerate(inst_plain)]
        back = interleave([[dec_word(v, a, i) for a, v in enumerate(p)]
                           for i, p in enumerate(inst_enc)])
        if back != rows:
            print("SELFTEST FAIL: %s 拆分/还原不一致 (linear roundtrip)" % spec['name'])
            nfail += 1
        elif len(inst_plain[0]) != spec['rows_out']:
            print("SELFTEST FAIL: %s 每实例 %d 行, 期望 %d"
                  % (spec['name'], len(inst_plain[0]), spec['rows_out']))
            nfail += 1
        else:
            print("SELFTEST PASS: %s 拆分/还原 %d 行线性镜像一致 (每实例 %d 行)"
                  % (spec['name'], spec['rows_in'], spec['rows_out']))
        for i in range(N_INST):                     # 整行搬运断言 (防半字重排回归)
            for j in range(spec['rows_out']):
                if inst_plain[i][j] != rows[i + N_INST * j]:
                    print("SELFTEST FAIL: %s 实例 %d 行 %d 未整行搬运" % (spec['name'], i, j))
                    nfail += 1

    if nfail:
        print("SELFTEST TOTAL FAIL = %d" % nfail)
        sys.exit(1)
    print("SELFTEST ALL PASS")


def main():
    ap = argparse.ArgumentParser(description='FLASH / OTP 线性镜像拆分 + 阵列加密 (dat/Memory/)')
    ap.add_argument('path', nargs='?', default=None,
                    help='FLASH.dat 或 otp.dat 文件, 或所在目录 (默认脚本所在目录, 递归查找)')
    ap.add_argument('--out-dir', default=None, help='输出目录 (默认与输入同目录)')
    ap.add_argument('--verify', action='store_true', help='回读 4 个输出, 解密重组后与输入逐行比对')
    ap.add_argument('--no-encrypt', action='store_true', help='输出明文 (仅供核对布局, 勿作烧写数据)')
    ap.add_argument('--selftest', action='store_true', help='已知向量 + 拆分自检 (不读文件)')
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    targets = find_targets(args.path)
    if not targets:
        print("ERROR: %s not found under %s"
              % (' / '.join(s['in_name'] for s in DATASETS),
                 args.path or os.path.dirname(os.path.abspath(__file__))))
        sys.exit(1)

    for src, spec in targets:
        print("Split %s [%s] (sel = q & %d, row = q >> 2):" % (src, spec['name'], N_INST - 1))
        split_file(src, spec, args.out_dir, args.verify, not args.no_encrypt)


if __name__ == '__main__':
    main()
