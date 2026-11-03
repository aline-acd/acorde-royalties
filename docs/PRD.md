# PRD — Acorde Royalties

**Objetivo:** converter os relatórios Abramus Digital (Geral, Editora, Autor) em dados consistentes, calcular a receita de editoras e autores descontando a taxa administrativa, e entregar relatórios (tela e PDF no modelo Acorde) e dashboards.

**Público:**
- Equipe Acorde (admin): processa uploads, confere, cadastra editoras e autores, define taxas, aprova lotes.
- Editoras (clientes): veem somente os próprios dados, relatórios e gráficos.

**Escopo (versão 1):**
- Importação de Abramus (Editora e Autor em XLSX; Geral em ZIP/CSV).
- Cadastro de editoras e autores (importação em massa por CSV e cadastro manual).
- Taxa administrativa por editora e por autor, com histórico por competência e popup de alteração.
- Cálculo: valor bruto da editora e do autor, taxa, valor líquido.
- Dashboard admin: top 10 editoras, top 10 autores, seleção de entidade, gráfico de evolução mensal (editora + autor somados), receita por fonte ou por região.
- Login por editora com múltiplos usuários; convite e revogação pela equipe Acorde.
- Relatórios PDF no modelo Acorde (editora e autor).

**Fora de escopo (v1):** pagamentos, emissão de nota, integração direta com a Abramus.

**Métricas de sucesso:**
- 100% dos lançamentos importados com competência e beneficiário identificados.
- Conferência de totais bate com os PDFs de referência (tolerância R$ 0,05 por editora).
- Tempo de processamento mensal reduzido (meta a definir com a Acorde).
- Zero lotes aprovados com taxa pendente ou conflito de competência.
