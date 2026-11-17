import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastProvider } from "./lib/toast";
import { UploadPage } from "./routes/UploadPage";
import { DashboardPage } from "./routes/DashboardPage";
import { FCDetailPage } from "./routes/FCDetailPage";
import { HistoryPage } from "./routes/HistoryPage";

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/upload" replace />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/dashboard/:id" element={<DashboardPage />} />
              <Route path="/dashboard/:id/fc/:name" element={<FCDetailPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="*" element={<Navigate to="/upload" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </ErrorBoundary>
  );
}
