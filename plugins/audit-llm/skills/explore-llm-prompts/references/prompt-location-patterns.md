# Prompt construction grep patterns by stack

| Stack | Patterns to grep for |
|---|---|
| Python | `SystemMessage(`, `role.*=.*"system"`, `system=`, `PromptTemplate`, `ChatPromptTemplate`, f-strings assigned to a variable named like `*prompt*`/`*instructions*` |
| TypeScript/JavaScript | `role: 'system'`, `role: "system"`, `SystemMessage`, template literals assigned to `*Prompt*`/`*Instructions*` |
| .NET/C# | `new SystemChatMessage(`, `ChatRole.System`, `Kernel.InvokePromptAsync(`, `.prompty`/`.yaml` prompt config files (Semantic Kernel) |
| Java/Spring AI | `SystemMessage(`, `PromptTemplate`, `@SystemPrompt` |

Also check for prompts stored outside source: a `prompts` database table, a
CMS/feature-flag field, or a vendor prompt-management SaaS referenced by an
API key/project id in config - these need to be listed with
`"version_controlled": false` even though there's no file to cite; cite the
storage location instead (table name, admin URL, config key).
