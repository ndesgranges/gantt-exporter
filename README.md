# Export GitHub to a Gantt (Mermaid)

This repo allows exporting a GitHub project roadmap into a Mermaid Gantt graph.

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
python export_gantt.py \
    --login YOUR_GITHUB_LOGIN \
    --project YOUR_PROJECT_ID
```

You might need to specify the repo it's linked to if you need to get
the milestones. Those are linked to the repository.

To do so, specify the
repository `YOUR_USERNAME/YOUR_REPOSITORY` with option `--repo`

Replace `YOUR_GITHUB_LOGIN` and `YOUR_PROJECT_ID`

For additional help, issue the command :
```sh
python export_gantt.py -h
```


## 4 - How to find the Project number

GitHub Project URLs include the project number.

User projects look like: `https://github.com/users/<USER>/projects/<NUMBER>`

The `<NUMBER>` part is the `--project` you pass to the script.


## Licensing

This project is dual-licensed.

### Open Source License (AGPL v3)
You may use, modify, and distribute this software
under the terms of the GNU AGPL v3.

### Commercial License
If you want to:
- Use this software in a commercial product
- Offer it as a hosted service without releasing source
- Distribute modified versions without AGPL obligations

You must obtain a commercial license.

Contact: sales@nicolasdesgranges.fr
