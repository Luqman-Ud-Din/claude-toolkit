# Reviewing a third-party MCP server or plugin

- **Source**: who publishes it, is it the vendor's own or a community
  re-implementation, and is the connection pinned to a specific version/commit?
- **Tool list**: does it match what's documented, or does it expose tools not
  mentioned anywhere (a server can register more than it advertises)?
- **Declared side effects vs. actual scope**: does a "read-only search" server
  also register a write/delete tool that wasn't expected?
- **Transport trust**: is the connection to the server itself authenticated
  and encrypted, or a local unauthenticated socket assumed safe by proximity?
- **Update process**: does the app pin a version, or auto-update to whatever
  the server publishes next, with no review step before a new tool schema
  reaches production?
- **Data exposure**: what does the app send to this server as tool-call
  arguments - could that include data the server's operator (if third-party)
  shouldn't see?

Treat "we haven't reviewed this MCP server's actual tool implementation, we
just trust its listed schema" as worth a finding on its own when the server
has write/execute access - not just a note.
