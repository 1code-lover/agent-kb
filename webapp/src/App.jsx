import { Navigate, Route, Routes } from "react-router-dom";
import ShellLayout from "./components/ShellLayout";
import AgentPage from "./pages/AgentPage";
import KnowledgePage from "./pages/KnowledgePage";
import QueryPage from "./pages/QueryPage";
import KbFilePage from "./pages/KbFilePage";
import SettingsPage from "./pages/SettingsPage";
import ModelsPage from "./pages/ModelsPage";
import KbWebPage from "./pages/KbWebPage";
import KbManagePage from "./pages/KbManagePage";
import StoragePage from "./pages/StoragePage";
import AdvancedPage from "./pages/AdvancedPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ShellLayout />}>
        <Route index element={<AgentPage />} />
        <Route path="agent" element={<AgentPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="query" element={<QueryPage />} />
        <Route path="kb-file" element={<KbFilePage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="kb-web" element={<KbWebPage />} />
        <Route path="kb-manage" element={<KbManagePage />} />
        <Route path="storage" element={<StoragePage />} />
        <Route path="advanced" element={<AdvancedPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
