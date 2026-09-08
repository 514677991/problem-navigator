# Chinese and English behavior scenarios · 中英文行为场景

These are review cases for the shared language policy, not claimed live-host transcripts.
Every case retains the same schema and evidence/acceptance requirements.

以下场景用于审阅共同语言规则，不冒充真实宿主运行记录。每个场景都保留相同的 schema、
证据质量与验收要求。

| Request / 请求 | Expected behavior / 预期行为 |
|---|---|
| “只根据我提供的材料，分析社团会议为什么低效。” | 中文访谈和研究报告；离线取证；键名仍为 `analysis_goal`、`neutral_synthesis` 等。 |
| “Use only my notes to explain why our community meetings are ineffective.” | English interview and research report; offline evidence; the same workflow and machine keys. |
| “请写一份英文 PRD，架构后续决定。” | English PRD because the explicit output request overrides the surrounding Chinese; `PRD_ONLY`, no mandatory architecture selection. |
| “Write the technical proposal in Simplified Chinese. Compare PostgreSQL indexing choices.” | 中文技术方案，保留 PostgreSQL 名称、原始引用与 `TECHNICAL_SPEC_ONLY` 等机器值；不得因英文问题正文而忽略明确语言要求。 |
| “帮我比较 Redis 和 PostgreSQL 的缓存实现。” | 技术名称不改变中文请求的主语言；解释和报告使用中文。 |
| Earlier: “Keep all final deliverables in English.” Later: “继续，补充性能约束。” | English final deliverables with Chinese clarification questions where needed; do not expand a deliverable-only preference to the conversation. |
| Earlier: “Keep all final deliverables in English.” Later, before acceptance: “这份报告改为中文，后续其他报告仍用英文。” | The current report preview is Chinese; other reports retain the earlier English preference. Keep evidence and machine keys; do not mark a translated preview accepted merely because another language was reviewed. |
| Chinese report cites an English API statement / 中文报告引用英文 API 声明 | Preserve the original quote and URL; label any Chinese translation. Translate chapter labels and explanations, not IDs, file names or quoted originals. |

A reviewer should compare the Chinese and English versions of the same scenario for
equal task scope, provider authorization, evidence quality and acceptance behavior.
Language is presentation and user preference, not a second state machine.

审阅时应比较同一场景的中英文版本，确认任务范围、工具授权、证据标准和验收行为一致。
语言是表达与用户偏好，不是第二套状态机。
