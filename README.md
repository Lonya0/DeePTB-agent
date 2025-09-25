# DeePTB Agent

To use this, you need a DeePTB-agent-tools deployed url as input.
You can deploy one locally, or use mcp tools url from bohr

## setup

1. `pip install .` in this directory.
2. modify `.env` file to your llm model.

ps: you can set XX_API_KEY in `.env` file, but it is better to manually set environment variable with cli which is safer.
And by include this in your activate bash file this is much more safe and convenient.

3. run `dptbagent`

it is recommand to run `dptbagent --help` first which will teach you how to set host/port/mode.