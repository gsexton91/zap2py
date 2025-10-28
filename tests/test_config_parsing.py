import yaml
import importlib

def test_sample_yaml_parses():
    with open('tests/sample_lineups.yaml', 'r') as f:
        data = yaml.safe_load(f)

    assert 'lineups' in data and isinstance(data['lineups'], list)
    first = data['lineups'][0]
    for key in ('name', 'outfile'):
        assert key in first

def test_entrypoint_imports():
    mod = importlib.import_module('zap2py.__main__')
    assert hasattr(mod, 'main')
