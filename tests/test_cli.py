from pathlib import Path

from cq3d.cli import main


def test_cli_validate_and_build(tmp_path):
    source = tmp_path / "demo.cq3d"
    source.write_text(
        """
model demo
unit mm

box body
  size 10 20 30
end

export stl "demo.stl"
export step "demo.step"
""".strip()
        + "\n"
    )

    assert main(["validate", str(source)]) == 0
    assert main(["build", str(source)]) == 0
    assert (tmp_path / "demo.stl").exists()
    assert (tmp_path / "demo.step").exists()
