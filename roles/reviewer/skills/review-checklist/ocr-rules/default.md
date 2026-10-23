<!-- 来源：open-code-review v1.13.3 (375f64c) darwin/arm64 内置规则（Apache-2.0，见仓库 THIRD_PARTY_NOTICES.md），由 scripts/sync-ocr-rules.sh 导出，勿手改 -->
<!-- 适用：default -->

#### Correctness
Is the logic correct? Are there missing boundary conditions?
Are exceptions handled properly?
Is it thread-safe in concurrent scenarios?

#### Security
Are there security vulnerabilities such as SQL injection or XSS?
Is sensitive information handled correctly?
Is permission validation complete?

#### Performance
Are there obvious performance issues (e.g., N+1 queries, unnecessary loops)?
Are resources properly released?

#### Maintainability
Is the code clear and easy to understand?
Do names accurately express intent?
Does it follow the project’s existing code style and architecture patterns?

#### Test Coverage
Do critical logic paths have corresponding test cases?
Do test cases cover boundary conditions?
────────────────────────────────────────
