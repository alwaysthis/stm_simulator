# 当前架构

start.vbs -> run.py -> stm_simulator.app.main -> Qt App。
core.py 读取 PARCHG，提供恒高与恒流入口。p4vasp_backend.py 实现 GPL 线性周期搜索。
widgets.py 提供细线箭头下拉框、禁滚轮数值框、自绘紧凑工作区标签。
app.py 负责布局、队列化后台任务、二维网格显示及导出。tests/test_core.py 验证密度读取、插值和周期搜索。
依赖安装在项目 .venv。启动失败记录 startup-error.log。
