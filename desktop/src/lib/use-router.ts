/**
 * A tiny hash router.
 *
 * The app used to keep the current page in React state, which meant Settings
 * had to be a modal and the back button did nothing. Hash routes make every
 * screen linkable (`#/voices`) and let the OS back button work.
 */
import { useCallback, useEffect, useState } from "react";
import { isPageKey, type PageKey } from "./pages";

const DEFAULT_PAGE: PageKey = "studio";

function currentHash(): PageKey {
  const raw = window.location.hash.replace(/^#\/?/, "").trim().toLowerCase();
  return isPageKey(raw) ? raw : DEFAULT_PAGE;
}

export function useHashRoute(): [PageKey, (page: PageKey) => void] {
  const [page, setPage] = useState<PageKey>(currentHash);

  useEffect(() => {
    const onHashChange = () => setPage(currentHash());
    window.addEventListener("hashchange", onHashChange);
    if (!window.location.hash) {
      window.history.replaceState(null, "", `#/${DEFAULT_PAGE}`);
    }
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((next: PageKey) => {
    if (currentHash() === next) {
      setPage(next);
      return;
    }
    window.location.hash = `#/${next}`;
    setPage(next);
  }, []);

  return [page, navigate];
}
