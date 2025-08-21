# Knowledge Sources

Declare reusable knowledge sources in `config/agents.knowledge.yaml`. Selection is controlled from `config/crew.yaml -> knowledge_sources`.

## Supported types

- `string`
- `text_file`
- `pdf`
- `csv`
- `excel`
- `json`
- `web_content` (requires `docling`)

## Example config (`config/agents.knowledge.yaml`)

```yaml
knowledge_sources:
  user_profile:
    type: string
    content: |
      User Profile: John Doe
      Location: San Francisco

  company_policies:
    type: text_file
    file_paths: ["company_policies.txt"]

  api_endpoints:
    type: json
    file_paths: ["api_endpoints.json"]
    content_key: documentation

  web_documentation:
    type: web_content
    urls:
      - https://docs.crewai.com/concepts/knowledge
    selector: main
    max_depth: 2
```

## Crew selection (`config/crew.yaml`)

```yaml
# Semantics:
# - omit key or set to ["ALL"] => use all available
# - [] => use none
# - [names...] => only those listed
knowledge_sources: []
```

Notes:

- Files are resolved from the project root; if paths are inside `knowledge/`, the loader normalizes them accordingly.
- `web_content` sources require `docling` to be installed (`pip install docling`).
- Errors are printed but do not stop the run; missing files will be reported.
