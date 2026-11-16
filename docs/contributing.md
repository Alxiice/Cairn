# Contributing

How to set up a development copy, the tech stack, the architecture and the rules are in [CONTRIBUTING.md](https://github.com/Alxiice/Cairn/blob/main/CONTRIBUTING.md) on GitHub.

In short:

```sh
python -m venv .venv            # py -m venv .venv on Windows
python -m pip install -r requirements-dev.txt   # in the activated virtualenv
python -m pytest                # tests, with coverage: python -m pytest --cov
mkdocs serve                    # this documentation, with live preview
```

How Cairn was built, step by step, is in the [development plan](development-plan.md).
