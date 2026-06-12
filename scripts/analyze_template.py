from pathlib import Path
import json
import re
import sys

from docx import Document
from utils.file_io import read_yaml_text, write_json, write_text


KEYWORDS = {
    "network_hcl": ["HDLC", "PPP", "PAP", "CHAP", "NAT", "ACL", "VLAN", "OSPF", "RIP", "静态路由", "路由器", "交换机", "网络拓扑", "HCL", "华三", "H3C", "ping", "display", "接口配置"],
    "database_datagrip": ["SQL", "数据库", "表", "视图", "索引", "查询", "插入", "删除", "更新", "授权", "GRANT", "REVOKE", "SELECT", "INSERT", "UPDATE", "DELETE", "DataGrip", "MySQL", "权限", "安全性"],
    "java_idea": ["Java", "类", "对象", "线程", "多线程", "继承", "接口", "IDEA", "控制台输出", "main 方法", "SpringBoot"],
    "web_vscode": ["HTML", "CSS", "JavaScript", "Vue", "前端", "浏览器", "页面", "VS Code", "Node.js", "npm", "网页效果"],
}

EXPLICIT_TYPE_PATTERNS = [
    ("network_hcl", [r"本实验应识别为\s*network_hcl", r"平台风格为\s*H3C\s*HCL", r"H3C\s*HCL", r"华三\s*HCL"]),
    ("database_datagrip", [r"本实验应识别为\s*database_datagrip", r"本实验使用\s*DataGrip", r"DataGrip"]),
    ("java_idea", [r"本实验应识别为\s*java_idea", r"本实验平台为\s*IntelliJ\s+IDEA", r"IntelliJ\s+IDEA"]),
    ("web_vscode", [r"本实验应识别为\s*web_vscode", r"本实验在\s*VS\s*Code\s*中完成", r"VS\s*Code"]),
]


def task_experiment_type(workspace: Path):
    task = workspace / "configs" / "task.yaml"
    if not task.exists():
        return None
    for line in read_yaml_text(task).splitlines():
        stripped = line.strip()
        if stripped.startswith("experiment_type:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None


def detect_type(text: str):
    scores = {
        key: sum(1 for kw in kws if kw.lower() in text.lower())
        for key, kws in KEYWORDS.items()
    }
    explicit_type = detect_explicit_type(text)
    if explicit_type:
        scores[explicit_type] = scores.get(explicit_type, 0) + 100
        return explicit_type, scores
    best = max(scores, key=scores.get)
    return best if scores[best] else "unknown", scores


def detect_explicit_type(text: str):
    for exp_type, patterns in EXPLICIT_TYPE_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text, flags=re.I):
                return exp_type
    return None


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    input_path = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "input" / "template.docx"
    if not input_path.is_absolute():
        input_path = workspace / input_path
    output = workspace / "work" / "report_analysis.md"
    output_json = workspace / "work" / "report_analysis.json"

    doc = Document(input_path)
    paragraphs = [p.text for p in doc.paragraphs]
    table_texts = [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    full_text = "\n".join(paragraphs + table_texts)
    detected_type, scores = detect_type(full_text)
    explicit_type = detect_explicit_type(full_text)
    configured_type = task_experiment_type(workspace)
    exp_type = configured_type if configured_type and configured_type != "auto" else detected_type
    if exp_type == "auto" or not exp_type:
        exp_type = detected_type if detected_type != "auto" else "unknown"

    empty_tables = []
    for idx, table in enumerate(doc.tables):
        text = "\n".join(cell.text for row in table.rows for cell in row.cells)
        if not text.strip():
            empty_tables.append(idx)

    identity = any(x in full_text for x in ("姓名", "学号", "班级", "专业"))
    needs_identity_in_images = bool(re.search(r"(截图|水印|主机名|用户名|数据库名|工程名|文件名).*(学号|姓名|班级)", full_text))

    md = [
        "# 模板分析报告",
        "",
        f"- 输入模板：`{input_path}`",
        f"- 段落数：{len(doc.paragraphs)}",
        f"- 表格数：{len(doc.tables)}",
        f"- 配置指定实验类型：`{configured_type or ''}`",
        f"- 自动识别实验类型：`{detected_type}`",
        f"- 显式声明实验类型：`{explicit_type or ''}`",
        f"- 最终实验类型：`{exp_type}`",
        f"- 类型评分：`{json.dumps(scores, ensure_ascii=False)}`",
        f"- 是否存在身份字段：{'是' if identity else '否'}",
        f"- 是否要求截图身份信息：{'是' if needs_identity_in_images else '否'}",
        f"- 空白表格候选图片占位：{empty_tables}",
        "",
        "## 主要结构",
        "",
    ]
    for idx, text in enumerate(paragraphs):
        stripped = text.strip()
        if stripped and (idx < 20 or stripped.startswith(("一、", "二、", "三、", "实验任务"))):
            md.append(f"- P{idx}: {stripped}")

    write_text(output, "\n".join(md) + "\n")
    write_json(
        output_json,
        {
            "input": str(input_path),
            "experiment_type": exp_type,
            "configured_experiment_type": configured_type,
            "detected_experiment_type": detected_type,
            "explicit_experiment_type": explicit_type,
            "scores": scores,
            "empty_tables": empty_tables,
            "has_identity_fields": identity,
            "needs_identity_in_images": needs_identity_in_images,
        },
    )
    print(output)


if __name__ == "__main__":
    main()
