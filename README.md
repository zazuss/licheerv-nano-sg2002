# LicheeRV Nano (SG2002) 本地资料索引

> 整理日期: 2026-09-22 | 板子已验证可用，当前已关机断开

## 目录结构

```
D:\licheerv-nano\
├── README.md                  ← 本文件
├── docs\                       ← 文档 & Wiki
│   └── sipeed-wiki\            ← Sipeed 官方 Wiki 全量 (1GB)
│       └── docs/hardware/en/lichee/RV_Nano/  ← LicheeRV Nano 专属页面
├── sdks\                       ← SDK & 源码
│   ├── sophon-demo\            ← 算能 SDK 示例 (216MB) - VI/VENC/Audio/IVE/NPU 等
│   └── tpu-mlir\               ← TPU-MLIR 编译器 - 将 ONNX/PyTorch 模型转 cvimodel
├── tools\                      ← 工具
│   └── sophon-tools\           ← 算能开发辅助工具
├── board-sdk\                  ← (待填充) 从板子拉取的 SDK 库 & 示例
│   ├── mnt-system-lib\         ← /mnt/system/usr/lib/ (libcvi_*.so, libsns_*.so 等)
│   ├── mnt-system-bin\         ← /mnt/system/usr/bin/sample_* (46个示例)
│   └── ko\                     ← /mnt/system/ko/ (soph_*.ko 内核模块)
└── opencode-skill\             ← opencode skill (软链)
    └── → C:\Users\15pro\.config\opencode\skills\licheerv-nano-sg2002\SKILL.md
```

## 快速连接（下次直接用）

```powershell
# 1. 插 USB 线，等双网卡出现
# 2. ping 验证
ping 10.233.141.1

# 3. SSH（用 plink 绕过 hostkey 缓存交互）
& "D:\putty\plink.exe" -ssh root@10.233.141.1 -pw root -hostkey "SHA256:WQ3oSDvkXYgOXbCTce3DHumniAemaxooLrf0IS0ss1Y" "uname -a"

# 4. 安全关机
& "D:\putty\plink.exe" -ssh root@10.233.141.1 -pw root -hostkey "SHA256:WQ3oSDvkXYgOXbCTce3DHumniAemaxooLrf0IS0ss1Y" "sync; poweroff"
# 等 ping 不通后再拔线
```

## 关键资源说明

### docs/sipeed-wiki
- LicheeRV Nano 英文介绍: `docs/hardware/en/lichee/RV_Nano/1_intro.html`
- 传感器配置: `docs/hardware/en/lichee/RV_Nano/` 下有 sensor_cfg 等
- 全量 Sipeed 硬件文档

### sdks/sophon-demo
算能官方 SDK 示例，包含：
- `cv180x/` 或 `sg200x/` 目录下的 sample 程序源码
- VI/VO/VPSS/VENC/VDEC 视频管线
- Audio 录音/播放
- IVE 图像处理算法
- NPU 模型推理

### sdks/tpu-mlir
TPU-MLIR 编译器，用于：
- 将 ONNX / PyTorch / TFLite 模型转换为 .cvimodel
- 量化 (int8/int16)
- 板端 libcviruntime.so 推理执行

### tools/sophon-tools
开发辅助工具集

## 待完成

- [ ] 板子开机后用 psftp 拉取 /mnt/system/usr/lib/ 库文件 → board-sdk/mnt-system-lib/
- [ ] 拉取 /mnt/system/usr/bin/sample_* 示例 → board-sdk/mnt-system-bin/
- [ ] 拉取 /mnt/system/ko/ 内核模块 → board-sdk/ko/
- [ ] 下载 SG2002 datasheet (如公开)
- [ ] 下载 CVitek SDK 完整包 (可能在 Sipeed 百度网盘/GitHub)

## 板端关键信息备忘

| 项目 | 值 |
|---|---|
| SoC | SG2002 (C906FDV RISC-V 1GHz + 700MHz 小核 + 1TOPS NPU) |
| 内存 | 256MB DDR3 |
| 系统 | Buildroot 2023.11.2, Linux 5.10.4, riscv64 |
| 主机名 | licheervnano-e98c |
| USB NCM IP | 10.233.141.1 (主机端 .100) |
| RNDIS IP | 10.233.140.1 (主机端 .100) |
| SSH | root / root |
| SD卡 | 59GB (p1=boot vfat 16MB, p2=rootfs ext4 59GB) |
| 预装 NPU 模型 | yolov5s_224_int8, mobilenet_v2_rgb_224_int8, resize_net_3_int8 |
| Python | 3.11.6 |
| OpenCV | 4.8 |
| 驱动状态 | 全部 soph_*.ko 已加载，外设节点齐全，无缺口 |
