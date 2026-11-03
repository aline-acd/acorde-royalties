# Acorde Royalties — referência para sessões de código

Sistema de processamento e conversão dos relatórios Abramus Digital para a Acorde (administradora de direitos autorais).
Clientes: editoras. Cada editora tem autores vinculados. Acesso: portal admin (equipe Acorde) e portal por editora (login individual).

## Documentos de referência (em `docs/`)
- `docs/PRD.md` — objetivo, público, escopo, métricas
- `docs/TRD.md` — decisões técnicas tomadas
- `docs/site-flow.md` — jornada do usuário (admin e editora)
- `docs/brief-ui.md` — brief de design UI/UX (inclui referência ao Guia de Estilo Acorde)
- `docs/backend-schema.md` — dados, APIs e integrações
- `docs/plano-implementacao.md` — fases, tarefas e critérios de aceite

## Regras obrigatórias
- Estilo visual: Guia de Estilo Acorde (atualizado 2026), Confluence › PEMP. Fonte Avenir Next LT Pro; Grafite #14171A, Off-white #F2EFE9, Amarelo #FFF51C (texto sobre amarelo em Grafite). Fotos de equipe em preto e branco.
- Preview usa somente o branch Neon `acorde-portal-dev`. Nunca `production`. Não revelar strings de conexão.
- Nenhum acesso público antes da aprovação explícita do gerente da Acorde.
- Documentos (CPF/CNPJ) sempre mascarados. Nunca gravar dados pessoais, bancários ou de clientes em `docs/`, neste arquivo, em commits ou em pastas sincronizadas (Google Drive).
- Taxa administrativa ausente nunca vira 0% silenciosamente. 0% só quando não há cobrança, com registro explícito.
- Competência vem do conteúdo do arquivo. Divergência entre arquivos gera conflito: lote fica em RASCUNHO e não pode ser aprovado.
- Exceção Siffra: percentual da editora não se aplica aos autores (autores 0,00%).

## Como rodar (local)
- `scripts/import_abramus.py <pasta_com_xlsx> <pasta_saida_FORA_do_repo>` — gera lançamentos normalizados. A saída contém dados reais: nunca dentro do repositório.
- `db/schema.sql` — schema Postgres (Neon). Aplicar somente no branch `acorde-portal-dev`.
- `preview/index.html` — protótipo estático do dashboard com dados de exemplo (sem conexão com banco).
