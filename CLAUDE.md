# claude-team 仓库约定

这个仓库存放我的 Claude Code 角色。每个 `roles/<角色>/` 是一个插件，`.claude-plugin/marketplace.json` 把它们登记成一个插件市场。完整说明见 README.md。

## 分支

- 主分支是 `main`，各台电脑安装和同步都以它为准。`/team:learn`、`/team:new-role` 的改动直接提交到 `main`。

## 改动规则

- 新角色、新技能用 `python3 scripts/scaffold.py` 生成，不要手工复制目录。它会同步更新 marketplace.json 和 agent 的 `skills:` 列表。
- 每次改动后运行 `python3 scripts/validate.py`，有 `claude` 命令时再运行 `claude plugin validate .`。不通过不提交。
- 不要给 plugin.json 或 marketplace.json 加 `version`：版本取自 git 提交，加了反而要手动维护。
- 每个角色的 plugin.json 都要有 `"dependencies": ["team"]`；每个 agent 的 `skills:` 都要包含 `team:house-rules`。
- `skills:` 里的技能名写全名 `<插件>:<技能>`。设置了 `disable-model-invocation: true` 的技能不能放进 `skills:`。
- 角色名、技能名：小写字母、数字、连字符；全仓库唯一；不以 `claude-`、`anthropic-` 开头。

## 内容规则

- 提示词和技能正文用简体中文；命令、标识符、frontmatter 字段名保持英文。
- 全员通用的习惯只写在 `roles/team/skills/house-rules/SKILL.md`，不要在各角色里重复。
- 角色特有的偏好写进该角色提示词的「我的习惯」章节；具体流程、模板、清单写成技能。
- 写法参考 `roles/team/skills/new-role/authoring-guide.md`：写可执行的规则并附原因，不写感想。

## 提交信息

- 新角色或新技能：`feat(roles): add <名字>`
- 沉淀习惯：`chore(habits): <一句话摘要>`
- 脚本和文档：`chore(scripts): ...` / `docs: ...`
