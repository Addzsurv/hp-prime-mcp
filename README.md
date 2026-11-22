# hp-prime-mcp

**Connect your HP Prime calculator to Claude and other AI assistants.**

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server for the **HP Prime G2** graphing calculator. Plug the Prime into your PC with its USB cable and your AI assistant can **see the calculator's screen, write and install HP PPL programs on it, and read programs and matrices back**.

Works with Claude Code, Claude Desktop and any MCP client. Windows, Python, no extra packages.

![examples/HELLO.txt as the Prime draws it (rendered on the PC with prime_preview)](docs/hello_preview.png)

*Keywords: HP Prime, HP Prime G2, HP PPL, HP Prime programming, HP Connectivity Kit, MCP server, Claude, AI, calculator, USB, screenshot.*

## Try it in one sentence

With it set up (below), plug in your Prime and ask your assistant:

> "Check, send and run `examples/HELLO.txt` on my HP Prime, then show me its screen."

The assistant lints the program, builds it, puts it on the calculator (you click Send in the Connectivity Kit, or it goes straight over USB), and takes a screenshot to confirm.

## What it's good for

- **Writing Prime programs with an AI.** The assistant writes the PPL, checks it on the PC, installs it on the calculator, then looks at the screen to see it running. You only press the calculator's keys.
- **Getting results off the calculator.** Read matrices and programs back to the PC, for spreadsheets, CAD or reports.
- **Putting things on the calculator.** Programs built and sent from the PC.
- **"What's on my screen?"** The assistant can see what the calculator shows, so it can help when something looks wrong.

## What it can't do

- **Press keys or tap the screen.** It is not a remote control: on the firmware it was tested on (G2, build 15751), remote key presses have no effect. You drive the calculator; the assistant sees and exchanges data.
- **Work without the cable.** The Prime has no network.
- **Read data back on its own.** Matrices and programs are read from the copy HP's Connectivity Kit keeps on the PC, so the Kit has to have been open with the calculator plugged in.

## Tools

| Tool | What it does |
|---|---|
| `prime_status` | Which calculators the PC has data for, their programs, and whether the Connectivity Kit is running |
| `prime_screen` | A picture of the calculator's screen right now |
| `prime_lint` | Check a PPL source for errors the Prime's compiler won't explain |
| `prime_send_program` | Lint, build and install a program, through the Connectivity Kit (default) or straight over USB |
| `prime_list` | Programs, matrices, lists, apps and notes on a calculator |
| `prime_read_matrix` | A matrix (M0..M9) as rows of numbers |
| `prime_read_program` | A program's source code, read back off the calculator |
| `prime_preview` | Run PPL on the PC and render the screen it draws (optional, needs hpdev) |

## Needs

- Windows, Python 3.9+ (standard library only).
- An HP Prime G2 on its USB cable.
- [hp-prime-kit](https://github.com/JordiRigau/hp-prime-kit) (MIT): the USB and file-format tools this server builds on.
- HP Connectivity Kit (free, from HP): for reading data back and for the default install route.
- Optional: [hpdev](https://github.com/golba98/hp-prime-development-toolkit) (MIT), for `prime_preview` and a second checker.

## Setup

```
git clone https://github.com/JordiRigau/hp-prime-kit
git clone https://github.com/Addzsurv/hp-prime-mcp
```

Claude Code: add to your project's `.mcp.json` (or `claude mcp add`):

```json
{
  "mcpServers": {
    "hp-prime": {
      "command": "python",
      "args": ["C:/path/to/hp-prime-mcp/hp_prime_mcp.py"],
      "env": {
        "HP_PRIME_KIT": "C:/path/to/hp-prime-kit/hpprime.py"
      }
    }
  }
}
```

Claude Desktop: the same block under `mcpServers` in `claude_desktop_config.json`.

### Settings (environment variables)

| Variable | Default |
|---|---|
| `HP_PRIME_KIT` | `hp-prime-kit/hpprime.py` next to this file |
| `HP_CK_DIR` | `~/Documents/HP Connectivity Kit` |
| `HP_CK_EXE` | `C:\Program Files\HP\HP Connectivity Kit\ConnectivityKit.exe` |
| `HP_VIRTUAL_DIR` | `~/Documents/HP Prime/Calculators` (HP's Virtual Calculator) |
| `HPDEV` | unset (path to `hpdev.exe` to enable `prime_preview`) |
| `HP_PRIME_MCP_OUT` | `hp-prime-mcp-out` in the working folder (screenshots, built programs) |

## Notes

- **Windows gives the USB connection to one program at a time.** Screen capture and USB send need the Connectivity Kit closed; `prime_screen` can close and reopen it for you (`close_kit=true`).
- **The USB send replaces a program of the same name without asking**, and the calculator acknowledges nothing: check with `prime_screen`. The Connectivity Kit route (`method: "kit"`) is the safer default.
- hp-prime-kit's USB send was measured on firmware 15515; this server passes `--any-build` so it also runs on newer builds. Tested by the author on a G2, build 15751, with the Kit route; treat the USB route as experimental.
- While a program is running on the calculator, the screen shows that program, and the Connectivity Kit can't browse the calculator.

## Questions, other models and firmware

Tested on an HP Prime G2, firmware build 15751, on Windows 11. If you try it on a G1, another firmware or another OS, please [open an issue](https://github.com/Addzsurv/hp-prime-mcp/issues) with what worked.

## Licence

MIT. Not affiliated with HP.
