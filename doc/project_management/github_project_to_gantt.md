# Export GitHub to a Gantt (Mermaid)

This repo includes a small script that pulls a GitHub via API and generate
a Gantt as Mermaid diagram

## 1 - Prerequisites

- A GitHub Project with issues. Those will be grouped using the "Subject" field
- A GitHub token in `GITHUB_TOKEN` (classic token or fine-grained token).

## 2 - Configure the token

Set the token in your shell:

```sh
export GITHUB_TOKEN="<your_token_here>"
```

## 3 - Run the exporter


```sh
python tools/export_gantt.py \
    --login YOUR_GITHUB_LOGIN \
    --project YOUR_PROJECT_ID
```

Replace `YOUR_GITHUB_LOGIN` and `YOUR_PROJECT_ID`


## 4 - How to find the Project number

GitHub Project URLs include the project number.

User projects look like: `https://github.com/users/<USER>/projects/<NUMBER>`

The `<NUMBER>` part is the `--project` you pass to the script.
