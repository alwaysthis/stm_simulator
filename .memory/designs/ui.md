# UI 设计

参考 studio 分支 src/ui/theme/constants.py 与 src/ui/components/widgets.py。
深灰 chrome #242424、page #222222、card #1c1c1c、tab strip #303030、field #1e1e1e、edge #303030、accent #4a90d9。
控件和卡片圆角 4px、面板 8px、工作区标签顶部 10px。字体 13px，标签文字 12px。
标签宽为文字宽+16px（最小64px），另留4px间距，高度 max(26,font height+12)。选中填充与页面相同，标签文字位置和颜色保持稳定，悬停为完整圆角块。
下拉箭头为1.6px两段细线。菜单暗底、蓝色选择，禁用滚轮修改。
数值框使用 QDoubleSpinBox，禁用滚轮和即时提交，悬停/焦点蓝色边框。z边界允许留空自动。
页面内边距左右24px、上下10px。没有底部日志。
当前未移植参考应用的整套拖拽、关闭标签和页面凸形描边系统，STM仅有固定两页。
