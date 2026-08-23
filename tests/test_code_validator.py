from agentcad.validators.code_validator import CodeValidator


def test_normal_freecad_script_allowed():
    code = "import FreeCAD as App\nimport Part\nprint('AGENTCAD_SUCCESS')\n"
    assert CodeValidator().validate(code).passed


def test_subprocess_is_blocked():
    code = "import subprocess\nsubprocess.run(['echo','x'])\n"
    result = CodeValidator().validate(code)
    assert not result.passed
    assert any("subprocess" in x for x in result.issues)
