from arroyo import kit

def mock_source(name, type=None, **kwargs):
	return kit.Source(name=name, provider='mock', uri='fake://' + name, type=type)
