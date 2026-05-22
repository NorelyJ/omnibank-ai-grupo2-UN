# Demo artifacts

This directory holds demo-day evidence. Some items are captured live during the
demo dry runs (they need a browser / screen recorder and are HITL deliverables):

- `argocd-synced.png` — screenshot of the ArgoCD UI showing the `omnibank`
  Application **Synced + Healthy** with the full app tree. Capture it with:
  ```bash
  make install-argocd
  kubectl -n argocd port-forward svc/argocd-server 8080:80
  # open http://localhost:8080, log in, screenshot the omnibank app tree
  ```
- `demo-backup.mp4` — recording of demo dry run 2 (Slice 12), kept as a fallback
  if demo-day wifi fails.
- `dry-run-1-notes.md` — surprises found during demo dry run 1 (Slice 12).
