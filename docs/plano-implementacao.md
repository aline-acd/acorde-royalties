# Plano de implementação

## Fase 0 — Preparação (concluída)
- Análise dos relatórios Abramus e dos modelos de PDF.
- Cadastro inicial de editoras (20) e autores (82) em CSV, com taxas.
- Documentação básica em `docs/` e `CLAUDE.md`.
- Protótipo visual com dados de exemplo (`preview/index.html`).

**Critérios de aceite:** CSVs revisados pela Acorde; protótipo aprovado para seguir.

## Fase 1 — Banco e importação (em andamento)
- [x] Schema aplicado no namespace `royalties` do branch `acorde-portal-dev` (projeto Neon ACORDE). Tabelas existentes no branch não foram alteradas.
- [x] Carga inicial: 20 editoras, 82 autores, 20 taxas de editora e 82 taxas de autor (herdadas da editora; Siffra = 0%). Divergências: 0.
- [ ] Carga dos lançamentos (scripts/import_abramus.py) e conferência de totais contra os PDFs.
- Aplicar `db/schema.sql` no branch `acorde-portal-dev`.
- `scripts/import_abramus.py` gera lançamentos normalizados e marca conflitos de competência.
- Carga dos CSVs de cadastro.

**Critérios de aceite:** totais de um mês conferem com os PDFs de referência (tolerância R$ 0,05 por editora); conflito de competência bloqueia aprovação.

## Fase 2 — Admin e dashboard
- Tela de upload e status do lote.
- Popup de taxa com vigência.
- Dashboard: top 10 editoras e autores, seletor de entidade, gráfico mensal (editora + autor), fonte/região.

**Critérios de aceite:** ranking e série batem com o banco; lote sem taxa pendente é o único aprovável.

## Fase 3 — Portal da editora
- Convite, login (Neon Auth), vínculo e revogação.
- Isolamento por editora testado (tentativa de acesso cruzado deve falhar).

**Critérios de aceite:** teste automatizado de isolamento passa; usuário revogado perde acesso.

## Fase 4 — PDFs
- Modelos de editora e autor reproduzidos em HTML → PDF.
- Download individual e em lote por competência.

**Critérios de aceite:** PDF gerado lado a lado com o modelo enviado, sem diferenças de layout nem de valores.

## Fase 5 — Publicação
- Revisão de segurança, deploy de preview para validação da Acorde.
- Aprovação explícita do gerente antes de qualquer acesso em produção.

**Critérios de aceite:** aprovação registrada; checklist de segurança concluído.

## Pendências
- Gerente aprovador (não definido).
- Nome do repositório GitHub e do projeto Vercel.
- Revisão do Guia de Estilo no Confluence.
- ID do card no Jira (não informado).
