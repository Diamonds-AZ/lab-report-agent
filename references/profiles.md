# Platform Profiles

## Experiment Type Detection

- `network_hcl`: NAT, ACL, VLAN, OSPF, RIP, static route, router, switch, topology, HCL, H3C, ping, display, Easy IP.
- `database_datagrip`: SQL, database, table, view, index, SELECT, INSERT, UPDATE, DELETE, GRANT, REVOKE, DataGrip, MySQL.
- `java_idea`: Java, class, object, thread, inheritance, interface, IDEA, console, main method, SpringBoot.
- `web_vscode`: HTML, CSS, JavaScript, Vue, frontend, browser, VS Code, Node.js, npm.

If `task.yaml` specifies a non-auto type, use it.

## HCL

Use `configs/profiles/network_hcl.yaml`.

Required:

- H3C HCL / 华三 HCL style.
- Realistic desktop software screenshot.
- HCL-like title bar, top gray toolbar, left dark device palette, light grid topology canvas.
- HCL-style router/switch/PC icons.
- Black H3C console window when CLI output is shown.

Forbidden:

- Huawei eNSP.
- Cisco Packet Tracer.
- Packet Tracer bottom device category bar.
- GNS3.
- Cisco or Huawei logos.

If `assets/references/hcl/` contains images:

1. Analyze them before image prompting.
2. Write `work/reference_analysis.md`.
3. Use only layout/style features.
4. Do not copy project names, paths, desktop shortcuts, personal data, or unrelated commands.
5. If image input is available, pass reference images as style/layout references; otherwise include the analysis in text prompts.

Important: after prompt creation, Codex must call the available image generation tool for each HCL screenshot when `requirements.generate_images=true`. `build_image_prompts.py` only prepares prompt records; it does not generate images.

## DataGrip

Required:

- JetBrains DataGrip English interface.
- Database tree, SQL editor, result grid, console/output.

Forbidden:

- Navicat.
- DBeaver.
- SQLyog.
- MySQL Workbench.

## IntelliJ IDEA

Required:

- IntelliJ IDEA English interface.
- Project tree, Java source editor, Run console.

Forbidden:

- Eclipse.
- NetBeans.

## VS Code

Required:

- VS Code interface.
- Code editor.
- Terminal or browser preview.

Forbidden:

- Unrelated IDEs.
