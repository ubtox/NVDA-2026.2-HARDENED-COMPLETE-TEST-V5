# NVDA MathCAT

This repository contains code from [MathCATForPython](https://github.com/nsoiffer/MathCATForPython), repackaged for integration into the core of NVDA.

## Weekly fetchAssets Workflow
A workflow is configured to run weekly which fetches the latest versions of the assets `Rules.zip` and `libmathcat_py-32-3.11-win.zip` from the latest release of MathCATForPython, unzips them, and pushes them to this repository.
