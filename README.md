# STM Simulator

VASP PARCHG 桌面后处理。深色控制面板，恒高切片、恒流等值面、上下表面、搜索范围、可选高斯平滑、鼠标读数与 PNG/CSV/NPZ 导出。

## 运行

```sh
python -m pip install -r requirements.txt
python run.py
```

Windows 双击 `start.vbs` 无控制台启动，失败时查看 `startup-error.log`。

Python 3.10+，需要 tkinter（Windows 官方 Python 自带）。先点击“载入演示”验证界面，再打开 PARCHG。

## 模型

Tersoff–Hamann 近似，以所选偏压能窗的部分密度作为电流代理。偏压能窗应在 VASP 的 EINT 中指定。程序保留原始 PARCHG 数值，阈值不标定为 pA/nA。读取第一数据块，即共线自旋计算的总密度。文件不保存原始波函数相位。

恒高采用相邻 z 平面线性插值。恒流按选定表面从真空向原子层搜索，采用首次向上跨越阈值的交点，再线性插值。默认只搜索最外层原子之外的真空。没有交点显示为 NaN/洋红色。阈值过低/高、模型跨周期边界时，请检查或显式指定搜索范围。仅支持 a,b 位于 xy 且正 c 轴沿 z 的晶胞，支持面内非正交网格。默认关闭平滑，sigma 单位为网格间距。

## 来源

参考 p4vasp 的恒高切片/恒流等值面流程及 VASP 官方方法说明，本项目当前为独立实现，未复制 p4vasp 源码。

- https://github.com/orest-d/p4vasp
- https://vasp.at/wiki/Partial_charge_densities_and_STM_simulations

UI 依据参考项目 experiment/rheed-spot-viewer 分支的 tools/mbe_panel 控制面板样式独立编写，采用中性深灰、蓝色强调、工作区标签、右侧紧凑参数与底部日志。参考 https://github.com/zaxoniu/clc_mbe/tree/experiment/rheed-spot-viewer 。

## 验证

```sh
python -m unittest discover -s tests -v
```
