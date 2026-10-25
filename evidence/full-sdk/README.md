# Actual installed NVIDIA SDK reproduction

`nvidia-1.4.3-result.json` records a successful offline regression against
`langchain-nvidia-ai-endpoints==1.4.3`, installed from official PyPI with its real
dependencies. `langchain-core==1.7.0` supplies the actual `AIMessage` class.

Original SDK serialization dropped both normalized tool calls. The reviewed
patched module copy preserved both calls and their nested/Unicode/boolean/zero
arguments. Plain user/system messages, empty tool results, and legacy calls
remained intact; a deliberate second-call corruption failed the fixed oracle.

The installed SDK is unchanged. The candidate executes only the saved reviewed
patch of `_utils.py` with the real dependencies. This validates that serializer
boundary, not complete provider behavior or a live agent task. No model API or
credentials were used. The child process uses Python isolated mode, an explicit
environment allowlist, a local empty home, and an audit hook blocking socket
connect/DNS/bind. These controls are not claimed to be an OS sandbox.

From the repository root:

```powershell
python -m pip install --target .sdk-nvidia --index-url https://pypi.org/simple langchain-nvidia-ai-endpoints==1.4.3
.\.venv\Scripts\python.exe -I examples\reproductions\full_sdk_nvidia.py
```

For the resolved dependency versions from this run, install using
`--requirement evidence/full-sdk/requirements-resolved.txt` into a clean target.
The resolved requirements are version-pinned; wheel download hashes were not
captured. The exact reviewed serializer file has a mandatory SHA-256 check, and
the original wheel's METADATA/WHEEL/RECORD and license are preserved alongside
the original source and patch. `.sdk-nvidia/` is ignored by Git.

Installation attempts: the first command used `.venv\Scripts\python.exe -m
pip` and failed with `No module named pip` before downloading anything. The
subsequent system `python -m pip` command above completed successfully, installing
only into `.sdk-nvidia`. The reproduction itself ran with the repository venv's
Python 3.13.14.
