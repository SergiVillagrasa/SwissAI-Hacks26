import { useCallback, useEffect, useState } from "react";

export type Page = "home" | "workflow";

function pageFromPath(): Page {
  return window.location.pathname === "/workflow" ? "workflow" : "home";
}

export function usePage() {
  const [page, setPage] = useState<Page>(pageFromPath);
  useEffect(() => {
    const handlePopState = () => setPage(pageFromPath());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);
  const navigate = useCallback((next: Page) => {
    window.history.pushState({}, "", next === "workflow" ? "/workflow" : "/");
    setPage(next);
  }, []);
  return { page, navigate };
}
