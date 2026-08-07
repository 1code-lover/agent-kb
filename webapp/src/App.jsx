import { useEffect } from "react";
import { useLocation, useNavigate } from "./router";
import ShellLayout from "./components/ShellLayout";
import AgentPage from "./pages/AgentPage";
import KnowledgePage from "./pages/KnowledgePage";
import KbFilePage from "./pages/KbFilePage";
import SettingsPage from "./pages/SettingsPage";
import ModelsPage from "./pages/ModelsPage";
import KbWebPage from "./pages/KbWebPage";
import KbManagePage from "./pages/KbManagePage";
import StoragePage from "./pages/StoragePage";
import AdvancedPage from "./pages/AdvancedPage";

const ROUTES = {
  "/": AgentPage,
  "/agent": AgentPage,
  "/knowledge": KnowledgePage,
  "/kb-file": KbFilePage,
  "/settings": SettingsPage,
  "/models": ModelsPage,
  "/kb-web": KbWebPage,
  "/kb-manage": KbManagePage,
  "/storage": StoragePage,
  "/advanced": AdvancedPage,
};

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const Page = ROUTES[location.pathname] || AgentPage;

  useEffect(() => {
    if (!ROUTES[location.pathname]) {
      navigate("/", { replace: true });
    }
  }, [location.pathname, navigate]);

  return (
    <ShellLayout>
      <Page />
    </ShellLayout>
  );
}
