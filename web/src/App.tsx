import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import DashboardPage from "./pages/DashboardPage";
import TickerPage from "./pages/TickerPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/ticker/:symbol" element={<TickerPage />} />
      </Routes>
    </Layout>
  );
}
