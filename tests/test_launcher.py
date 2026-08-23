from pathlib import Path
import re


def test_windows_launcher_is_english_and_defaults_to_agent_mode() -> None:
    root = Path(__file__).parents[1]
    launcher = root / "Start-ACV.cmd"

    assert launcher.exists()
    assert not (root / "启动ACV.cmd").exists()
    content = launcher.read_text(encoding="utf-8")
    assert not re.search(r"[\u4e00-\u9fff]", content)
    assert 'set "ACV_MODE=agent"' in content
    assert "-m acv %ACV_MODE%" in content
