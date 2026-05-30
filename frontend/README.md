# Frontend — Motor PVSyst

Interface React + Vite que consome a API de simulação fotovoltaica.

## Configuração da API (Cloudflare Worker)

O frontend está apontado para o **Cloudflare Worker** `motor-pvsyst`. Defina a URL
do seu worker antes de rodar:

```bash
cp .env.example .env          # ou .env.local
# edite VITE_WORKER_URL com o seu subdomínio .workers.dev
npm install
npm run dev
```

A URL do worker fica em `VITE_WORKER_URL` (veja `.env.example`). Se não for
definida, o código usa um placeholder que **não funciona** até ser ajustado.

> Observação: o worker é uma versão **rápida/síncrona** do motor. KPIs principais,
> produção mensal e irradiância funcionam; **histograma, diagrama de perdas e
> download de PDF** não são fornecidos pelo worker e aparecem vazios na interface.
> Para a experiência completa, use o backend FastAPI (`backend/`).

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
