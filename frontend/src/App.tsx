import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./lib/auth";
import { Home } from "./pages/Home";
import { LaneEditor } from "./pages/LaneEditor";
import { Lanes } from "./pages/Lanes";
import { LeadDetail } from "./pages/LeadDetail";
import { Login } from "./pages/Login";
import { Pipeline } from "./pages/Pipeline";
import { Queue } from "./pages/Queue";
import { Settings } from "./pages/Settings";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-slate-500">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Home />} />
        <Route path="queue" element={<Queue />} />
        <Route path="pipeline" element={<Pipeline />} />
        <Route path="leads/:id" element={<LeadDetail />} />
        <Route path="lanes" element={<Lanes />} />
        <Route path="settings" element={<Settings />} />
        <Route path="lanes/new" element={<LaneEditor />} />
        <Route path="lanes/:id" element={<LaneEditor />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
