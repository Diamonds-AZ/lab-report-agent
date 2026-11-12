# 全局规则

- 保留模板原有结构、表格、页眉页脚和编号。
- first_run_test 阶段不填写真实姓名、学号、班级，也不在截图和文件名中使用真实身份信息。
- synthetic execution 下不启动真实桌面软件，统一生成平台风格截图。
- 生成的截图按正常平台画面生成，默认不添加可见 AI、示意图、图号、水印或解释性标记；图片来源只记录在内部 manifest / audit 中。
- 填空题必须优先原位回填：直接替换下划线、空白 run、括号占位或表格空白单元格，不在下一行写“填写：”“应填入：”“答案：”。
- 只有题目明确要求说明、分析、解释原因时，才允许另起段落写说明性内容。
- Word 填空识别必须包含语义填空步骤：先提取 `work/doc_structure.json`，再生成 `work/draft_text_fill_candidates.json`，然后由 Codex/GPT 语义审查生成 `work/refined_text_fill_plan.json`，最后脚本按 refined plan 原位回填；GPT/语义判断只负责规划，不直接修改 Word。
- 低置信度填空不得自动回填；中置信度填空可以回填但必须写入 `work/blank_fill_audit.md` 供用户复核。
- HCL 截图生成前，如果 `assets/references/hcl/` 存在真实 HCL 参考图，必须先生成 `work/reference_analysis.md` 并将界面特征加入图片提示词。
- HCL 参考图只用于窗口比例、菜单栏、工具栏、拓扑画布、设备图标、连接线、命令行窗口、字体和颜色风格，不复制参考图中的具体实验内容、个人信息、文件名、路径或无关命令。
