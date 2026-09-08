import json
from memoir.ingest import ingest_folder
from memoir.prefix import assemble_prefix
sources=ingest_folder('examples/notes')
a=assemble_prefix(sources);b=assemble_prefix(list(reversed(sources)))
print(json.dumps({'sources':len(sources),'ordered_paths':[s.path for s in a.sources],'prefix_hash':a.prefix_hash,'same_bytes_after_input_reversal':a.text==b.text,'cache_stable':a.cache_stable},indent=2))
