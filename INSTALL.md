# Installation and Operations

This guide covers Docker deployment, multiple Tunnels, and native installation for the Gemini File Search MCP server. For the project overview and quickstart, see [README.md](README.md).

Complete the [prerequisites in README.md](README.md#prerequisites) first. The shell commands below are for macOS and Linux and run from the repository root. Choose either Docker or native installation after preparing the configuration files.

- [Configuration files](#configuration-files)
- [Docker deployment](#docker-deployment)
- [Multiple Tunnels](#multiple-tunnels)
- [Native installation](#native-installation)
- [Troubleshooting](#troubleshooting)

## Configuration Files

Create the local configuration files if they do not exist. Existing files are preserved.

```bash
if [ ! -f config/settings.json ]; then
  cp config/settings.example.json config/settings.json
fi
if [ ! -f .env ]; then
  cp .env.example .env
fi
chmod 600 config/settings.json .env
```

### Credentials and Tunnel ID

Edit `.env` locally. Docker Compose reads it at startup; the native instructions below load it into the shell environment.

| Variable | Value |
|---|---|
| `CONTROL_PLANE_TUNNEL_ID` | Existing Platform Tunnel ID: `tunnel_` followed by 32 lowercase letters or digits. Replace `tunnel_your_id` |
| `CONTROL_PLANE_API_KEY` | OpenAI runtime API key authorized to use the Tunnel |
| `GEMINI_API_KEY` | Gemini API key with access to the configured File Search Stores |
| `GEMINI_FILESEARCH_SETTINGS_FILE` | Settings file to mount with Docker. Defaults to `./config/settings.json` |
| `DOCKER_UID`, `DOCKER_GID` | Docker container user and group IDs. Use the settings file owner's IDs; both default to `1000` |

The Gemini API key must contain at least 8 printable ASCII characters without whitespace. Both API keys go in `.env`; model and Store settings go in `config/settings.json`.

For Docker, run the following commands and add their respective results as `DOCKER_UID` and `DOCKER_GID` in `.env`. This assumes your current user owns the settings file. Check these values even if `.env` already exists, including after using the README quickstart, which supplies them only for its single command.

```bash
id -u
id -g
```

### Model and Stores

Edit `config/settings.json` using this format:

```json
{
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
| `model` | Gemini File Search model to use |
| `file_search_store_names` | One or more Store resource names in `fileSearchStores/<store-id>` format |
| `top_k` | Number of document chunks to retrieve; a positive integer |
| `temperature` | Answer-generation randomness, from 0 to 2. Not sent for some models or APIs |
| `request_timeout_seconds` | Gemini request timeout, from 5 to 75 seconds |

The server supplies the configured Store names together in one search request. To include more Stores, add their resource names to the array.

For Docker, the settings file must already exist. Relative values of `GEMINI_FILESEARCH_SETTINGS_FILE` are resolved from the directory containing `compose.yaml`, not the environment file's directory. Use an absolute path for a file elsewhere. For native execution, use `GEMINI_FILESEARCH_SETTINGS` as described in the native section.

`.env`, `.env.*` files other than `.env.example`, `config/settings.json`, and `config/settings.local.json` are excluded from Git. Put custom local settings files outside the repository or add their paths to `.gitignore`; arbitrary settings filenames are not excluded automatically.

## Docker Deployment

Docker with Docker Compose is required. The image includes Python and `tunnel-client` and supports Linux `amd64` and `arm64`, including Docker on Apple Silicon. It starts a client for the existing Tunnel ID in `.env`; create the Tunnel in OpenAI Platform during the prerequisites.

Exported shell variables override values in `.env` and files selected with `--env-file`. Unset conflicting variables before using these examples so the selected file supplies the values. See [Docker Compose environment variable precedence](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/#ways-to-set-variables-with-interpolation).

### Start and Check

With the configuration files and container UID/GID prepared above, start the service:

```bash
docker compose up -d --build
docker compose logs -f tunnel
```

Startup logs show three stages:

1. Validate the Tunnel variables and Gemini settings locally.
2. Create a temporary container profile with `tunnel-client init --force`.
3. Run `tunnel-client`, which launches the stdio MCP server and connects to OpenAI.

Check readiness in another terminal:

```bash
docker compose ps
docker compose exec tunnel tunnel-client health \
  --url http://127.0.0.1:8080 \
  --require-control-plane-poll
```

The container health check uses the same command to check Tunnel control-plane readiness. Check Gemini Store access separately by calling `gemini_filesearch_inventory` or `gemini_filesearch_search` from ChatGPT or Codex after connecting as described in the README prerequisites.

Compose passes the API keys as runtime environment variables, mounts the settings file read-only, and recreates the temporary Tunnel profile on each start. No host ports are published. The `restart: unless-stopped` policy restarts the service after its process exits unless you explicitly stop it.

### Update and Stop

After editing `.env` or replacing the mounted settings file, recreate the container:

```bash
docker compose up -d --force-recreate
```

After changing the source code, rebuild the image and update the container:

```bash
docker compose up -d --build
```

Stop and remove the container:

```bash
docker compose down
```

Your local `.env` and settings files remain available for the next start.

## Multiple Tunnels

Use one environment file and one unique Compose project name for each Tunnel ID. The example below runs two Tunnels in two containers using one shared image. Extend the `a b` lists to run more Tunnels.

Prepare the environment files. These commands assume the settings files belong to your current user. Existing environment files are preserved; check their values before starting.

```bash
for name in a b; do
  if [ ! -f ".env.$name" ]; then
    cp .env.example ".env.$name"
    printf '\nDOCKER_UID=%s\nDOCKER_GID=%s\n' "$(id -u)" "$(id -g)" >> ".env.$name"
  fi
  chmod 600 ".env.$name"
done
```

In each file, set its `CONTROL_PLANE_TUNNEL_ID`, an OpenAI runtime key authorized for that Tunnel, and the appropriate `GEMINI_API_KEY`.

| Environment file | Compose project | Tunnel ID | Container |
|---|---|---|---|
| `.env.a` | `gemini-a` | First Platform Tunnel ID | `gemini-a-tunnel-1` |
| `.env.b` | `gemini-b` | Second Platform Tunnel ID | `gemini-b-tunnel-1` |

By default, both containers share `./config/settings.json` while using their own API keys. To use different models or Stores, create a settings file for each and set `GEMINI_FILESEARCH_SETTINGS_FILE` in each environment file to its absolute path. Use the configuration-file format above and match each container's UID/GID to its settings file owner.

Build the image once, then start each project:

```bash
docker build -t gemini-filesearch-mcp:local .

for name in a b; do
  docker compose --env-file ".env.$name" -p "gemini-$name" up -d --no-build
done
```

The [`-p` option](https://docs.docker.com/compose/how-tos/project-name/) gives each Tunnel a separate Compose project. Each container has its own environment, temporary profile, and internal health listener on port `8080`. Reusing a project name updates that project's container.

Use the same `--env-file` and `-p` pair for every management command. For Tunnel A:

```bash
docker compose --env-file .env.a -p gemini-a ps
docker compose --env-file .env.a -p gemini-a logs -f tunnel
```

Check readiness in another terminal:

```bash
docker compose --env-file .env.a -p gemini-a exec tunnel \
  tunnel-client health --url http://127.0.0.1:8080 --require-control-plane-poll
```

Apply changes to Tunnel A's environment or settings mount without restarting Tunnel B:

```bash
docker compose --env-file .env.a -p gemini-a up -d --no-build --force-recreate
```

After source changes, rebuild the shared image and rerun the startup loop. To stop and remove both projects:

```bash
for name in a b; do
  docker compose --env-file ".env.$name" -p "gemini-$name" down
done
```

Use separate projects for different Tunnel IDs. `docker compose up --scale tunnel=n` duplicates the same service configuration, including its Tunnel ID and keys.

## Native Installation

Install Python 3.10 or later and `tunnel-client` on the host. Download the client through OpenAI Platform or its [official release page](https://github.com/openai/tunnel-client/releases/latest), following the [tunnel-client setup guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels#set-up-tunnel-client). No third-party Python packages are required for this MCP server.

Check the installed commands:

```bash
python3 --version
tunnel-client help quickstart
```

### Load the Environment File

Prepare `.env` and `config/settings.json` using the configuration section above. Native installation uses the same three Tunnel and API-key entries. Write `.env` as shell-compatible `KEY=value` assignments, with no spaces around `=`. Single-quote values containing spaces or shell-special characters.

The default native settings path is `config/settings.json`. To use a different file, add the following entry to `.env` with your file's absolute path. `GEMINI_FILESEARCH_SETTINGS_FILE`, `DOCKER_UID`, and `DOCKER_GID` are Docker-specific settings.

```dotenv
GEMINI_FILESEARCH_SETTINGS='/absolute/path/to/settings.json'
```

From the repository root, load `.env` before initializing or running the client:

```bash
set -a
. ./.env
set +a
```

`set -a` exports the loaded values so `tunnel-client` and its Python child process receive them. The Python server itself does not automatically read `.env`. Reload this block in each new terminal and after editing `.env`; assignments in the file replace existing shell values of the same name.

### Initialize and Run

Create the local profile once. Run this command from the repository root so the server path is stored correctly:

```bash
tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile gemini-filesearch \
  --tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --mcp-command "python3 \"$PWD/scripts/mcp_server.py\""
```

Check the profile, then start the client:

```bash
tunnel-client doctor --profile gemini-filesearch --explain
tunnel-client run --profile gemini-filesearch
```

`doctor` is a preflight check. Keep `run` active while connecting or using the MCP tools. Once the client is ready, use the connection instructions in the README prerequisites.

Press `Ctrl+C` to stop the client. To restart, return to the repository root, reload `.env`, and run the same profile again. After changing keys or model/Store settings, stop the client and follow this restart procedure. After changing the Tunnel ID or moving the repository, reload `.env` and rerun `init` with `--force`, then run `doctor` and `run` again.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Tunnel is missing in ChatGPT or Codex | Recheck permissions and workspace/organization associations in the [official Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels#permissions-and-access) |
| Docker reports a missing variable or invalid settings | Fill in the three required `.env` entries and the model/Store settings; replace example IDs and check for conflicting exported shell variables |
| Docker cannot read the settings file | Confirm the file exists and `DOCKER_UID`/`DOCKER_GID` match its owner |
| Native startup cannot find the server file | Return to the repository root and rerun the native `init` command with `--force` to refresh the stored path |
| Tunnel is ready but search fails | Call `gemini_filesearch_inventory` to check Store access, and confirm the Gemini API key, Store names, and model settings |
| A changed `.env` value is not used | Recreate the Docker container, or reload `.env` and restart the native client |
