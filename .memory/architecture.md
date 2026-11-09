# 当前架构

start.vbs -> run.py -> stm_simulator.app.main -> Qt App。
core.py 读取 PARCHG，提供恒高与恒流入口。p4vasp_backend.py 实现 GPL 线性周期搜索。
widgets.py 提供细线箭头下拉框、禁滚轮数值框。
app.py 负责布局、队列化后台任务、二维网格显示及导出。view3d.py 使用 Matplotlib Qt canvas 绘制同步三维曲面/恒高着色平面与原子，保留旋转角度。tests/test_core.py 验证密度读取、插值和周期搜索。
read_parchg 支持 progress 回调，2048行分批解析，进度通过独立队列回到主线程。
依赖安装在项目 .venv。启动失败记录 startup-error.log。
