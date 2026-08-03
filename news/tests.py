from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from news.models import Article, Category


class ArticleDetailSeoTests(TestCase):
    def test_article_detail_renders_structured_data_and_transparency_fields(self):
        category = Category.objects.create(name="Public Interest", slug="public-interest")
        article = Article.objects.create(
            title="Original public interest update",
            slug="original-public-interest-update",
            category=category,
            summary="A clear summary describing the important public-interest update for readers.",
            content="<p>This independently written report gives readers useful background and local context.</p>",
            status=Article.Status.PUBLISHED,
            source_name="Official reference",
            source_url="https://example.com/reference",
            image_caption="Representative image caption",
            image_credit="The Up Media",
            meta_description="A clear search description for the public-interest update and reader context.",
        )

        response = self.client.get(reverse("news:article_detail", kwargs={"slug": article.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "application/ld+json")
        self.assertContains(response, "BreadcrumbList")
        self.assertContains(response, "1 min read")
        self.assertContains(response, "Reference:")

    def test_future_published_articles_are_not_public_yet(self):
        category = Category.objects.create(name="Education", slug="education")
        Article.objects.create(
            title="Scheduled education analysis",
            slug="scheduled-education-analysis",
            category=category,
            summary="A scheduled report summary with enough context for readers.",
            content="<p>This article should become public only after its scheduled time.</p>",
            status=Article.Status.PUBLISHED,
            published_at=timezone.now() + timezone.timedelta(hours=2),
        )

        self.assertEqual(Article.published.count(), 0)
