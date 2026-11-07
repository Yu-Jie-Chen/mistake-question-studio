# {{subject_short}}{{grade_short}} · {{student}} · 错题卡

> ID：`{{id}}`

<!-- 这个模板只描述卡片的形状；真正生成卡片请用 build_card.py / build_card_html.py。
     标题：科目+年级简称 → 学生姓名（有 student.name 才有） → 错题卡。
     状态、来源、备注不进卡片；卡片以一个日期收尾。 -->

## 题目

{{instruction}}

{{stem}}

**{{subquestion_label}}** {{subquestion_text}}

### 选项

- **A.** ...
- **B.** ...
- **C.** ...
- **D.** ...

### 配图

![{{figure_id}}]({{figure_path}})

*{{figure_caption}}*

## 答案

{{final_answer}}

**检验：** {{verification}}

*答案置信度：{{confidence}}*

## 解析

{{analysis_steps}}

### 关键点

- ...

### 易错点

- ...

## 错因诊断

**学生答案：** {{student_answer}}

**错误类型：** {{error_types}}

**根因：** {{root_cause}}

**改进：** {{remedy}}

## 知识点与标签

- ...

- 难度：★★★☆☆

## 变式

{{variant}}

{{date}}
