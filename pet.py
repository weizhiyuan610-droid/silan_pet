#!/usr/bin/env python3
"""
Desktop Pet - 桌面猫咪宠物
一个可爱的桌面宠物，提醒你按时休息和吃饭
"""

import sys
import os
import math
from datetime import datetime, time
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QPixmap, QFont, QAction

# macOS API imports for window snapping
try:
    from AppKit import NSWorkspace, NSRunningApplication
    from Quartz import CGWindowListCopyWindowInfo, kCGNullWindowID, kCGWindowListOptionOnScreenOnly
    MACOS_AVAILABLE = True
except ImportError:
    MACOS_AVAILABLE = False
    print("⚠️  macOS API 不可用，窗口吸附功能将被禁用")


def get_resource_path(relative_path):
    """
    获取资源文件的绝对路径
    支持 PyInstaller 打包后的路径 (_MEIPASS)
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发环境：当前目录
    return os.path.join(os.path.abspath("."), relative_path)


class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()

        # 初始配置
        self.normal_size = 200  # 正常大小（像素，宽度）
        self.min_height = 150  # 最低高度
        self.large_size_ratio = 0.6  # 提醒时占屏幕高度的比例

        # 原始位置和大小
        self.original_pos = None
        self.original_size = None

        # 鼠标拖拽相关
        self.is_dragging = False
        self.drag_start_pos = QPoint()

        # 提醒状态
        self.is_reminding = False

        # 窗口吸附相关
        self.snapping_enabled = True  # 是否启用吸附
        self.current_app_pid = None  # 当前吸附的应用进程ID
        self.last_window_pos = None  # 上次窗口位置，用于失败时回退
        self.is_user_dragging = False  # 用户是否正在拖拽
        self.current_pos = None  # 当前动画位置
        self.target_pos = None  # 目标位置
        self.animation_timer = None  # 平滑过渡动画定时器

        # 图片标签
        self.image_label = None

        # 文字标签
        self.text_label = None

        # 初始化界面
        self.init_ui()

        # 加载猫咪图片
        self.load_cat_image()

        # 初始化呼吸动画
        self.init_breathing_animation()

        # 初始化窗口吸附
        self.init_window_snapping()

        # 初始化定时器
        self.init_timers()

    def init_ui(self):
        """初始化用户界面"""

        # 设置窗口属性 - 透明、无边框、置顶
        # 注意：不使用 Tool 标志，因为它会导致窗口在某些情况下自动隐藏
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |  # 无边框
            Qt.WindowType.WindowStaysOnTopHint  # 置顶
        )

        # 设置窗口背景透明
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 创建布局（清除边距）
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # 创建图片标签
        self.image_label = QLabel(self)
        self.image_label.setScaledContents(True)  # 自适应缩放，填充整个标签
        layout.addWidget(self.image_label)

        # 创建文字标签（用于显示提醒）
        self.text_label = QLabel("", self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("color: white; font-weight: bold; background-color: rgba(0, 0, 0, 100); padding: 10px; border-radius: 5px;")
        self.text_label.setVisible(False)
        layout.addWidget(self.text_label)

        # 设置初始大小（稍后在加载图片后会根据图片比例调整）
        self.setFixedSize(self.normal_size, self.normal_size)

        # 计算屏幕中心位置
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # 暂时移动到屏幕中央（加载图片后会重新计算）
        x = (screen_width - self.normal_size) // 2
        y = (screen_height - self.normal_size) // 2
        self.move(x, y)

        # 保存原始位置和大小
        self.original_pos = self.pos()
        self.original_size = self.size()

        # 显示窗口
        self.show()
        self.raise_()  # 确保窗口在最前面
        self.activateWindow()  # 激活窗口

        print("✓ 窗口初始化完成")
        print(f"  - 位置: ({self.x()}, {self.y()})")
        print(f"  - 大小: {self.width()}x{self.height()}")
        print(f"  - 是否可见: {self.isVisible()}")

    def load_cat_image(self):
        """加载猫咪图片并显示到 QLabel"""

        # 获取图片资源路径
        image_path = get_resource_path("silan.png")

        # 检查文件是否存在
        if not os.path.exists(image_path):
            print("❌ 错误：找不到 silan.png 文件")
            print(f"   查找路径: {image_path}")
            print(f"   当前工作目录: {os.getcwd()}")
            print("   请确保 silan.png 与 pet.py 在同一目录下")
            print("\n程序无法启动，请准备好 silan.png 图片文件后重试。")
            sys.exit(1)  # 直接退出程序

        # 读取图片
        pixmap = QPixmap(image_path)

        if pixmap.isNull():
            print("❌ 错误：silan.png 加载失败")
            print("   文件可能损坏或不是有效的图片格式")
            print("   请确保 silan.png 是有效的 PNG/JPG 图片")
            print("\n程序无法启动，请修复图片文件后重试。")
            sys.exit(1)  # 直接退出程序

        print("✓ silan.png 加载成功")
        print(f"   图片原始尺寸: {pixmap.width()}x{pixmap.height()}")

        # 计算窗口尺寸
        # 宽度固定为 200，高度根据图片比例计算
        target_width = 200
        target_height = int(200 * pixmap.height() / pixmap.width())

        # 确保最低高度为 150
        if target_height < 150:
            target_height = 150
            print(f"   ⚠️  高度低于最低值，已调整为 150px")

        print(f"✓ 目标窗口尺寸: {target_width}x{target_height}")

        # 直接设置窗口和标签大小
        self.setFixedSize(target_width, target_height)
        self.image_label.setFixedSize(target_width, target_height)

        # 直接将原始图片设置到 QLabel
        # QLabel 会自动缩放以填充整个标签（因为设置了 setScaledContents(True)）
        self.image_label.setPixmap(pixmap)

        # 重新计算屏幕中心位置
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # 移动到屏幕正中央
        center_x = (screen_width - target_width) // 2
        center_y = (screen_height - target_height) // 2
        self.move(center_x, center_y)
        self.original_pos = self.pos()

        # 更新原始大小记录
        self.original_size = self.size()

        print(f"✓ 图片已显示")
        print(f"   窗口尺寸: {self.width()}x{self.height()}")
        print(f"   窗口位置: ({self.x()}, {self.y()})")
        print(f"   屏幕中心: ({screen_width//2}, {screen_height//2})")
        print(f"   透明背景: {'支持' if pixmap.hasAlpha() else '不透明'}")

        # 确保窗口在最前面
        self.raise_()
        self.activateWindow()

    def init_breathing_animation(self):
        """初始化呼吸动画"""
        # 保存原始尺寸
        self.base_width = self.width()
        self.base_height = self.height()

        # 创建呼吸动画定时器（约 60fps）
        self.breathing_timer = QTimer()
        self.breathing_timer.timeout.connect(self.update_breathing)
        self.breathing_timer.start(16)  # 16ms ≈ 60fps

        # 呼吸动画参数
        self.breathing_time = 0  # 当前时间
        self.breathing_period = 3000  # 呼吸周期（毫秒）
        self.breathing_min_scale = 1.00  # 最小缩放（100%）
        self.breathing_max_scale = 1.03  # 最大缩放（103%）

        print("✓ 呼吸动画已启动（周期: 3秒，幅度: 100%-103%）")

    def update_breathing(self):
        """更新呼吸动画帧"""
        # 计算当前在呼吸周期中的位置（0 到 2π）
        progress = (self.breathing_time % self.breathing_period) / self.breathing_period
        angle = progress * 2 * math.pi

        # 使用正弦波计算缩放因子（-1 到 1）
        sine_value = math.sin(angle)

        # 将正弦值映射到缩放范围（100% 到 103%）
        scale = self.breathing_min_scale + (sine_value + 1) / 2 * (self.breathing_max_scale - self.breathing_min_scale)

        # 计算新的尺寸（保持中心点不变）
        new_width = int(self.base_width * scale)
        new_height = int(self.base_height * scale)

        # 调整标签大小和位置（保持居中）
        offset_x = (new_width - self.base_width) // 2
        offset_y = (new_height - self.base_height) // 2

        self.image_label.setGeometry(-offset_x, -offset_y, new_width, new_height)

        # 更新时间
        self.breathing_time += 16  # 每次增加 16ms

    def init_window_snapping(self):
        """初始化窗口吸附功能"""
        if not MACOS_AVAILABLE:
            print("⚠️  窗口吸附功能不可用（需要 macOS）")
            return

        # 创建窗口检测定时器（100ms 检测一次）
        self.snapping_timer = QTimer()
        self.snapping_timer.timeout.connect(self.update_window_snapping)
        self.snapping_timer.start(100)  # 100ms

        print("✓ 窗口吸附功能已启动（检测间隔: 100ms）")

    def update_window_snapping(self):
        """更新窗口吸附位置"""
        # 如果用户正在拖拽或正在提醒，暂时禁用吸附
        if self.is_user_dragging or self.is_reminding:
            return

        try:
            # 获取当前活动的应用
            workspace = NSWorkspace.sharedWorkspace()
            active_app = workspace.frontmostApplication()

            if not active_app:
                return

            app_pid = active_app.processIdentifier()
            app_name = active_app.localizedName()

            # 排除 Finder 和自己
            if app_name in ['Finder', 'Desktop Pet', 'Python', 'Terminal']:
                return

            # 如果切换了应用，更新当前应用 PID
            if self.current_app_pid != app_pid:
                self.current_app_pid = app_pid
                print(f"✓ 切换到应用: {app_name} (PID: {app_pid})")

            # 获取该应用的窗口信息（过滤阴影）
            window_info = self.get_active_window_info(app_pid)

            if not window_info:
                return

            # 计算猫咪应该在的位置（窗口右上角，趴在窗口上）
            window_x = window_info['x']
            window_y = window_info['y']
            window_width = window_info['width']
            window_height = window_info['height']

            # macOS 的坐标系：原点在屏幕左下角，Y 轴向上为正
            # PyQt6 的坐标系：原点在屏幕左上角，Y 轴向下为正
            screen = QApplication.primaryScreen()
            screen_geometry = screen.geometry()
            screen_height = screen_geometry.height()

            # 窗口在 PyQt6 坐标系中的位置
            window_top_qt = screen_height - (window_y + window_height)

            # 猫咪尺寸
            pet_width = self.width()
            pet_height = self.height()

            # 智能标题栏高度检测
            titlebar_height = self.detect_titlebar_height(app_name, window_width, window_height)

            # 计算宠物位置（外挂模式）
            # X 轴：宠物左边缘紧贴窗口右边缘，完全不重叠
            pet_x = window_x + window_width

            # Y 轴：让角色的手部（在图片高度的 40% 处）刚好抓在窗口顶栏上
            # 手部位置 = pet_y + pet_height * 0.4
            # 我们希望手部位置 = window_top_qt
            # 所以：pet_y = window_top_qt - pet_height * 0.4
            pet_y = window_top_qt - int(pet_height * 0.4)

            # 平滑移动到新位置
            self.smooth_move_to(pet_x, pet_y)

            # 更新原始位置（用于恢复）
            self.original_pos = self.pos()

            # 保存最后成功的窗口位置
            self.last_window_pos = (pet_x, pet_y)

        except Exception as e:
            # 获取失败时，保持在上次成功位置
            if self.last_window_pos:
                pass  # 静默失败，保持当前位置
            # 不打印错误，避免刷屏

    def detect_titlebar_height(self, app_name, window_width, window_height):
        """智能检测应用标题栏高度"""
        # 标准 macOS 标题栏高度约为 28 像素
        standard_titlebar = 28

        # 某些应用可能有特殊的标题栏高度
        if app_name in ['Chrome', 'Safari', 'Firefox', 'Edge']:
            # 浏览器通常有标准标题栏
            return standard_titlebar
        elif app_name in ['Terminal', 'iTerm2']:
            # 终端应用标题栏可能稍高
            return standard_titlebar
        elif app_name in ['Visual Studio Code', 'Sublime Text', 'Atom']:
            # 编辑器可能有标签栏
            return standard_titlebar + 5
        elif app_name in ['人人视频', '腾讯视频', '爱奇艺', '优酷']:
            # 视频应用可能没有标准标题栏或使用自定义 UI
            # 检查是否为全屏或接近全屏
            screen = QApplication.primaryScreen()
            screen_geometry = screen.geometry()
            if window_width > screen_geometry.width() * 0.9:
                return 0  # 全屏模式，无标题栏
            return standard_titlebar
        else:
            # 默认使用标准标题栏高度
            return standard_titlebar

    def smooth_move_to(self, target_x, target_y):
        """平滑移动到目标位置"""
        # 如果是第一次移动或位置变化很小，直接移动
        current_x, current_y = self.x(), self.y()

        # 计算距离
        distance = ((target_x - current_x) ** 2 + (target_y - current_y) ** 2) ** 0.5

        # 如果距离很小（小于 20px），直接移动
        if distance < 20:
            self.move(target_x, target_y)
            return

        # 如果距离较大，启动平滑动画
        self.current_pos = (current_x, current_y)
        self.target_pos = (target_x, target_y)

        # 如果动画定时器不存在，创建并启动
        if self.animation_timer is None or not self.animation_timer.isActive():
            self.animation_steps = 10  # 动画分 10 步完成
            self.animation_step = 0

            if self.animation_timer is None:
                self.animation_timer = QTimer()
                self.animation_timer.timeout.connect(self.animate_move)

            self.animation_timer.start(16)  # 16ms per step

    def animate_move(self):
        """执行平滑移动动画"""
        if self.current_pos is None or self.target_pos is None:
            self.animation_timer.stop()
            return

        start_x, start_y = self.current_pos
        target_x, target_y = self.target_pos

        # 计算当前步
        self.animation_step += 1

        # 使用缓动函数（ease-out）
        progress = self.animation_step / self.animation_steps
        eased_progress = 1 - (1 - progress) ** 2  # ease-out quad

        # 计算当前位置
        current_x = int(start_x + (target_x - start_x) * eased_progress)
        current_y = int(start_y + (target_y - start_y) * eased_progress)

        # 移动到当前位置
        self.move(current_x, current_y)

        # 检查是否完成
        if self.animation_step >= self.animation_steps:
            self.animation_timer.stop()
            # 确保最终位置精确
            self.move(target_x, target_y)

    def get_active_window_info(self, app_pid):
        """获取指定应用的活跃窗口信息，过滤阴影"""
        try:
            # 获取所有窗口信息
            window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)

            # 查找属于该应用的主窗口（layer = 0，最顶层）
            main_window = None
            max_area = 0

            for window_dict in window_list:
                window_pid = window_dict.get('kCGWindowOwnerPID', 0)
                window_layer = window_dict.get('kCGWindowLayer', 0)
                window_bounds = window_dict.get('kCGWindowBounds', None)
                window_alpha = window_dict.get('kCGWindowAlpha', 1.0)  # 透明度

                # 过滤条件：
                # 1. PID 匹配
                # 2. 最顶层窗口（layer = 0）
                # 3. 有窗口边界
                # 4. 不完全透明（alpha > 0.1）
                # 5. 窗口可见（宽度和高度都大于 50）
                if (window_pid == app_pid and
                    window_layer == 0 and
                    window_bounds and
                    window_alpha > 0.1):

                    width = int(window_bounds['Width'])
                    height = int(window_bounds['Height'])

                    # 过滤掉太小的窗口（可能是菜单、工具栏等）
                    if width > 50 and height > 50:
                        area = width * height

                        # 选择面积最大的窗口（主窗口）
                        if area > max_area:
                            max_area = area
                            main_window = {
                                'x': int(window_bounds['X']),
                                'y': int(window_bounds['Y']),
                                'width': width,
                                'height': height
                            }

            return main_window

        except Exception as e:
            return None

    def init_timers(self):
        """初始化所有定时器"""

        # 久坐提醒定时器（45分钟 = 2700000毫秒）
        self.sedentary_timer = QTimer()
        self.sedentary_timer.timeout.connect(self.show_sedentary_reminder)
        self.sedentary_timer.start(45 * 60 * 1000)  # 45分钟

        # 提醒持续时间定时器（30秒）
        self.reminder_duration_timer = QTimer()
        self.reminder_duration_timer.setSingleShot(True)
        self.reminder_duration_timer.timeout.connect(self.hide_reminder)

        # 吃饭提醒检查定时器（每分钟检查一次）
        self.meal_check_timer = QTimer()
        self.meal_check_timer.timeout.connect(self.check_meal_time)
        self.meal_check_timer.start(60000)  # 每分钟检查一次

    def show_sedentary_reminder(self):
        """显示久坐提醒"""
        self.reminder_text = "该起身动动啦"
        self.show_reminder()

    def check_meal_time(self):
        """检查是否到了吃饭时间"""
        now = datetime.now().time()

        # 定义吃饭时间
        meal_times = [
            time(8, 30),   # 早餐
            time(12, 0),   # 午餐
            time(18, 30)   # 晚餐
        ]

        # 检查当前时间是否接近吃饭时间（在那一分钟内）
        for meal_time in meal_times:
            if (now.hour == meal_time.hour and now.minute == meal_time.minute):
                self.reminder_text = "陪我一起吃饭吧"
                self.show_reminder()
                break

    def show_reminder(self):
        """显示提醒（放大猫咪并显示文字）"""
        if self.is_reminding:
            return

        self.is_reminding = True

        # 保存当前位置
        self.original_pos = self.pos()

        # 获取屏幕尺寸
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        # 计算放大后的大小（屏幕高度的60%）
        large_size = int(screen_geometry.height() * self.large_size_ratio)

        # 设置新大小
        self.setFixedSize(large_size, large_size + 100)  # 增加高度给文字标签

        # 移动到屏幕中央
        x = (screen_geometry.width() - large_size) // 2
        y = (screen_geometry.height() - large_size - 100) // 2
        self.move(x, y)

        # 显示提醒文字
        self.text_label.setText(self.reminder_text)
        self.text_label.setVisible(True)

        # 设置字体大小
        font = QFont("Arial", 32, QFont.Weight.Bold)
        self.text_label.setFont(font)

        print(f"✓ 显示提醒: {self.reminder_text}")

        # 30秒后恢复
        self.reminder_duration_timer.start(30000)

    def hide_reminder(self):
        """隐藏提醒（恢复到原始大小和位置）"""
        if not self.is_reminding:
            return

        self.is_reminding = False

        # 恢复原始大小
        self.setFixedSize(self.normal_size, self.normal_size)

        # 恢复到原始位置
        if self.original_pos:
            self.move(self.original_pos)

        # 隐藏提醒文字
        self.text_label.setVisible(False)

        print("✓ 提醒已结束，恢复原始状态")

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.is_user_dragging = True  # 标记用户正在拖拽，禁用吸附
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """鼠标移动事件（拖拽）"""
        if self.is_dragging:
            # 移动窗口
            new_pos = event.globalPosition().toPoint() - self.drag_start_pos
            self.move(new_pos)

            # 更新原始位置，以便恢复时使用
            self.original_pos = new_pos

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            # 延迟一段时间后重新启用吸附（给用户时间放手）
            QTimer.singleShot(500, lambda: setattr(self, 'is_user_dragging', False))

    def contextMenuEvent(self, event):
        """右键菜单事件"""
        menu = QMenu(self)

        # 创建"退出"动作
        quit_action = QAction("退出 (Quit)", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(quit_action)

        # 在鼠标位置显示菜单
        menu.exec(event.globalPos())

    def quit_application(self):
        """退出应用程序"""
        print("👋 正在退出桌面宠物...")
        sys.exit(0)

    def closeEvent(self, event):
        """窗口关闭事件 - 防止意外关闭"""
        print("⚠️  窗口尝试关闭，已忽略")
        print("💡 提示：使用 Ctrl+C 或关闭终端来退出程序")
        event.ignore()  # 忽略关闭事件


def main():
    print("=" * 50)
    print("🐱 桌面猫咪宠物启动中...")
    print("=" * 50)

    # 创建应用程序实例
    app = QApplication(sys.argv)

    # 重要：防止窗口关闭时程序退出
    app.setQuitOnLastWindowClosed(False)

    # macOS 特定设置
    if sys.platform == "darwin":
        # 设置应用程序名称
        app.setApplicationName("Desktop Pet")

    # 创建并显示桌面宠物
    # 注意：将 pet 赋值给全局变量，防止被垃圾回收
    global pet
    pet = DesktopPet()

    print("=" * 50)
    print("✓ 程序已启动，猫咪窗口应该可见")
    print("✓ 按 Ctrl+C 退出程序")
    print("=" * 50)

    # 运行应用程序事件循环
    # 这会阻塞主线程，保持程序运行
    exit_code = app.exec()

    print(f"\n程序已退出，退出码: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
