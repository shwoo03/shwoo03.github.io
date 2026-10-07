# AGENTS.md

Personal Korean blog built with Jekyll + Chirpy 7.6, deployed to GitHub Pages
(`https://스우스우.site`) by `.github/workflows/pages-deploy.yml` on every push to `main`.
The repository is public: anything committed, including `_drafts/`, is visible.

## Local environment

- The system Ruby is 4.0, which Chirpy does not support. Always use the keg-only Ruby 3.4:
  `export PATH="/opt/homebrew/opt/ruby@3.4/bin:$PATH"` before any `bundle` command.
- Gems live in `vendor/bundle` (git-ignored). If they are missing, run `bundle install`.
- Check a build the same way CI does:

  ```sh
  JEKYLL_ENV=production bundle exec jekyll b -d _site
  bundle exec htmlproofer _site --disable-external \
    --ignore-urls "/^http:\/\/127.0.0.1/,/^http:\/\/0.0.0.0/,/^http:\/\/localhost/"
  ```

## Publishing from Notion

The user does not run commands. They hand over a Notion link and talk to the agent:

| User says | Agent does |
|---|---|
| "이 링크 로컬에서 띄워줘" + Notion link | Import the page, start the local preview, report the URL |
| Fix requests | Re-import or adjust, the preview rebuilds by itself |
| "push 해줘" | Build check, commit, push to `main`, stop the preview |

**Never commit or push before the user says "push 해줘" (or an equivalent explicit request).**
The detailed procedure is in the `notion-post` skill: `.claude/skills/notion-post/SKILL.md`.

- Importer: `tools/notion_import.py` (stdlib-only Python, run with `--help` for options).
  Posts go to `_posts/`, original images and files to `assets/img/notion/<page-id>/`.
- Styles for imported markup: `_sass/notion.scss`, loaded from `assets/css/jekyll-theme-chirpy.scss`.
  Everything is scoped to `.notion-page`, so hand-written posts are unaffected.
- `NOTION_TOKEN` comes from the user's shell (`~/.zshrc`). Never ask for it in chat, print it,
  or write it to a file.

## Crawling

- Open-source-first gate: before writing non-trivial implementation code for a subsystem that is infrastructure-like or likely to exceed roughly 100 lines, actually search the web and GitHub for existing projects first — do not answer from memory or start implementing first. Rank candidates by release recency and commit activity first, then stars/adoption as a tie-breaker, then license and purpose fit, and show a reuse-vs-build shortlist before implementing. See `../AI_architecture/recipes/open-source-reuse.md`.
- If this project needs to collect public web content, start from Crawl4AI, the AI Project Kit's preferred crawler, instead of writing a new requests/httpx + HTML-parser crawler. Security testing, logged-in automation, and exploit scripts keep their own tools. Record the decision in `docs/REFERENCES.md` before adding it (template: `../AI_architecture/examples/reference-decisions/crawl4ai-adapter.md`).
