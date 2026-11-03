# Esquema do backend (dados, APIs e integrações)

## Dados
Ver `db/schema.sql`. Tabelas principais: `editoras`, `autores`, `taxas` (histórico por vigência), `uploads`, `lancamentos`, `usuarios_editora`, `usuarios_admin`, `auditoria`. View `v_total_editora_mes`.

Regras:
- Taxa sem linha em `taxas` = PENDENTE. `lancamentos.taxa_aplicada_pct` nulo impede aprovação do lote.
- Siffra: `editoras.aplica_percentual_autores = false`; autores dela recebem 0,00%.
- Lote só vira `APROVADO` com `uploads.status` sem conflito.

## APIs (rotas internas)
| Método | Rota | Quem | Função |
|---|---|---|---|
| POST | /api/uploads | admin | envia arquivo Abramus, detecta tipo e competência |
| GET | /api/uploads/:id | admin | status, conflitos, inconsistências |
| POST | /api/uploads/:id/aprovar | admin | aprova lote (bloqueado se houver pendência) |
| POST | /api/cadastro/importar | admin | importa CSV de editoras e autores |
| PUT | /api/taxas | admin | nova taxa com vigência (popup) |
| GET | /api/dashboard/ranking | admin | top 10 editoras e autores |
| GET | /api/dashboard/serie | admin, editora | evolução mensal (editora + autor) |
| GET | /api/dashboard/receita | admin, editora | por fonte ou por região |
| GET | /api/relatorios/:tipo/:id.pdf | admin, editora (só o próprio) | PDF no modelo Acorde |
| POST | /api/acessos/convites | admin | convida usuário de editora |
| DELETE | /api/acessos/:id | admin | revoga acesso |

## Integrações
- Neon (Postgres + Neon Auth).
- GitHub → Vercel (deploy de preview a partir do branch de desenvolvimento).
- E-mail transacional para convites (provedor a definir; plano gratuito).
