# Estilo de código

Convecções duras, aplicadas em CI (`ruff check`) e em code review.

## Tamanho

- **Funções**: 4–20 linhas.
- **Arquivos**: <500 linhas. Dividir por responsabilidade.
- **Indentação**: máx 2 níveis. Usar early return em vez de aninhar.

## Tipos

- Explícitos. **Proibido** `Any`, `Dict` sem parâmetros, funções sem anotação.
- `from __future__ import annotations` quando o módulo depende de tipos ainda não importados.
- Unions com `|`, não `Union[...]`.

## Nomes

- Específicos e únicos. Evitar `data`, `handler`, `Manager`, `Helper`.
- Funções/métodos descrevem o que fazem: `resolve_project_id`, não `get_project`.

## Erros

- Mensagens incluem o valor ofensivo e o formato esperado.
  - Ex: `f"scope inválido {scope!r}, esperado um de {sorted(_VALID_SCOPES)}"`
- Não engolir exceções silenciosamente.

## Logging

- **Nunca** `print()` em código de biblioteca — usar `logging`.
- Logs de debug em **JSON estruturado**; saída de CLI em texto plano.
- `from src/mem0ry/utils/logging import get_logger` (verificar path exato).

## Docstrings

- Em **funções públicas**: `WHY` + 1 exemplo de uso.
- Em funções internas triviais: sem docstring.
- Preservar comentários existentes em refactor — eles carregam intenção.

## Formatação

- `ruff check` + `ruff format` localmente. CI só roda `check` (ver `.github/workflows/ci.yml`).
- Sem discussão de estilo além de ruff.

## Imports

- Ordem: stdlib, terceiros, locais. Ruff `I` cuida.
- Imports absolutos (`from mem0ry.x import y`), não relativos.

## Comentários

- **Mínimos** e só onde o *porquê* não é óbvio.
- Não comentar *o quê* — o nome da função já diz.

## When editing…

- Antes de refactor: ler o módulo inteiro (`read`) pra absorver convenções locais.
- Mypy roda em `uv run mypy src/mem0ry`; `mypy.ini` tem `ignore_missing_imports` para `spacy`, `sqlite-vec`, `rank_bm25`.
- CI quebra em `Any`/`Dict` sem typing — corrigir antes de push.
