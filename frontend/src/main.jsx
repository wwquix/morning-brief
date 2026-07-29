import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { App } from "./App.jsx";
import { PlannerSection } from "./PlannerSection.jsx";

const rootElement = document.getElementById("root");

if (rootElement) {
  createRoot(rootElement).render(
    <React.StrictMode>
      <App data={window.BRIEF_DATA} />
    </React.StrictMode>
  );

  const plannerRoot = document.createElement("div");
  plannerRoot.id = "planner-root";
  rootElement.insertAdjacentElement("afterend", plannerRoot);

  createRoot(plannerRoot).render(
    <React.StrictMode>
      <PlannerSection data={window.BRIEF_DATA?.planner} />
    </React.StrictMode>
  );
}
