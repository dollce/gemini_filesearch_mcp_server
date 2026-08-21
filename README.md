# Gemini File Search MCP Server

A read-only stdio MCP server that lets ChatGPT and Codex search knowledge stored in your Gemini File Search Stores. It connects through [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) without exposing the server to the public internet.

> The source code in this repository is public, while the running MCP server and Gemini credentials remain in your environment. Secure MCP Tunnel is intended for private, developer-mode connections; it is not a mechanism for submitting or distributing a public OpenAI plugin.

![](images/chatgpt.png)


## Features

- **Easy Integration Method Between Private RAG (Gemini File Store) and ChatGPT**
- Search multiple Gemini File Search Stores in a single request
- Withhold Gemini answer text when no File Search citation is present
- List document names, indexing states, and update times for each Store
- Expose read-only MCP tools with no upload, update, or delete operations
- Apply best-effort redaction to API keys and recognizable credentials
- Run on Python 3.10 or later with no third-party Python packages

Documents in Stores selected by the user are treated as trusted knowledge sources for answers. Prompts, code, and commands embedded in those documents are treated only as retrieved data, not as instructions to execute.

## Connection Architecture

![](images/gemini_filesearch_mcp_server.png)

You do not need to open an inbound port to this MCP server. `tunnel-client` establishes an outbound HTTPS connection to OpenAI and forwards received MCP requests to the local stdio server.

## Requirements

- Python 3.10 or later
- Gemini API key
- A Gemini File Search Store containing indexed documents
- A `tunnel_id` from OpenAI Platform
- An OpenAI runtime API key for `tunnel-client`
- Developer-mode access and Tunnel permissions in the target ChatGPT workspace
- Outbound HTTPS access from the `tunnel-client` host to the OpenAI and Google APIs

The Gemini API key and the `tunnel-client` runtime API key are different credentials. Do not commit either one to Git or paste it into a chat.

Creating or editing a Tunnel requires Tunnels Read + Manage permissions in OpenAI Platform. Running `tunnel-client` and selecting the Tunnel in ChatGPT require Tunnels Read + Use permissions. To use the same server from Codex, associate the Platform organization used by Codex with the same Tunnel.

## 1. Configuration

The shell examples below are for macOS and Linux. From the repository root, copy the example file to the local settings path.

```bash
cp config/settings.example.json config/settings.json
chmod 600 config/settings.json
```

Edit the following values locally in `config/settings.json`.

```json
{
  "GEMINI_API_KEY": "your-local-gemini-api-key",
  "model": "gemini-3.5-flash",
  "file_search_store_names": [
    "fileSearchStores/your-store-id"
  ],
  "top_k": 8,
  "temperature": 0.2,
  "request_timeout_seconds": 45
}
```

| Setting | Description |
|---|---|
| `GEMINI_API_KEY` | Gemini API key. At least 8 printable ASCII characters |
| `model` | Supported Gemini File Search model to use |
| `file_search_store_names` | Store resource names in `fileSearchStores/<store-id>` format |
| `top_k` | Number of document chunks to retrieve. Must be a positive integer |
| `temperature` | Answer-generation randomness. Not sent for some models or APIs |
| `request_timeout_seconds` | Gemini request timeout, from 5 to 75 seconds |

To search multiple Stores, add more resource names in the same format to the `file_search_store_names` array.

The default settings path is `config/settings.json`. To use a different location, set an absolute path in the environment that runs the MCP server.

```bash
export GEMINI_FILESEARCH_SETTINGS=/absolute/path/to/settings.json
```

`config/settings.json` and `config/settings.local.json` are excluded from Git.

## 2. Connect through Secure MCP Tunnel

Download `tunnel-client` from the Tunnel settings in OpenAI Platform, or install the [latest official release](https://github.com/openai/tunnel-client/releases/latest). After installation, review the quickstart commands.

```bash
tunnel-client help quickstart
```

After creating a Tunnel in OpenAI Platform, obtain its `tunnel_id` and runtime API key. The commands below use macOS/Linux shell syntax; replace the path and ID with values for your environment. On Windows, set the same environment variable using PowerShell syntax.

```bash
export CONTROL_PLANE_API_KEY="your-openai-tunnel-runtime-key"

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile gemini-filesearch \
  --tunnel-id tunnel_your_id \
  --mcp-command "python3 /absolute/path/to/repository/scripts/mcp_server.py"

tunnel-client doctor --profile gemini-filesearch --explain
tunnel-client run --profile gemini-filesearch
```

`doctor` is a preflight check. For tool discovery and calls to work, `tunnel-client run` must remain running in a healthy and ready state.

The Python and server paths supplied through `--mcp-command` are stored literally in the Tunnel profile. They are not updated automatically when the repository moves or its directory structure changes. If `can't open file` or `no such file or directory` appears immediately after `run`, rerun the `init` command above with `--force` and the current absolute path to `scripts/mcp_server.py`, then rerun `doctor --explain`.

In ChatGPT, enable developer mode and connect in this order:

1. In Plugins, choose the option to add a developer app.
2. Select **Tunnel** as the connection type.
3. Select the Tunnel associated with the target workspace.
4. Start a new conversation and confirm that the MCP tools are available.

If the Tunnel does not appear in the list, confirm that it is associated with the target ChatGPT workspace as well as the Platform organization.

In Codex, select the tunnel-backed MCP target associated with the Platform organization used by Codex. Although the connection UI differs by product, the same private MCP server and Tunnel can be reused.

## MCP Tools

| Tool | Purpose |
|---|---|
| `gemini_filesearch_search` | Search all configured Stores and return an answer with citation metadata |
| `gemini_filesearch_inventory` | List names, states, and update times for the first 20 documents in each Store |
| `gemini_filesearch_status` | Show the selected settings and whether a key is configured without calling an external API |

Use `search` for a specific question. If you do not know which documents are available, call `inventory` first and then search by file name or topic. A successful `status` call does not prove that the key is valid or that the Store is accessible.

Search results use the following primary status fields:

- `answer_status: citation_backed`: At least one recognized File Search citation is present
- `answer_status: no_cited_support`: No citation is present, so the provider's answer text is withheld
- `has_citations`: Whether at least one citation is present

A citation indicates that retrieved evidence was included. It does not automatically guarantee the accuracy of every sentence or citation.

## Security and Privacy

- The Gemini API key is sent in the `x-goog-api-key` header, not in the URL.
- The Gemini API key is sent only to the Google Gemini API and is not used to authenticate with the OpenAI Tunnel.
- The `tunnel-client` runtime API key is used only with the OpenAI Tunnel control plane.
- API keys must contain only printable ASCII characters to prevent header injection.
- Interactions API requests include `store: false` to disable Interaction storage.
- MCP questions and responses pass through ChatGPT/Codex and Secure MCP Tunnel. Search requests, Store names, and search results are processed by the Gemini API. Each service's standard application and API logging policies may apply.
- Recognizable credentials are redacted before search results are returned.
- Redaction is a supplemental safeguard against accidental exposure, not a complete DLP system.
- The system instruction that tells the model not to follow commands found in documents is not a substitute for an independent prompt-injection detector.

## Limitations

- Secure MCP Tunnel is intended for private connections and does not support public plugin submission.
- The server uses the API key and Store list from one settings file. It does not provide per-user OAuth or tenant isolation.
- `inventory` returns only the first 20 documents from each Store and does not fetch subsequent pages automatically.
- All configured Stores are supplied as search targets, but the server does not independently prove which Store Gemini selected results from.
- Supported models and Gemini API behavior may change. Check the [official Gemini File Search documentation](https://ai.google.dev/gemini-api/docs/file-search) for current information.
