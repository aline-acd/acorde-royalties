# Jornada do usuário

## Admin (equipe Acorde)
1. Login (usuário interno).
2. Upload dos arquivos Abramus (Geral, Editora, Autor). Sistema detecta tipo e competência.
3. Se a competência divergir entre arquivos: lote em RASCUNHO, exibe conflito, não permite aprovar.
4. Revisão de inconsistências (beneficiário sem cadastro, taxa pendente, nome possivelmente duplicado).
5. Cadastro e ajuste de editoras e autores (CSV em massa ou formulário). Popup de taxa: percentual, vigência, observação.
6. Aprovação do lote. Os dados passam a aparecer no dashboard e nos portais das editoras.
7. Dashboard: top 10 editoras, top 10 autores, seletor de entidade, gráfico mensal, alternância fonte/região.
8. Relatórios: PDF por editora ou autor (modelo Acorde), download em lote por competência.
9. Gestão de acessos: convidar, revogar e vincular usuários a editoras.

## Editora
1. Recebe convite por e-mail, define senha, faz login.
2. Dashboard próprio: receita total (editora + autores), evolução mensal, por fonte ou região.
3. Lista de autores vinculados e relatório de cada um (somente dados da própria editora).
4. Download do relatório da editora em PDF. A taxa administrativa aparece no relatório da editora, não no do autor.

## Erros e estados vazios
- Sem dados aprovados na competência: mensagem clara, sem gráfico zerado enganoso.
- Arquivo com layout diferente: rejeitado, com a lista das colunas esperadas.
