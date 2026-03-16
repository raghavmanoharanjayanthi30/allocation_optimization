# React Tutorial (for this project)

## 1) What React is

React is a UI library for building interactive screens from reusable components.

In this project, React:
- calls backend APIs,
- lets you paste/edit JSON,
- runs optimizers and displays results.

## 2) File walkthrough

- `frontend/src/App.jsx` -> main UI and state
- `frontend/src/api.js` -> backend fetch helpers
- `frontend/src/components/JsonEditor.jsx` -> reusable textarea component

## 3) How to run

```bash
cd code/ui/frontend
npm install
npm run dev
```

## 4) React concepts to notice

- **State (`useState`)**:
  - selected method
  - technicians/jobs JSON strings
  - API result/error
- **Effects (`useEffect`)**:
  - load methods once on app startup
- **Events**:
  - button click -> API call
  - select change -> update method

## 5) Next mini exercise

1. Add a slider for technician count.
2. Use that slider value in `handleGenerate`.
3. Add a small chart or summary card showing assignment rate.
