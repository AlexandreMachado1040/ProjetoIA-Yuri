# Frontend — Motor PVSyst

Interface React + Vite que consome a API de simulação fotovoltaica.

## Configuração da API (Cloudflare Worker)

O frontend já vem apontado para o worker em produção
`https://motor-pvsyst.alexandreclm.workers.dev` (padrão definido em
`src/api/client.js`). Para rodar localmente, basta:

```bash
npm install
npm run dev          # http://localhost:5173
```

Para apontar para outro ambiente (backend local ou outro worker), defina
`VITE_WORKER_URL` em um arquivo `.env` (veja `.env.example`).

> Observação: o worker é uma versão **rápida/síncrona** do motor. KPIs principais,
> produção mensal e irradiância funcionam; **histograma, diagrama de perdas e
> download de PDF** não são fornecidos pelo worker e aparecem vazios na interface.
> Para a experiência completa, use o backend FastAPI (`backend/`).

## Deploy no Cloudflare Pages

O site é estático (Vite) e o worker libera CORS (`*`), então o Pages consome a
API sem ajustes. Há duas formas de publicar:

**A) Pela CLI (rápido):**

```bash
npm install
npm run build
npx wrangler pages deploy dist --project-name=motor-pvsyst-app
```

Ao final, o Pages mostra a URL pública (ex.: `https://motor-pvsyst-app.pages.dev`).

**B) Conectando o GitHub (deploy automático a cada push):**

No dashboard Cloudflare → **Workers & Pages** → **Create** → **Pages** →
*Connect to Git*, selecione o repositório e use estas configurações de build:

| Campo | Valor |
|---|---|
| Framework preset | `Vite` |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |

O arquivo `public/_redirects` (`/*  /index.html  200`) já garante o roteamento
SPA no Pages.

---

## React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
