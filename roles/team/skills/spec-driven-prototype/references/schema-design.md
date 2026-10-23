# 多租户 SaaS 库表设计

设计库表时读。重点不是画 ER 图，而是**哪些决策事后改不了**。

## 一、先声明口径差异

库表设计通常按**全量口径**做（含架构建议文档的内容），会大于原型的本期口径。必须在文档里显式说明差异在哪几处，否则开发会以为库表就是本期范围。

> 数据库设计同时考虑了架构约束章的内容（自然人、多租户、门控、两条钱流），覆盖范围大于本 PRD。待确认项确定后，支付渠道、日志留存期、教练与会员的关联三处表结构需相应调整。

## 二、事后改不了的六个决策

这些必须在开工前拍板，因为改动成本随数据量线性上升。

**1. 基础实体是「人」还是「账号」。** 如果存在「有自然人、无账号」的情形——后台代录入的成员、批量导入的被推荐人、家长绑定的未成年学员——那基础实体必须是自然人。把账号当基础实体的话这些数据无处安放。

**2. 跨租户去重靠什么键。** 身份证号 / 护照号。这是敏感 PII，必须在本期的申请表单里就采集。**如果本期不采集，后期两个租户的同一个人永远无法自动归并**——因为历史数据里根本没有这个字段。

**3. 编号的唯一性作用域。** 会员号是租户内唯一还是全局唯一、序号按年重置还是永续。改这个要重编所有历史单号。

**4. 敏感字段的存储形式。** 只存哈希则无法展示后四位、无法向监管报送原文。推荐三列并存：`_hash`（SHA-256 + 全局盐，用于去重与查找）+ `_cipher`（AES-GCM，受控解密）+ `_last4`（明文，仅供展示）。

**5. 两条钱流是否分开。** SaaS 场景通常有两条：租户→平台（订阅费，平台收款）和终端用户→租户（业务费，租户收款）。用一个 `money_flow` 枚举从数据层分开，否则对账时无法拆分。

**6. 档案是否可原地修改。** 若有合规留存要求，档案锁定后不可编辑，更正 = 新建一条事件引用旧事件。这决定了表要不要 `correction_of_id` 与 `state` 字段。

## 三、可扩展性机制

目标是「加功能不改表结构」。以下每条都对应一类未来需求。

| 机制 | 实现 | 解决 |
|---|---|---|
| 统一申请单 | 一张表 + `app_type` 枚举 | 入会/续费/入驻/转店共表；二期加报名类只加枚举与模板 |
| 统一订单 | 一张表 + `order_type` + `money_flow` | 二期商城/课程订单复用 |
| 单表多态机构 | `org_type` + `parent_id` + `path` 物化路径 | 总会/子机构/分支同表，加层级不建新表 |
| 字典三层 | 平台预置（编码只读）+ 租户覆写（改名/启停/排序）+ `allow_tenant_extend` | 新增业务类型零发版 |
| KV 配置表 | `group_code` + `setting_key` + JSON 值 | 新增配置项不改表 |
| 模块门控三件套 | `plat_module` + `plan_module` + `tenant_module_override` | 套餐调整与单客户特批都不改表 |
| 权限点表驱动 | `perm_code` 层级 + 关联 `module_code` | 新增功能只插数据；与套餐门控做交集判定 |
| 表单字段映射 | `map_target` 指向固定列，为空则落 `ext_json` | 核心字段可查重，扩展字段自由，**映射关系本身可配置** |
| 版本化定价 | `valid_from` / `valid_to` | 改价不影响已生成订单，历史订单可溯源 |
| 事件外发表 | outbox + 幂等键 | 「一次审核触发建档+生成订单+发通知」的最终一致 |

## 四、生成列做「仅生效行唯一」

一类反复出现的约束：**同一时刻只能有一个生效记录，但历史记录要留痕**。普通唯一索引做不到。

```sql
active_person_id BIGINT UNSIGNED GENERATED ALWAYS AS
  (IF(status IN ('pending','active','frozen'), person_id, NULL)) STORED,
UNIQUE KEY uk_tenant_active_person (tenant_id, active_person_id)
```

非生效行的生成列为 `NULL`，MySQL 唯一索引把多个 NULL 视为互不相同，自动放行。

适用场景：一人一租户一个生效会籍（退会后可重新入会）、一个自然人只能被一个账号绑定（解绑后可换绑）。

**注意**：生成列必须定义在它引用的列之后。

## 五、软删除与唯一索引

`deleted_at` 用 `NOT NULL DEFAULT '1970-01-01'`，**不要用 NULL**。因为 MySQL 唯一索引把多个 NULL 视为互不相同，`UNIQUE(tenant_id, code, deleted_at)` 在 NULL 方案下等于没有约束。

## 六、实机验证

不要只靠肉眼看 DDL。装一个真实数据库跑一遍：

```bash
apt-get install -y -qq mysql-server-8.0
mysqld --initialize-insecure --datadir=/tmp/mysqld/data
chown -R mysql:mysql /tmp/mysqld /var/run/mysqld    # 必须：mysqld 降权到 mysql 用户
setsid mysqld --datadir=/tmp/mysqld/data --socket=/var/run/mysqld/mysqld.sock \
  --skip-networking --mysqlx=0 >/dev/null 2>&1 </dev/null &
mysql -uroot -e "CREATE DATABASE test DEFAULT CHARSET utf8mb4"
mysql -uroot test < schema.sql
```

三个坑：

- **权限**。`mysqld` 会降权到 `mysql` 用户，socket 目录和 datadir 都要 `chown`，否则静默失败、日志空白。
- **后台进程**。`cd x && cmd &` 会把整个链条放到后台导致 `cd` 只在子 shell 生效。用 `setsid` 并把启动与后续命令放在**同一个** bash 调用里，否则服务在两次工具调用之间被杀掉。
- **`sqlglot` 之类的解析器不认索引级 `COMMENT`**。那是合法 MySQL 语法，报错是解析器的限制而非 DDL 的问题。要真实验证就用真实数据库。

### 验证约束行为，不只验证语法

建表成功不等于约束正确。跑用例：

```sql
-- 同租户同人第二个生效会籍应被拒
INSERT ... VALUES (1,'C002',100,'active');
-- 期望 ERROR 1062 Duplicate entry '1-100'
-- 第一条改 quit 后应可插入（退会再入会）
-- 不同租户同一人应可各有一个（跨租户入会）
-- 支付回调重复入账应被幂等键拒绝
```

这些用例是设计意图的可执行表达。跑通了才算设计成立。

## 七、分区与留存

审计类表（操作日志、消息发送记录）通常有长期留存要求且数据量最大。按时间分区：

```sql
PRIMARY KEY (id, created_at)     -- 分区表的唯一索引必须包含分区列
PARTITION BY RANGE (YEAR(created_at)) (
  PARTITION p2026 VALUES LESS THAN (2027), ... PARTITION pmax VALUES LESS THAN MAXVALUE)
```

`AUTO_INCREMENT` 列必须是某个索引的第一列，`PRIMARY KEY (id, created_at)` 满足。

**留存与被遗忘权的冲突**：合规要求日志留存 N 年不可删，隐私法规要求用户可注销。解法是**匿名化而非硬删除**——保留 ID 与审计链，清空可识别个人信息的字段，加 `anonymized_at` 标记。

## 八、通用约定

| 项 | 约定 | 理由 |
|---|---|---|
| 租户隔离 | 租户内表首列必带 `tenant_id`，且是每个复合索引第一列 | 索引前缀命中；将来分库分表无需改索引 |
| 金额 | `DECIMAL(14,2)` + `currency CHAR(3)` | 禁止浮点 |
| 时间 | `DATETIME(3)` 存 UTC，租户时区单独存 | 多区域扩展 |
| 外键 | 不建物理外键 | 分库分表友好；完整性由应用层 + 定时校验任务保证 |
| 乐观锁 | 可变业务表带 `row_version` | 审核、改价、状态流转的并发保护 |
| 快照字段 | 日志表存 `operator_name` / `target_name` | 账号改名或删除后历史日志不失真 |
| 幂等 | 关键写操作有唯一键或幂等键 | 防支付回调重复入账 |

## 九、交付时列出待确认

库表设计会暴露一批需求层面的空白。和 PRD 的缺口清单一样列出来，重点是那些**影响表结构**的：

- 状态何时生效（决定状态机与到期日起算）
- 唯一性约束的粒度（同一人在同一租户能否有多个身份）
- 敏感字段的存储形式
- 编号的作用域
- 留存期与注销策略的冲突如何解

每条注明「若改动，影响哪几张表」。
