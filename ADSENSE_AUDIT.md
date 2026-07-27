# AdSense and Search Quality Audit

Audit date: 2026-07-27

This audit covers the Django news/content website in this repository. The goal is to improve reader trust, Google Search Essentials alignment, AdSense readiness, and editorial safety without mass-generating or copying content.

| Issue | Affected file/page | Severity | Recommended fix | Implementation status |
| --- | --- | --- | --- | --- |
| Missing visible editorial policy pages | Footer, static pages | High | Add editorial, fact-checking, and corrections policy pages, then link them from the footer and sitemap. | Implemented |
| Risky wording suggested content may be collected from newspapers/media reports | `templates/core/terms.html`, `templates/core/disclaimer.html`, `templates/core/about.html` | High | Replace wording with original editorial process language and clear source attribution standards. | Implemented |
| Article admin does not warn editors before publishing thin or under-sourced content | `news/admin.py`, `news/models.py` | High | Add optional transparency fields and non-blocking warnings for short body, missing image credit, missing source, and missing review/fact-check owner. | Implemented |
| Article pages could show stronger trust signals | `templates/news/article_detail.html`, `news/views.py` | Medium | Show reading time, review/fact-check metadata, image caption/credit, correction note, and BreadcrumbList structured data. | Implemented |
| Empty categories can appear in navigation | `core/context_processors.py` | Medium | Only show active categories that have published articles. | Implemented |
| No read-only quality audit workflow for existing content | `news/management/commands/` | Medium | Add management command to list thin, duplicate-title, source-missing, image-credit-missing, and meta-description issues. | Implemented |
| Contact page was mostly static | `core/views.py`, `core/forms.py`, `templates/core/contact.html` | Medium | Add a working CSRF-protected contact form with spam honeypot and error handling. | Implemented |
| Sitemap should include trust pages | `core/sitemaps.py` | Medium | Add new policy pages to static sitemap. | Implemented |
| The supplied article text must not be blindly published | Content workflow | High | Verify topic facts against official/primary sources before publishing; do not copy structure or wording from any source. | Not auto-published by design |
| Production deployment requested after completion | Git/VPS workflow | High | Do not push/pull/restart production without explicit approval and final review. | Approved by user for this deployment |

## Manual Review Still Needed

- Review existing published articles with `python manage.py audit_content_quality --status published --csv content-quality.csv` on the VPS or a DB-connected environment.
- Update low-word-count or under-sourced articles manually; do not bulk-generate content.
- Confirm every featured image has permission, caption, and credit.
- Confirm `SITE_DOMAIN`, `CONTACT_EMAIL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `robots.txt`, `ads.txt`, and sitemap URLs point to the production domain.
