import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { HomePage } from './pages/HomePage'
import { TaskReviewPage } from './pages/TaskReviewPage'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects/:projectId" element={<DashboardPage />} />
          <Route
            path="/projects/:projectId/tasks/:taskId"
            element={<TaskReviewPage />}
          />
          <Route path="*" element={<HomePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
