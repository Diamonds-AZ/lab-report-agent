from pathlib import Path
from PIL import Image
import sys

from utils.file_io import write_json, write_text


WORKSPACE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
REF_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else WORKSPACE / "assets" / "references" / "hcl"
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else WORKSPACE / "work" / "reference_analysis.md"
if not REF_DIR.is_absolute():
    REF_DIR = WORKSPACE / REF_DIR
if not OUT.is_absolute():
    OUT = WORKSPACE / OUT


def image_info(path: Path) -> str:
    with Image.open(path) as img:
        return f"- `{path.as_posix()}`: {img.width}x{img.height}px, format {img.format}"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    images = []
    if REF_DIR.exists():
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            images.extend(sorted(REF_DIR.glob(ext)))

    if not images:
        write_text(
            OUT,
            "# HCL 参考图分析\n\n未发现 `assets/references/hcl/` 下的 HCL 参考图。后续 HCL 图片只能回退到纯文本 profile，真实度风险较高。\n",
        )
        write_json(WORKSPACE / "work" / "reference_analysis.json", {"platform": "H3C HCL", "reference_images": [], "warning": "no reference images found"})
        print(OUT)
        return

    lines = [
        "# HCL 参考图分析",
        "",
        "## 参考图文件",
        "",
    ]
    lines.extend(image_info(path) for path in images[:5])
    lines.extend(
        [
            "",
            "## 真实 HCL 界面特征",
            "",
            "- 两张参考图都是 HCL 中文界面，不是通用网络模拟器界面。",
            "- 主窗口顶部标题栏显示类似 `HCL - hcl_xxx[临时工程]`，窗口整体为浅灰色 Windows 桌面软件。",
            "- 顶部工具栏是一排小而密集的灰色图标，包含文件、保存、启动/停止、缩放、相机、扳手、设置、CMD、帮助等按钮。",
            "- 左侧是深色竖向设备分类栏，顶部有彩色 HCL 云形 logo，下方是 DIY、路由器、交换机、无线、服务器、终端、线缆等灰色分类图标。",
            "- 拓扑参考图的主区域是大面积白色细网格画布，上方中文标签为 `设计`、`概要`、`配置`、`文件`。",
            "- 拓扑参考图右侧有浅灰面板，上半部分标题为 `抓包接口列表`，包含 `设备名`、`接口`；下半部分标题为 `拓扑汇总`，用红点列出设备。",
            "- 拓扑参考图只有设备垂直摆放，没有连线：上方深灰路由器图标 `MSR36-20_1`，中间深灰交换机图标 `S5820V2-54QS-GE_2`，下方蓝色 PC 图标 `PC_3`。",
            "- 设备名称是亮蓝色文字，位于设备图标下方或附近。",
            "- 控制台参考图中，黑底 H3C 终端窗口占据画面绝大部分，顶部有设备标签 `MSR36-20_1`，正文为大号白色等宽字体。",
            "- 控制台文本包含 H3C 启动信息、`Cryptographic algorithms tests passed.`、`Press ENTER to get started.` 和 `<H3C>` 提示符。",
            "- 控制台图左侧仍露出 HCL 深色设备栏，顶部仍露出灰色工具栏，底部状态栏显示版权和 `HCL v5.10.3`。",
            "",
            "## 生成提示词必须强调",
            "",
            "- Match the two HCL reference screenshots for Chinese HCL window layout, left dark device palette, top gray toolbar, white grid canvas, blue device labels, right Chinese summary panels, and black H3C console style.",
            "- Use HCL-specific visual structure, not Cisco Packet Tracer, Huawei eNSP, GNS3, or a generic network simulator UI.",
            "- Do not force green links unless the task explicitly needs links; the topology reference image has no links.",
            "- For topology screenshots, prefer the reference layout: no console window unless needed, three vertically arranged devices, right-side `抓包接口列表` and `拓扑汇总` panels.",
            "- For console screenshots, prefer the reference layout: very large black H3C console window over the HCL main window, white monospace boot/configuration text and `<H3C>` prompt.",
            "- Reference images are style-only. Do not copy project names, file paths, desktop shortcuts, VirtualBox text, unrelated commands, personal information, or watermark text.",
        ]
    )
    write_text(OUT, "\n".join(lines) + "\n")
    write_json(
        WORKSPACE / "work" / "reference_analysis.json",
        {
            "platform": "H3C HCL",
            "reference_images": [path.as_posix() for path in images[:5]],
            "reference_usage": "style_only; pass these image paths as visual references when the image generation backend supports image inputs",
            "window_layout": [
                "Chinese HCL desktop application window, light gray Windows-style chrome",
                "title bar like HCL - hcl_xxx[临时工程]",
                "bottom status bar with copyright and HCL v5.10.3",
            ],
            "toolbar_style": [
                "dense top gray toolbar with small file/save/start/stop/zoom/camera/tools/settings/CMD/help icons",
                "left dark vertical device palette with colorful HCL cloud logo and gray category icons",
            ],
            "topology_canvas_style": [
                "large white fine-grid topology canvas with Chinese tabs 设计/概要/配置/文件",
                "right-side Chinese panels 抓包接口列表 and 拓扑汇总",
                "reference topology has three vertically arranged devices and no links",
            ],
            "device_icon_style": [
                "flat dark gray router/switch icons with white network symbols",
                "blue PC monitor icons",
                "bright blue device labels such as MSR36-20_1",
            ],
            "cli_window_style": [
                "very large black H3C console window occupying most of the HCL main window",
                "device tab like MSR36-20_1, white monospace boot/config text, prompts like <H3C>",
            ],
            "forbidden_copy_content": [
                "project names",
                "file paths",
                "desktop shortcuts",
                "VirtualBox labels",
                "unrelated commands",
                "personal information",
                "student name or ID",
                "watermarks",
            ],
        },
    )
    print(OUT)


if __name__ == "__main__":
    main()
