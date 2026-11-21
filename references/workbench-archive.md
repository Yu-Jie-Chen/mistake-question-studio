# 自动归档到文源教学工作台

成品检查通过后，Agent 调用本技能的 `scripts/archive_to_workbench.py`，将文件和结构化内容归到对应学生。用户只要求本地文件、不归档时跳过；不要给家长发消息或公开上传。归档不是 GitHub 推送。

## 本机连接（一次配置）

工作台需要运行包含统一归档接口的版本。客户端只使用 Python 标准库，只连接本机 HTTP，不发送到公网。
在用户主目录创建 `.wenyuan-workbench.json`（不要提交仓库）：

```json
{"url":"http://127.0.0.1:8765","workbench_root":"/本机教学工作台源码目录"}
```

安装版可用 `token_file` 指向其数据目录的 `.local-session-token`。也可使用 `WENYUAN_WORKBENCH_URL`、`WENYUAN_WORKBENCH_ROOT`、`WENYUAN_WORKBENCH_TOKEN_FILE`，或同名命令行参数（小写短横线）。`WENYUAN_ARCHIVE_CONFIG` 可指定配置文件。令牌只从本机文件读入请求头，不打印、不写入归档清单。

## 学生匹配

```sh
python scripts/archive_to_workbench.py --students
```

使用工作台已有的 `student_id` 最稳妥。没有 ID 时，只允许精确匹配唯一的未结业姓名；有重名、姓名冲突、学生未建档时停止归档，请用户确认或先建档，不模糊匹配、不擅自新建学生。不要把学号 `studentId` 当工作台 ID。年级使用工作台档案，学科使用本次成果。

## 本技能命令

有公式时先按 [公式展示检查](formula-display.md) 完成严格构建；能访问同版本工作台检查器时也执行兼容性预检。教学资料优先附自包含 `card.html`；不要单独上传依赖相对 `formulas/`、`figures/` 路径的 `card.md`。HTML 预览可能禁用 JavaScript，公式须已嵌入图片或静态 MathML。

```sh
python scripts/archive_to_workbench.py --type mistake-question --input /工作目录/text/question.json --file /工作目录/card.html --manifest /工作目录/result.archive.json
```

`--file` 可重复传入多个已检查的成品。反馈的 `--type feedback` 会根据 report.json 的 report_type 自动选择试听/诊断；省略 report_type 默认试听。学情诊断反馈可加 `--report-id`，必须是同一学生的已有诊断报告 ID；单独的试听或诊断反馈无需 report_id。
试卷分析导入 draft.json 并保存为草稿，成品附件关联新建诊断；错题导入题干、答案、解析、题图与学生错因，新增题目为待审草稿，同题也会关联到当前学生。不会自动发布、签核或认定已掌握。

## 回执与失败处理

每次新成果使用新的 `*.archive.json` 路径；脚本生成稳定 artifact_id，先保存包含文件内容的本地清单，再提交。网络中断、工作台未启动、认证失败时，成品保留、退出码为 2，并写明待归档，不能声称成功。修复连接后最多自动重试一次：

```sh
python scripts/archive_to_workbench.py --retry /输出目录/result.archive.json
```

姓名歧义尚未归档时，确认学生后用 `--retry /输出目录/result.archive.json --student-id 已确认ID` 补充选择；已成功归档的成果不能改挂其他学生。

原样重试返回同一归档记录，不重复文件、不累加错题次数。内容修改后是新版本，用新清单和新编号，不修改旧清单绕过冲突。清单、回执包含学生资料，只存本地；已加 gitignore。
成功回执 `*.archive.receipt.json` 含 student_id、material_ids、report_id 或 question_id。只有 ok=true 才告诉用户“已归档到某同学”；刷新工作台后，在学生档案的专属资料、学情诊断、错题本查看。题目默认在待审视图。

`ok=true` 只确认存储成功。打开回执对应的题目详情和每种成品的资料预览，核对题干、选项、答案、解析以及公式字形、箭头、根式和裁切；在 `review.md` 记录所见证据。页面无法访问时报告“已归档，目标展示待核验”，不能写成全部检查通过。

工作台和云端 Agent 不在同一台机器时，先保留归档清单，在工作台所在机器运行重试；不要擅自把本机服务或令牌暴露公网。

## 生成命令联动

`python scripts/run.py finish /工作目录 --html --archive-manifest /工作目录/result.archive.json`，可加 `--student-id`。此接口连接文源教学工作台，不使用 export_xueji.py 或学记的接口。

该参数用于生成与结构检查通过后立即归档，并自动生成、附入自包含 HTML。仍须按 Skill 完成视觉/事实检查；首次生成需要先看成品时，使用上面的独立归档命令。生成失败不会提交；归档失败不会删除成品。重新生成不要覆盖或复用旧归档清单。

客户端代码以 wenyuan-workbench/tools/archive_to_workbench.py 为维护源，三个技能携带相同副本，不要求用户把四个仓库放在一起。
