-- Acorde Royalties — schema v1 (Postgres / Neon)
-- Aplicar somente no branch acorde-portal-dev.
-- Tudo fica no schema "royalties", isolado das tabelas já existentes no branch.
CREATE SCHEMA IF NOT EXISTS royalties;
SET search_path TO royalties;

CREATE TABLE editoras (
  id                          bigserial PRIMARY KEY,
  nome_abramus                text NOT NULL UNIQUE,      -- nome exato como vem no arquivo
  nome_exibicao               text NOT NULL,
  documento_mascarado         text,                       -- ex.: *****707 (nunca o documento completo)
  aplica_percentual_autores   boolean NOT NULL DEFAULT true,  -- false apenas para Siffra
  ativo                       boolean NOT NULL DEFAULT true,
  criado_em                   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE autores (
  id                    bigserial PRIMARY KEY,
  nome_abramus          text NOT NULL,
  nome_exibicao         text NOT NULL,
  documento_mascarado   text,
  editora_id            bigint NOT NULL REFERENCES editoras(id),
  ativo                 boolean NOT NULL DEFAULT true,
  criado_em             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (nome_abramus, editora_id)
);

-- Taxa administrativa com vigência. Ausência de linha = PENDENTE (nunca 0% implícito).
CREATE TABLE taxas (
  id                  bigserial PRIMARY KEY,
  beneficiario_tipo   text NOT NULL CHECK (beneficiario_tipo IN ('EDITORA','AUTOR')),
  beneficiario_id     bigint NOT NULL,
  percentual          numeric(5,2) NOT NULL CHECK (percentual >= 0 AND percentual <= 100),
  vigencia_inicio     date NOT NULL,
  vigencia_fim        date,
  motivo              text,
  alterado_por        text NOT NULL,
  criado_em           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX taxas_benef_idx ON taxas (beneficiario_tipo, beneficiario_id, vigencia_inicio);

CREATE TABLE uploads (
  id              bigserial PRIMARY KEY,
  tipo            text NOT NULL CHECK (tipo IN ('GERAL','EDITORA','AUTOR')),
  nome_arquivo    text NOT NULL,
  competencia     date,                         -- primeiro dia do mês
  status          text NOT NULL CHECK (status IN ('RASCUNHO','CONFLITO','APROVADO','REJEITADO')),
  linhas          integer NOT NULL DEFAULT 0,
  enviado_por     text NOT NULL,
  criado_em       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE lancamentos (
  id                    bigserial PRIMARY KEY,
  upload_id             bigint NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
  competencia           date NOT NULL,
  tipo_arquivo          text NOT NULL CHECK (tipo_arquivo IN ('EDITORA','AUTOR')),
  editora_id            bigint NOT NULL REFERENCES editoras(id),
  autor_id              bigint REFERENCES autores(id),          -- null quando a linha é da própria editora
  categoria             text,                                    -- CAT (E = editora; demais = autor)
  id_obra               text,
  obra                  text NOT NULL,
  fonte                 text NOT NULL,                           -- ex.: BRASIL - DIGITAL - SPOTIFY
  regiao                text,                                    -- TERRITORIO
  formato               text,
  tipo_utilizacao       text,                                    -- rubrica (DG, etc.)
  pagamento             text,
  periodo_texto         text,                                    -- período de uso como vem no arquivo
  unidades              numeric(18,4) NOT NULL DEFAULT 0,
  perc_total            numeric(9,6),
  perc_recebido         numeric(9,6),
  perc_beneficiario     numeric(9,6),                            -- PERC_EDITORA ou PERC_AUTOR
  liquido               numeric(18,6),
  valor_bruto           numeric(18,6) NOT NULL,                  -- VL_EDITORA ou VL_AUTOR
  taxa_aplicada_pct     numeric(5,2),                            -- null = pendente
  valor_taxa            numeric(18,6),
  valor_liquido         numeric(18,6)
);
CREATE INDEX lanc_comp_idx   ON lancamentos (competencia, editora_id);
CREATE INDEX lanc_autor_idx  ON lancamentos (autor_id, competencia);
CREATE INDEX lanc_upload_idx ON lancamentos (upload_id);

-- Usuários do portal por editora (login via Neon Auth; vínculo gerido pela Acorde)
CREATE TABLE usuarios_editora (
  id              bigserial PRIMARY KEY,
  auth_user_id    text NOT NULL UNIQUE,
  editora_id      bigint NOT NULL REFERENCES editoras(id),
  email           text NOT NULL,
  revogado_em     timestamptz,
  criado_em       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE usuarios_admin (
  id            bigserial PRIMARY KEY,
  auth_user_id  text NOT NULL UNIQUE,
  email         text NOT NULL,
  criado_em     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auditoria (
  id          bigserial PRIMARY KEY,
  quem        text NOT NULL,
  acao        text NOT NULL,
  alvo        text,
  detalhes    jsonb,
  criado_em   timestamptz NOT NULL DEFAULT now()
);

-- Total coletado por editora no mês: bruto da editora + bruto dos autores (aprovados)
CREATE VIEW v_total_editora_mes AS
SELECT l.competencia, l.editora_id,
       SUM(l.valor_bruto) AS total_bruto,
       SUM(COALESCE(l.valor_taxa,0)) AS total_taxa,
       SUM(COALESCE(l.valor_liquido,0)) AS total_liquido
FROM lancamentos l
JOIN uploads u ON u.id = l.upload_id AND u.status = 'APROVADO'
GROUP BY l.competencia, l.editora_id;

-- Row level security: cada editora vê somente os próprios lançamentos
ALTER TABLE lancamentos ENABLE ROW LEVEL SECURITY;
-- Política de exemplo (ajustar ao mecanismo de sessão do Neon Auth):
-- CREATE POLICY editora_ve_os_seus ON lancamentos FOR SELECT
--   USING (editora_id IN (SELECT editora_id FROM usuarios_editora
--                         WHERE auth_user_id = auth.user_id() AND revogado_em IS NULL));
