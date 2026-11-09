# STM Simulator

VASP PARCHG 桌面后处理。深色控制面板，恒高切片、恒流等值面、上下表面、搜索范围、可选高斯平滑、鼠标读数与 PNG/CSV/NPZ 导出。

## 运行

```sh
python -m pip install -r requirements.txt
python run.py
```

Windows 双击 `start.vbs` 无控制台启动，失败时查看 `startup-error.log`。

Python 3.10+，需要 PyQt6、NumPy、SciPy。点击“打开文件”载入 PARCHG，设置参数后运行模拟。

## 模型

Tersoff–Hamann 近似，以所选偏压能窗的部分密度作为电流代理。偏压能窗应在 VASP 的 EINT 中指定。程序保留原始 PARCHG 数值，阈值不标定为 pA/nA。读取第一数据块，即共线自旋计算的总密度。文件不保存原始波函数相位。

恒高采用相邻 z 平面线性插值。恒流按选定表面从真空向原子层搜索，采用首次向上跨越阈值的交点，再线性插值。限定真空模式只搜索最外层原子之外的真空。没有交点显示为 NaN/洋红色。阈值过低/高、模型跨周期边界时，请检查或显式指定搜索范围。仅支持 a,b 位于 xy 且正 c 轴沿 z 的晶胞，支持面内非正交网格。默认关闭平滑，sigma 单位为网格间距。

## 来源

恒流线性后端已根据 p4vasp 源码移植，原作者与 GPL 许可见 THIRD_PARTY.md。

- https://github.com/orest-d/p4vasp
- https://vasp.at/wiki/Partial_charge_densities_and_STM_simulations

UI 依据参考项目 experiment/rheed-spot-viewer 分支的 tools/mbe_panel 控制面板样式独立编写，采用中性深灰、蓝色强调、工作区标签、右侧紧凑参数与底部日志。参考 https://github.com/zaxoniu/clc_mbe/tree/experiment/rheed-spot-viewer 。

## 验证

```sh
python -m unittest discover -s tests -v
```


## Qt UI 与 p4vasp 移植

界面改为 PyQt6，移除底部日志，采用参考控制面板的 8px 面板圆角、4px 卡片圆角、10px 标签顶角与中性深灰配色。

默认恒流引擎是 p4vasp 线性移植，保留最低平均密度层起点、周期边界与首次达到阈值规则。无交点用 NaN，未移植三次模式。完整出处与许可证见 THIRD_PARTY.md。限定真空引擎仍可选择。

项目记忆入口见 `.memory/AGENTS.md`，界面约定见 `.memory/designs/ui.md`。

## 双视图与参数

左侧二维图和右侧可旋转三维图由同一次模拟同步更新。三维图可勾选显示原子。恒流模式调整“目标信号 / 原始密度”，恒高模式调整“距外层原子 / Å”，点击“运行模拟”更新两图。恒高三维图使用实际截面高度，密度由颜色表示。三维绘制最多采用120×120采样点，计算和导出保持原始分辨率。

导入时显示密度网格读取进度。原子为文件中的位置，在p4vasp周期展开高度分支附近显示最近的整胞周期副本。原子统一用灰色标记。
