# Instruções para a equipe (o que precisa ser feito manualmente)

## 1. Enviar o código ao GitHub (uma vez)
No terminal, dentro da pasta `acorde-royalties`:
```
git remote add origin https://github.com/ACORDE-Musica/acorde-royalties.git
git push -u origin main
```
Se o GitHub pedir login, use sua conta com permissão na organização ACORDE-Musica.

## 2. Criar o branch de trabalho (uma vez)
```
git checkout -b acorde-portal-dev
git push -u origin acorde-portal-dev
```

## 3. Configurar o Vercel (uma vez)
- Abra o projeto no Vercel, em **Settings › Git**.
- Em **Production Branch**, deixe `main` ou outro branch que **não** seja `acorde-portal-dev`, e **não** faça deploy de produção até a aprovação do gerente.
- Não adicione domínio público.
- Preview: o branch `acorde-portal-dev` gera URLs de preview privadas.

## 4. Conferir o banco de dev (opcional, para validar)
No Neon, projeto **ACORDE**, branch **acorde-portal-dev**, o schema `royalties` deve ter 9 objetos: `editoras`, `autores`, `taxas`, `uploads`, `lancamentos`, `usuarios_editora`, `usuarios_admin`, `auditoria` e a view `v_total_editora_mes`.

## 5. Quando precisar de decisão sua
- Confirmar se o branch `acorde-portal-dev` é o correto para este projeto. Ele já contém outro conjunto de tabelas (titular, obra, rendimento, ECAD etc.). Nossas tabelas estão isoladas no schema `royalties`, mas vale confirmar.
- Autores duplicados a confirmar: Cauan Batistela/Batistella; Ailson/Alyson Guedes da Fonseca.
- Envio dos modelos PDF de editora e autor, para a fase 4.
