# Acorde — Royalties Processor (PRD)

## Problem Statement (original, Portuguese)

Site de processamento e conversão de arquivos para a Acorde — administradora
de direitos autorais musicais. Clientes = editoras; editoras têm autores. A
Acorde cobra uma taxa administrativa % individualizada por editora e, quando
cabe, também do autor. A fonte dos dados são 3 relatórios exportados da
Abramus Digital:

- Relatório Geral (ZIP de CSVs ou CSV único): recebimento total consolidado
  por editora.
- Relatório Editora (XLSX): participação da editora no contrato de edição
  por obra.
- Relatório Autor (XLSX): valor bruto por autor, obra, fonte, território...

O sistema deve calcular a taxa administrativa (fonte: banco cadastrado via
UI ou CSV em massa), gerar relatórios Acorde detalhados por editora e por
autor, exportar PDFs com marca Acorde (preto/amarelo/branco) — e permitir
login individual para cada editora.

## Users
- Admin Acorde (aline@acordemusica.com.br): tudo.
- Editora: vê somente a si mesma, seus autores e seus relatórios.

## Core Requirements (static)
- Upload dos 3 tipos de relatório Abramus; parsing robusto BR (vírgula
  decimal, latin-1 fallback, ZIP com múltiplos CSVs).
- CRUD Editoras (nome, CNPJ, taxa_admin %, email, login opcional).
- CRUD Autores (nome, editora vinculada, taxa_admin %).
- Importação em massa via CSV para editoras e autores.
- Relatório editora com cálculo da taxa admin (bruto, taxa, líquido).
- Relatório autor que NÃO exibe a taxa admin — somente o valor líquido final.
- Exportação PDF com cabeçalho e rodapé Acorde (preto/amarelo).
- Dashboard admin: KPIs e gráfico por fonte (Spotify, YouTube...).
- Dashboard editora: escopo restrito.

## Architecture
- Backend: FastAPI, Motor (MongoDB async), JWT + bcrypt auth, pandas +
  openpyxl para XLSX, reportlab para PDFs.
- Frontend: React 19, Shadcn UI, Tailwind, Recharts, Sonner.
- MongoDB coleções: users, editoras, autores, uploads, royalty_rows.

## What's been implemented (Feb 2026)
- JWT auth (admin + editora), admin seeding idempotente a partir de .env.
- Upload de .zip/.csv/.xlsx para os 3 tipos de relatório Abramus.
- Parsers normalizam valores BR e armazenam linhas em `royalty_rows` com
  `titular_norm`/`nome_norm` para casamento.
- CRUD completo + importação CSV para editoras e autores (com e-mail).
- Criação de login para editora (gera user role=editora com editora_id).
- Dashboard admin com KPIs (valor total geral/editora/autor) + chart por
  fonte + top editoras.
- Dashboard editora com escopo restrito.
- Visualização e PDF de relatório Editora (com taxa admin).
- Visualização e PDF de relatório Autor (sem taxa admin, só valor líquido).
- **Logo Acorde no PDF** (versão com fundo transparente embutida no header).
- **Exportação em lote**: ZIP de PDFs por escopo (editora|autor|both) por competência.
- **Trava de repasse**: por editora/autor+competência, com status pago/pendente,
  valor, observação, data_pagamento e histórico (últimos 50 eventos).
- **Envio automático por e-mail**: integração Resend gerenciada pela Emergent,
  dispara notificação com link para o portal para editoras e/ou autores com
  e-mail cadastrado. Templates HTML com guardrails de segurança (sem forms,
  sem pedidos de credencial, URLs https-only).
- Design preto/amarelo/branco (Outfit + Manrope + JetBrains Mono).
- Testes: iter 1 = 21/21 backend; iter 2 = 39/39 backend; frontend validado.

## Backlog / Next
P0:
- Logo/modelo personalizado da Acorde no PDF (usuário vai enviar).
- Exportação em lote (gerar todos os PDFs de uma competência em ZIP).

P1:
- Comparação de competências (crescimento MoM).
- Envio automático dos relatórios por e-mail (Resend) para cada editora.
- Status de "pago/não pago" por repasse e histórico de repasses.

P2:
- Dashboard de autores com música mais tocada.
- Importação direta de outras fontes (UBC, ECAD).
