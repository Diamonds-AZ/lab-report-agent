# 05 Long Question Answer Boundary

Purpose: verify that a long task description and a later answer area are separated semantically.

The matching fixture template should contain:

```text
三、实验流程
题目说明：观察硬件结构，如下图所示……
这里是题目/参考材料，不应插入新图。

实验报告模板
一、程序流程图：
二、实验现象：
三、实验结果展示：
```

Expected behavior:

- Blocks before `实验报告模板` are normally `question_area` or `reference_material`.
- Blocks after `实验报告模板` are normally `answer_area`.
- Image/text plans should target answer blocks unless the user explicitly requests editing the earlier question/reference area.
