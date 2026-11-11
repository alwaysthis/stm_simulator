# 当前架构

start.vbs -> run.py -> stm_simulator.app.main -> Qt App。
core.py 读取 PARCHG，提供恒高与恒流入口。p4vasp_backend.py 实现 GPL 线性周期搜索。
widgets.py 提供细线箭头下拉框、禁滚轮数值框。
app.py 负责布局、队列化后台任务、二维网格显示及导出。view3d.py 使用 PyQtGraph OpenGL 绘制同步三维曲面/恒高着色平面与原子，Qt叠层绘制轴标，保留相机视角。tests/test_core.py 验证密度读取、插值和周期搜索。
read_parchg 支持 progress 回调，2048行分批解析，进度通过独立队列回到主线程。
依赖安装在项目 .venv。启动失败记录 startup-error.log。

.settings.ini (QSettings IniFormat) 记忆最近成功文件和打开目录，启动自动恢复。恒流/恒高滑条250ms防抖更新双图，忙碌时延后。native_backend.py 用ctypes调用native/stm_native.cpp，build_native.py通过MinGW g++编译静态运行库链接的DLL，DLL缺失时自动回退NumPy。

colors.py 统一二维/三维/色条的线性RGBA映射、配色、数值范围及相对高度标注。曲面和原子采用实际笛卡尔Å坐标，三维网格最多160×160，单一相机等比例变换。PNG导出使用图像控件快照包含色条。

Volume.elements为按原子顺序展开的元素元组，旧调用默认空元组兼容。VASP4计数格式保留X1/X2类型分组。elements.py读取element_styles.json，来自crystalX的VESTA主题。GLScatterPlotItem采用逐原子颜色和世界坐标显示直径2r，Qt标签叠层显示元素名，开关与原子可见性独立。

app.ImageView保留物理xy坐标截面线并发出信号；App.update_profile用晶格逆矩阵转换坐标，scipy.ndimage.map_coordinates进行周期双线性采样，最多4096点，横轴实际Å距离、纵轴共用ColorScale单位转换，NaN和晶胞外空白保留断点。底部曲线使用PyQtGraph。plot_tools.HoverActions封装悬浮工具栏与无工具栏截图，Windows剪贴板使用独立RGB32图像。SurfaceView保存初始相机供重置。
