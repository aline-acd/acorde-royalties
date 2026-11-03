# TRD — Decisões técnicas

| Tema | Decisão | Motivo |
|---|---|---|
| Banco | Neon Postgres (plano gratuito), branches `production` e `acorde-portal-dev` | Já usado pela equipe; branch de dev isola testes |
| Hospedagem | Vercel + GitHub | Já usados pela equipe |
| Autenticação | Neon Auth (login e senha com convite; Google OAuth opcional) | Custo zero, integrado ao banco, sem Drive |
| Isolamento por editora | Filtro por `editora_id` do usuário em toda consulta, reforçado com row level security no Postgres | Evita vazamento entre editoras |
| Importação | Script Python (pandas) lendo a aba `Todos` dos XLSX Abramus | Layout já conhecido; validação antes da gravação |
| Valores | Valor bruto da editora vem de `VL_EDITORA` (arquivo Editora); valor do autor de `VL_AUTOR` (arquivo Autor) | Campos do próprio relatório |
| Taxa | Aplicada sobre o bruto de cada beneficiário; tabela `taxas` com vigência | Histórico por competência |
| Competência | Lida do conteúdo (`PERIODO` / `COMPETENCIA`); divergência entre arquivos gera conflito | Regra combinada |
| Dados sensíveis | CPF/CNPJ armazenados mascarados; nunca em logs | Regra combinada |
| PDF | Renderização HTML → PDF no servidor (Playwright ou similar) mantendo o layout dos modelos | Layout exato |
| Gráficos | Biblioteca leve (ex.: Recharts) no front | Sem custo |
| Código | Fora de pastas sincronizadas; repositório sem dados reais | Regra combinada |

**Pendências técnicas:** nome do projeto no GitHub e no Vercel; confirmação de acesso ao branch `acorde-portal-dev`; escolha final entre Playwright e outro gerador de PDF após teste de layout.
