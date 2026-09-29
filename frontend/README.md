# Frontend — AI Project & Workflow Automation Agent

React + Vite + TypeScript SPA. See the [project README](../README.md) for setup
and usage.

```bash
npm install     # install dependencies
npm run dev     # dev server on http://localhost:5173 (proxies /api to :8000)
npm run build   # typecheck (tsc -b) + production build to dist/
npm run lint    # oxlint
```

## Structure

- `src/api.ts` — typed fetch client for the backend API
- `src/types.ts` — API response types
- `src/App.tsx` — router (`/`, `/projects/:id`, `/projects/:id/tasks/:taskId`)
- `src/pages/` — `HomePage`, `DashboardPage`, `TaskReviewPage`
- `src/components/` — `Layout` (sidebar shell), tables, badges, tabs, spinner,
  forms

All data comes from the backend; there is no mock data.
