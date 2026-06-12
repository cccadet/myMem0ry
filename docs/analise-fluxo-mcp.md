# Análise crítica do fluxo MCP — myMem0ry

> Documento de avaliação do fluxo atual (v0.14.9). Objetivo: tornar o app
> **extremamente útil e enxuto**, sem trabalho desnecessário, preservando os 4
> pilares que importam para o usuário:
> 1. Continuar conversas entre code agents diferentes (handoff).
> 2. Salvar o que de fato importa.
> 3. Manter as separações por escopo (session → context → project → global).
> 4. Ter busca geral quando precisar.

---

## 1. Fluxo atual

O sistema tem **dois caminhos de escrita/leitura** que convivem e, em parte, se
sobrepõem.

### 1.1 Caminho A — Ferramentas MCP (custam tokens, o agente decide chamar)

Expostas em `mcp_server.py` (12 tools):

| Tool | O que faz | Lê/escreve em |
|------|-----------|---------------|
| `get_context` | Agrega memórias por escopo no início da sessão | SQLite (`memories`) |
| `save_memory` | Salva 1 memória | SQLite **+** arquivo `.md` |
| `search_memory` | Busca textual/semântica em memórias curadas | SQLite (`memories`) |
| `search_conversations` | Busca geral em transcripts arquivados | `.md` + vector store |
| `read_memory` | Lê conteúdo completo por `id` ou `path` | SQLite ou arquivo `.md` |
| `memory_handoff_begin` | Abre handoff para o próximo agente | SQLite (`handoffs`) |
| `memory_handoff_accept` | Peek do handoff pendente (não-mutante) | SQLite (`handoffs`) |
| `memory_pin` / `memory_unpin` | Protege memória da decadência | SQLite (`memories`) |
| `memory_forget_sweep` | Limpa memórias obsoletas | SQLite (`memories`) |
| `memory_stats` | Estatísticas gerais | SQLite (`memories`) |
| `evolve_fact` | Consolida fatos contraditórios | SQLite (`memories`) |

### 1.2 Caminho B — Hooks (zero tokens, automático)

Disparados pelos scripts em `hooks/claude-code/*.sh`, que fazem `POST /hook`
no servidor HTTP (`daemon.py` sobe o servidor sob demanda):

- **SessionStart** → grava observação `session-start` **e** faz
  `GET /handoff/accept`, imprimindo o handoff pendente no stdout. Esse texto é
  prefixado ao primeiro prompt do agente (foi o `📥 myMem0ry: pending handoff`
  que apareceu nesta sessão).
- **PostToolUse** → grava 1 observação `post-tool-use` **por chamada de
  ferramenta** (resumida em `sanitize._summarize_post_tool_use`).
- **SessionEnd** → grava observação, arquiva a conversa inteira em `.md`
  (a partir do `transcript_path`, sem custo de token) e, se não houver handoff
  explícito, gera um **auto-handoff** a partir das observações.

### 1.3 Diagrama do ciclo de vida

```
                 ┌─────────────── SessionStart (hook) ───────────────┐
                 │ grava obs + injeta handoff pendente no 1º prompt    │
                 └────────────────────────────────────────────────────┘
                                      │
          (opcional, custa tokens) get_context  ◄── o agente PRECISA lembrar
                                      │
                 ┌────────── durante a sessão ──────────┐
                 │ PostToolUse(hook): 1 obs por tool     │  ← alto volume
                 │ save_memory(MCP): grava SQLite + .md   │
                 │ search_memory(MCP): lê só .md          │
                 └───────────────────────────────────────┘
                                      │
                 ┌─────────────── SessionEnd (hook) ─────────────────┐
                 │ arquiva conversa .md + auto_handoff_from_session    │
                 │ (resumo = últimas 20 observações de tool-use)       │
                 └─────────────────────────────────────────────────────┘
```

---

## 2. Pontos fortes

- **Separação de escritas por custo** (a ideia central é boa): escritas em massa
  (arquivamento de conversa, observações) via hook = **0 tokens**; só o que é
  curadoria vai por MCP.
- **Escopos bem modelados** no SQLite (session/context/project/global) com
  resolução automática a partir de `cwd` (git remote = project, branch = context).
- **Handoff tipado** (summary, open_questions, next_steps) com expiração (7 dias)
  e auditoria — bom alicerce para o pilar "trocar de harness no meio da tarefa".
- **Offline / sem API key**: spaCy + sqlite-vec + BM25, sem dependência externa.
- **Robustez operacional**: daemon auto-sobe, health check, schema idempotente com
  `PRAGMA user_version` (evita contenção de lock), sanitização de segredos.
- **Multi-agente real**: handoff é agnóstico de CLI (claude-code, codex, opencode…).

---

## 3. Pontos fracos (o que está atrapalhando o objetivo)

### 🔴 3.1 Duas fontes de verdade que não conversam (SQLite × `.md`)

`save_memory` grava **nos dois**, mas cada feature lê só de um lado:

- `search_memory` busca **apenas** nos `.md` → **ignora** os parâmetros
  `scope`, `memory_type` e `tags` que estão na própria assinatura da tool
  (parâmetros mortos — a API mente para o agente).
- `get_context`, `memory_stats`, `pin/unpin`, `forget_sweep` operam **apenas**
  no SQLite.
- O `.md` salvo **não carrega** scope/project/tags/type (só título, id, data,
  conteúdo). Logo, mesmo que `search_memory` quisesse filtrar por escopo, não
  conseguiria — a metainformação não está lá.

**Consequência prática:** existe `store.search_memories()` no SQLite que
**respeita** escopo/tipo/tags/projeto — mas a tool MCP exposta usa a outra
implementação (a que ignora tudo). O recurso certo existe e está desligado.

### 🔴 3.2 `pin` / `forget` são inalcançáveis pelo fluxo normal

`memory_pin`/`memory_unpin`/`forget_sweep` exigem um `memory_id` do SQLite.
Mas `search_memory` devolve `path` (do `.md`), **não** o `id`. Não há tool para
listar memórias com seus ids. Resultado: o agente **não consegue** fixar ou
apagar algo que acabou de buscar. Toda a maquinaria de pin/retention fica órfã.

### 🔴 3.3 Memórias curadas e dumps de conversa no mesmo balaio

Conversas arquivadas (SessionEnd) e memórias deliberadas (`save_memory`) caem na
**mesma pasta** `conversations/<data>/<uuid>.md`. Como `search_memory` roda
ripgrep/bm25 sobre tudo, os arquivos enormes de conversa **soterram** as poucas
memórias importantes nos resultados. Isso fere diretamente o pilar "salvar o que
importa e achar depois".

### 🔴 3.4 O auto-handoff produz ruído, não sinal

`auto_handoff_from_session` monta o resumo com as **últimas 20 observações**, que
são quase todas `post-tool-use` (`[post-tool-use] tool: Edit; file: ...`). Foi
exatamente o que apareceu no início desta sessão: uma lista de chamadas de
ferramenta em ordem reversa — **sem narrativa, sem prompts do usuário, sem
decisões**. Como o pilar #1 (continuar entre agents) depende do handoff, o
comportamento *padrão* (quando o agente esquece o `memory_handoff_begin`) entrega
um handoff de baixíssimo valor.

### 🟠 3.5 Caminho duplo e confuso para o handoff

O hook de **SessionStart já faz** `/handoff/accept` (marca como aceito **e**
injeta no prompt). Então, quando o agente roda, o handoff **já foi consumido**.
A tool `memory_handoff_accept` vira:
- redundante no Claude Code (o hook já entregou), e
- perigosa: se chamada, marca um *segundo* handoff como aceito ou retorna `None`,
  confundindo o agente.

Há dois mecanismos para a mesma coisa, com semântica de "consumo" diferente.

### 🟠 3.6 Recuperação útil é manual; a ruidosa é automática

`get_context` (a leitura mais valiosa) **depende do agente lembrar** de chamar —
custa tokens e é frequentemente pulada. Já o auto-handoff (ruidoso) é
automático. Está invertido: o de alto sinal deveria ser o injetado.

### 🟠 3.7 `get_context` é raso e não usa salience

- `per_scope = top_k // n_escopos`. Com `top_k=5` e 4 escopos → **1 por escopo**.
  Se o projeto tem 10 decisões importantes, retorna ~1.
- Ordena por `created_at DESC` (mais recente), **nunca** por `salience` — apesar
  de `salience` ser calculada e gravada em toda memória. Ou seja: toda a
  maquinaria de salience só serve ao `forget_sweep`; não melhora a recuperação.

### 🟠 3.8 Amplificação de escrita por `post-tool-use`

Cada chamada de ferramenta gera: 1 POST HTTP + 1 insert em `observations` +
1 insert em `audit_log` (o `create_observation` audita também). Uma sessão com
centenas de tools = centenas de linhas, cujo único consumidor é o resumo de
auto-handoff (que, como visto em 3.4, é ruim). Custo alto, payoff baixo.

### 🟠 3.9 Identidade de projeto frágil (`project_id = git remote origin`)

- Repo **sem remote** → `project_id = None`. Aí **todos** os projetos sem remote
  colapsam no mesmo `None` → contaminação cruzada de memórias "de projeto".
  O código só emite `warning` e segue.
- `project_path` (que seria um identificador estável) existe mas **não é usado**
  como fallback de escopo no `get_context`.
- Branch como `context`: rename/delete da branch órfã as memórias.

Para o caso de uso do usuário (trocar de harness no meio da tarefa, vários
repos), isso é justamente onde mais dói.

### 🟡 3.10 Sanitização não cobre Windows

`_strip_home_paths` só casa `/home/...` e `/Users/...`. Caminhos
`C:\Users\ccsantos\...` (o ambiente atual) **não** são mascarados → vazam para
memórias e conversas arquivadas.

### 🟡 3.11 spaCy em inglês por padrão

`SPACY_MODEL=en_core_web_lg`. O usuário escreve em português; a expansão de
query (`expand_query_spacy`) fica subótima até trocar para `pt_core_news_lg`.

### 🟡 3.12 Pequenos defeitos

- `accept_handoff`: `open_questions`/`next_steps` são desserializados **duas
  vezes** (linhas duplicadas) — inofensivo mas sinal de descuido.
- `PreToolUse` e `PostToolUse` mapeiam ambos para `post-tool-use`; se os dois
  forem configurados, duplica observações.
- `/health` reporta `"version": "0.7.0"` fixo (desatualizado vs 0.14.9).

---

## 4. Recomendações (enxugar o desnecessário, reforçar o núcleo)

Princípio: **uma fonte de verdade**, recuperação automática de alto sinal,
e cortar a maquinaria que não paga o próprio custo.

### ✅ Fazer (núcleo)

1. **Unificar a busca no SQLite.** Trocar a implementação de `search_memory`
   para usar `store.search_memories()` (que já respeita scope/type/tags/project).
   Manter os `.md` apenas como _export_ legível, não como índice de busca.
   → Resolve 3.1 e ativa os filtros já existentes.

2. **Dar `id` nos resultados de busca e de `get_context`.** Com o `id`, `pin` e
   `forget` passam a ser usáveis. → Resolve 3.2.

3. **Separar fisicamente memórias de conversas arquivadas.** Ex.:
   `memories/<data>/...` vs `conversations/<data>/...`. Busca de curadoria não
   deve competir com dumps. → Resolve 3.3.

4. **Handoff automático com sinal.** No SessionEnd, em vez de concatenar
   `post-tool-use`, gerar o resumo a partir de: último(s) prompt(s) do usuário +
   memórias `decision`/`fact` criadas na sessão + arquivos tocados (deduplicados).
   Opcionalmente, instruir o agente (via prompt) a chamar `memory_handoff_begin`
   no fim — mas o **fallback automático precisa ser bom sozinho**. → Resolve 3.4.

5. **Injetar `get_context` automaticamente no SessionStart**, junto do handoff
   (o hook já imprime no primeiro prompt). Assim o agente recebe contexto sem
   gastar uma chamada de tool. → Resolve 3.6.

6. **Rankear `get_context` por salience/recência combinadas** e remover o teto de
   "1 por escopo" (usar uma cota maior por escopo prioritário). → Resolve 3.7.

7. **Identidade de projeto robusta:** `project_id = remote origin` **ou**
   `project_path` normalizado como fallback (nunca `None` silencioso). → 3.9.

### ✂️ Cortar / simplificar (o que não paga o custo)

8. **`memory_handoff_accept` (MCP):** remover ou rebaixar a "peek" (não-mutante),
   já que o hook é quem consome o handoff. Elimina o caminho duplo. → 3.5.

9. **Observações `post-tool-use`:** parar de gravar 1 por tool. Ou (a) não gravar
   nada e derivar o handoff do transcript no SessionEnd, ou (b) gravar só erros e
   marcos (ex.: edição de arquivo). Cortar a auditoria redundante por observação.
   → Resolve 3.8.

10. **Salience:** ou passa a alimentar a recuperação (item 6) ou é simplificada
    a um pin/forget manual. Hoje é complexidade que só serve ao sweep.

### 🧹 Higiene rápida

11. Mascarar caminhos Windows em `_strip_home_paths`. → 3.10
12. Default `SPACY_MODEL=pt_core_news_lg` (ou auto-detecção). → 3.11
13. Remover desserialização duplicada em `accept_handoff`; `/health` ler a versão
    real do pacote; decidir entre `PreToolUse`/`PostToolUse`. → 3.12

---

## 5. Resumo executivo

O alicerce (escopos, handoff tipado, escrita zero-token por hook) é **sólido**.
Os problemas são de **integração e foco**:

- **Duas fontes de verdade** (`.md` × SQLite) que não conversam fazem busca,
  pin e filtros funcionarem pela metade.
- O **handoff automático** — justamente o pilar #1 — entrega ruído por padrão.
- Há **maquinaria cara e subutilizada** (salience sem ranqueamento, observação
  por tool, handoff_accept duplicado) que pode ser cortada sem perda.

Atacando os itens ✅ 1–7 e ✂️ 8–10, o app entrega os 4 pilares com bem menos
peças móveis: **uma busca que respeita escopos, um handoff que vale a leitura,
e contexto injetado de graça no início de cada sessão.**

---

## 6. Status de implementação (v0.15 em diante)

Todos os itens acima foram implementados nesta rodada de reorganização:

| Item | Mudança |
|------|---------|
| 3.1 / ✅1 | `search_memory` agora consulta o SQLite (`store.search_memories`) com filtro de texto real (tokenizado, EN+PT stopwords), respeitando scope/type/tags/project. |
| 3.2 / ✅2 | `search_memory` e `get_context` retornam `id`; novo `get_memory_by_id`; `read_memory(ref)` aceita id (SQLite) **ou** path (.md). `pin`/`forget` agora alcançáveis. |
| 3.3 / ✅3 | Novo `memories_dir` separado de `conversations_dir`. `save_memory` exporta o `.md` em `memories_dir` e grava `file_path` no SQLite. |
| 3.4 / ✅4 | `auto_handoff_from_session` reescrito: resumo a partir de prompts do usuário (transcript + observações `user-prompt`) + arquivos tocados + erros — não mais dump de tool-use. |
| 3.6 / ✅5 | Novo endpoint HTTP `/context`; o hook de SessionStart injeta o contexto no primeiro prompt (zero tokens), junto do handoff. |
| 3.7 / ✅6 | `get_context` ordena por `pinned, salience, created_at`, preenche o `top_k` por prioridade de escopo (sem teto de 1-por-escopo) e exclui deletados. |
| 3.9 / ✅7 | `stable_project_id` (remote **ou** `path:<abspath>`) aplicado no MCP, hooks e endpoints — nunca `None`. Funções git puras inalteradas. |
| 3.5 / ✂️8 | `memory_handoff_accept` agora é um *peek* não-mutante (`pending_handoff`); o hook continua sendo o único consumidor. |
| 3.8 / ✂️9 | Router só persiste observação de `post-tool-use` para ferramentas que mutam arquivo ou que retornam erro. Audit por observação removido. |
| ✂️10 | Busca geral isolada em `search_conversations` (semântica sobre transcripts), separada das memórias curadas. |
| 3.10 | `sanitize` mascara caminhos Windows (`C:\Users\x`), inclusive em resumos de tool-use. |
| 3.11 | `.env` com `SPACY_MODEL=pt_core_news_lg`; expansão de query tolera modelo ausente (degrada para query crua). |
| 3.12 | Desserialização duplicada em `accept_handoff` removida; `/health` reporta a versão real do pacote. |

### Superfície de ferramentas MCP resultante (12)
`get_context`, `save_memory`, `search_memory` (memórias curadas, com escopo),
`search_conversations` (busca geral), `read_memory` (id ou path),
`memory_handoff_begin`, `memory_handoff_accept` (peek), `memory_pin`,
`memory_unpin`, `memory_forget_sweep`, `memory_stats`, `evolve_fact`.
```
