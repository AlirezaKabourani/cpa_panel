import { createBrowserRouter } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import CampaignBuilder from "./pages/CampaignBuilder";
import CustomersPage from "./pages/Customers";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "campaign", element: <CampaignBuilder /> },
      { path: "customers", element: <CustomersPage /> },
    ],
  },
]);
