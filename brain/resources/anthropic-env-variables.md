# Anthropic Environment Variables

> Created: 2023-10-19

Environment variable values to use Ollama as a local backend with Claude Code (offline mode).

| Variable | Value |
|----------|-------|
| `ANTHROPIC_API_KEY` | `m` |
| `ANTHROPIC_BASE_URL` | `http://localhost:11434` |
| `ANTHROPIC_AUTH_TOKEN` | `ollama` |

## Setting on Windows (CMD)

Use `setx` for persistent variables that survive terminal restarts:

```cmd
setx ANTHROPIC_API_KEY "m"
setx ANTHROPIC_BASE_URL "http://localhost:11434"
setx ANTHROPIC_AUTH_TOKEN "ollama"
```

`setx` writes to the registry. Changes take effect in new terminal sessions, not the current one.

## Related

- [[ollama-claude-code-setup]]
